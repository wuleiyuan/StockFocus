"""
StockFocus ETL 处理器 - 重构版本
专注于数据提取、转换和加载任务
"""
import logging
import time
from datetime import datetime, time as dt_time
from typing import Dict, Any, List, Optional
import pandas as pd

from config import config, setup_network_config, get_db_engine
from backend_service import StockDataService

# 设置配置
setup_network_config()
logger = config.setup_logging()

class ETLProcessor:
    """ETL数据处理器"""
    
    def __init__(self):
        self.data_service = StockDataService()
        self.engine = get_db_engine()
    
    def is_trading_time(self) -> bool:
        """判断当前是否为A股交易时间"""
        now = datetime.now()
        
        # 周末不运行
        if now.weekday() >= 5:
            return False
        
        current_time = now.time()
        
        # 上午: 9:15-11:35 (含开盘集合竞价)
        morning_start = dt_time(9, 15)
        morning_end = dt_time(11, 35)
        
        # 下午: 13:00-15:05
        afternoon_start = dt_time(13, 0)
        afternoon_end = dt_time(15, 5)
        
        return (morning_start <= current_time <= morning_end) or \
               (afternoon_start <= current_time <= afternoon_end)
    
    def run_etl_cycle(self) -> bool:
        """运行一次ETL周期"""
        try:
            logger.info("🔄 开始ETL数据处理周期")
            
            # 获取监控的股票
            stocks_df = self.data_service.db.get_monitored_stocks()
            
            if stocks_df.empty:
                logger.warning("⚠️ 没有找到需要处理的股票数据")
                return False
            
            # 分批处理数据
            symbols = stocks_df['symbol'].tolist()
            fair_price_map = dict(zip(stocks_df['symbol'], stocks_df['fair_price']))
            
            batch_size = config.BATCH_SIZE
            total_processed = 0
            
            for i in range(0, len(symbols), batch_size):
                batch_symbols = symbols[i:i+batch_size]
                
                # 获取实时数据
                realtime_data = self.data_service.api.fetch_realtime_batch(batch_symbols)
                
                if realtime_data:
                    # 转换数据格式
                    transformed_data = self._transform_data(realtime_data, fair_price_map)
                    
                    # 加载到数据库
                    loaded_count = self._load_to_database(transformed_data)
                    total_processed += loaded_count
                    
                    logger.info(f"✅ 批次 {i//batch_size + 1}: 处理 {loaded_count} 只股票")
                
                # 礼貌性延迟
                time.sleep(0.5)
            
            logger.info(f"🎉 ETL周期完成，共处理 {total_processed} 只股票")
            return True
            
        except Exception as e:
            logger.error(f"❌ ETL周期执行失败: {e}")
            return False
    
    def _transform_data(self, realtime_data: Dict[str, Any], fair_price_map: Dict[str, float]) -> List[Dict[str, Any]]:
        """转换数据格式"""
        transformed = []
        
        for symbol, data in realtime_data.items():
            fair_price = fair_price_map.get(symbol, 0)
            bias = ((data['price'] - fair_price) / fair_price * 100) if fair_price > 0 else 0
            
            transformed.append({
                'symbol': symbol,
                'name': data['name'],
                'current_price': data['price'],
                'fair_price': fair_price,
                'bias': bias,
                'mkt_cap': data['mkt_cap'],
                'industry': data['industry'],
                'updated_at': datetime.now()
            })
        
        return transformed
    
    def _load_to_database(self, data: List[Dict[str, Any]]) -> int:
        """加载数据到数据库"""
        if not data:
            return 0
        
        try:
            # 转换为DataFrame便于批量操作
            df = pd.DataFrame(data)
            
            # 使用merge/upsert语义更新数据
            from sqlalchemy import text
            
            loaded_count = 0
            with self.engine.begin() as conn:
                for _, row in df.iterrows():
                    result = conn.execute(
                        text("""
                            INSERT INTO market_scan_results 
                            (symbol, name, current_price, fair_price, bias, mkt_cap, industry, updated_at)
                            VALUES (:symbol, :name, :current_price, :fair_price, :bias, :mkt_cap, :industry, :updated_at)
                            ON CONFLICT (symbol) DO UPDATE SET
                                name = EXCLUDED.name,
                                current_price = EXCLUDED.current_price,
                                fair_price = EXCLUDED.fair_price,
                                bias = EXCLUDED.bias,
                                mkt_cap = EXCLUDED.mkt_cap,
                                industry = EXCLUDED.industry,
                                updated_at = EXCLUDED.updated_at
                        """),
                        row.to_dict()
                    )
                    loaded_count += result.rowcount
            
            return loaded_count
            
        except Exception as e:
            logger.error(f"数据库加载失败: {e}")
            return 0
    
    def run_etl_loop(self):
        """运行ETL主循环"""
        logger.info("🚀 StockFocus ETL处理器已启动")
        
        consecutive_failures = 0
        max_failures = 5
        
        while True:
            try:
                # 检查交易时间
                if not self.is_trading_time():
                    logger.info("🕒 非交易时段，ETL处理器休眠5分钟")
                    consecutive_failures = 0  # 重置失败计数
                    time.sleep(300)
                    continue
                
                # 执行ETL周期
                success = self.run_etl_cycle()
                
                if success:
                    consecutive_failures = 0
                    logger.info(f"💤 ETL周期完成，休眠 {config.REFRESH_INTERVAL} 秒...")
                    time.sleep(config.REFRESH_INTERVAL)
                else:
                    consecutive_failures += 1
                    if consecutive_failures >= max_failures:
                        logger.error(f"❌ 连续失败 {max_failures} 次，ETL处理器停止")
                        break
                    else:
                        logger.warning(f"⚠️ ETL失败，将在 {config.REFRESH_INTERVAL} 秒后重试...")
                        time.sleep(config.REFRESH_INTERVAL)
                
            except KeyboardInterrupt:
                logger.info("👋 ETL处理器被用户中断")
                break
            except Exception as e:
                consecutive_failures += 1
                logger.error(f"❌ ETL主循环异常: {e}")
                
                if consecutive_failures >= max_failures:
                    logger.error(f"❌ 连续异常 {max_failures} 次，ETL处理器停止")
                    break
                
                time.sleep(config.REFRESH_INTERVAL)

def main():
    """主函数"""
    logger.info("🎯 StockFocus ETL处理器启动中...")
    
    processor = ETLProcessor()
    processor.run_etl_loop()

if __name__ == "__main__":
    main()