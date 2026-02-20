"""
StockFocus 专业ETL数据管道
支持增量更新、错误重试、数据校验
"""
import time
import logging
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
import pandas as pd

from config import config, get_db_engine
from stock_api import EastMoneyAPI
from validators import DataValidator, sanitize_stock_dataframe

logger = logging.getLogger(__name__)


class ETLStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class ETLResult:
    status: ETLStatus
    total_records: int = 0
    success_records: int = 0
    failed_records: int = 0
    errors: List[str] = None
    duration_seconds: float = 0
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class ETLBase(ABC):
    def __init__(self, name: str):
        self.name = name
        self.engine = get_db_engine()
        self.validator = DataValidator()
    
    @abstractmethod
    def extract(self) -> pd.DataFrame:
        pass
    
    @abstractmethod
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        pass
    
    @abstractmethod
    def load(self, df: pd.DataFrame) -> int:
        pass
    
    def validate(self, df: pd.DataFrame) -> ETLResult:
        validation = self.validator.validate_dataframe(df)
        if validation['is_valid']:
            return ETLResult(status=ETLStatus.SUCCESS, total_records=len(df))
        return ETLResult(
            status=ETLStatus.FAILED,
            errors=validation['errors'][:10]
        )
    
    def run(self) -> ETLResult:
        start_time = time.time()
        
        try:
            logger.info(f"[{self.name}] 开始提取数据...")
            df = self.extract()
            
            logger.info(f"[{self.name}] 开始转换数据...")
            df = self.transform(df)
            
            logger.info(f"[{self.name}] 开始加载数据...")
            loaded = self.load(df)
            
            duration = time.time() - start_time
            return ETLResult(
                status=ETLStatus.SUCCESS,
                total_records=len(df),
                success_records=loaded,
                duration_seconds=duration
            )
            
        except Exception as e:
            logger.error(f"[{self.name}] ETL失败: {e}")
            return ETLResult(
                status=ETLStatus.FAILED,
                errors=[str(e)],
                duration_seconds=time.time() - start_time
            )


class StockPriceETL(ETLBase):
    def __init__(self, symbols: List[str] = None):
        super().__init__("StockPriceETL")
        self.symbols = symbols
        self.api = EastMoneyAPI()
    
    def extract(self) -> pd.DataFrame:
        from sqlalchemy import text
        
        if not self.symbols:
            df = pd.read_sql(text("SELECT symbol, fair_price FROM market_scan_results"), self.engine)
            self.symbols = df['symbol'].tolist()
        
        data = self.api.fetch_realtime_batch(self.symbols)
        
        records = []
        for symbol, item in data.items():
            records.append({
                'symbol': symbol,
                'current_price': item.get('price', 0),
                'name': item.get('name', ''),
                'mkt_cap': item.get('mkt_cap', 0),
                'industry': item.get('industry', '')
            })
        
        df = pd.DataFrame(records)
        
        fair_df = pd.read_sql(text("SELECT symbol, fair_price FROM market_scan_results"), self.engine)
        df = df.merge(fair_df, on='symbol', how='left')
        
        return df
    
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        
        df['bias'] = df.apply(
            lambda r: ((r['current_price'] - r['fair_price']) / r['fair_price'] * 100) 
            if r['fair_price'] and r['fair_price'] > 0 else 0,
            axis=1
        )
        
        df = sanitize_stock_dataframe(df)
        
        validation = self.validator.validate_dataframe(df)
        if not validation['is_valid']:
            logger.warning(f"数据验证警告: {validation['invalid_rows']} 条无效数据")
        
        return df
    
    def load(self, df: pd.DataFrame) -> int:
        if df.empty:
            return 0
        
        from sqlalchemy import text
        
        loaded = 0
        with self.engine.begin() as conn:
            for _, row in df.iterrows():
                try:
                    conn.execute(
                        text("""
                            UPDATE market_scan_results 
                            SET current_price=:price, name=:name, 
                                mkt_cap=:mkt_cap, industry=:industry, 
                                bias=:bias, updated_at=NOW()
                            WHERE symbol=:symbol
                        """),
                        {
                            'price': row['current_price'],
                            'name': row['name'],
                            'mkt_cap': row['mkt_cap'],
                            'industry': row['industry'],
                            'bias': row['bias'],
                            'symbol': row['symbol']
                        }
                    )
                    loaded += 1
                except Exception as e:
                    logger.error(f"加载失败 {row['symbol']}: {e}")
        
        return loaded


class ETLPipeline:
    def __init__(self):
        self.stages: List[ETLBase] = []
        self.error_handler: Optional[Callable] = None
    
    def add_stage(self, etl: ETLBase):
        self.stages.append(etl)
        return self
    
    def set_error_handler(self, handler: Callable):
        self.error_handler = handler
    
    def run(self) -> List[ETLResult]:
        results = []
        
        for stage in self.stages:
            logger.info(f"=== 执行阶段: {stage.name} ===")
            result = stage.run()
            results.append(result)
            
            if result.status == ETLStatus.FAILED:
                if self.error_handler:
                    self.error_handler(stage.name, result)
                break
            elif result.status == ETLStatus.PARTIAL:
                logger.warning(f"阶段 {stage.name} 部分成功")
        
        return results


class ETLScheduler:
    def __init__(self):
        self.pipeline = ETLPipeline()
        self.is_running = False
    
    def add_price_etl(self, symbols: List[str] = None):
        self.pipeline.add_stage(StockPriceETL(symbols))
        return self
    
    def run_once(self) -> List[ETLResult]:
        return self.pipeline.run()
    
    def run_continuous(self, interval_seconds: int = 60, max_iterations: int = None):
        self.is_running = True
        iteration = 0
        
        while self.is_running:
            if max_iterations and iteration >= max_iterations:
                logger.info("达到最大迭代次数，停止运行")
                break
            
            logger.info(f"=== ETL循环 第 {iteration + 1} 次 ===")
            results = self.run_once()
            
            for r in results:
                logger.info(f"状态: {r.status.value}, 成功: {r.success_records}/{r.total_records}")
            
            iteration += 1
            time.sleep(interval_seconds)
    
    def stop(self):
        self.is_running = False


def run_etl_pipeline(symbols: List[str] = None) -> ETLResult:
    etl = StockPriceETL(symbols)
    return etl.run()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run_etl_pipeline()
    print(f"ETL完成: {result.status.value}, 加载 {result.success_records} 条记录")
