"""
StockFocus 后端数据服务 - 重构版本
提供实时股价更新和ETL处理功能
"""
import time
import pandas as pd
from datetime import datetime, time as dt_time
from typing import Dict, Any, List
from sqlalchemy import text
import logging

from config import config, setup_network_config, get_db_engine
from stock_api import EastMoneyAPI

setup_network_config()
logger = config.setup_logging()

class DatabaseManager:
    """数据库管理类"""
    
    def __init__(self):
        self.engine = get_db_engine()
    
    def get_monitored_stocks(self) -> pd.DataFrame:
        """获取需要监控的股票列表"""
        try:
            query = "SELECT symbol, fair_price FROM market_scan_results"
            return pd.read_sql(query, self.engine)
        except Exception as e:
            logger.error(f"获取监控股票列表失败: {e}")
            return pd.DataFrame()
    
    def update_stock_prices(self, price_data: Dict[str, Any], fair_price_map: Dict[str, float]) -> int:
        """批量更新股票价格"""
        if not price_data:
            return 0
        
        updated_count = 0
        try:
            with self.engine.begin() as conn:
                for symbol, data in price_data.items():
                    fair_price = fair_price_map.get(symbol, 0)
                    bias = ((data['price'] - fair_price) / fair_price * 100) if fair_price > 0 else 0
                    
                    result = conn.execute(
                        text("""
                            UPDATE market_scan_results 
                            SET current_price=:price, name=:name, 
                                mkt_cap=:mkt_cap, industry=:industry, bias=:bias 
                            WHERE symbol=:symbol
                        """),
                        {
                            "price": data['price'],
                            "name": data['name'],
                            "mkt_cap": data['mkt_cap'],
                            "industry": data['industry'],
                            "bias": bias,
                            "symbol": symbol
                        }
                    )
                    updated_count += result.rowcount
            
            logger.info(f"✅ 成功更新 {updated_count} 只股票数据")
            return updated_count
            
        except Exception as e:
            logger.error(f"批量更新股票价格失败: {e}")
            return 0

class TradingTimeChecker:
    """交易时间检查器"""
    
    @staticmethod
    def is_trading_time() -> bool:
        """判断当前是否为A股交易时间"""
        now = datetime.now()
        
        # 周末不交易
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

class StockDataService:
    """股票数据服务主类"""
    
    def __init__(self):
        self.api = EastMoneyAPI()
        self.db = DatabaseManager()
        self.time_checker = TradingTimeChecker()
    
    def update_stock_prices_loop(self):
        """股价更新主循环"""
        logger.info("🚀 StockFocus 后端服务已启动")
        
        while True:
            try:
                # 检查交易时间
                if not self.time_checker.is_trading_time():
                    logger.info("🕒 非交易时段，进入节能模式（5分钟检查一次）")
                    time.sleep(300)  # 5分钟
                    continue
                
                # 获取需要监控的股票
                stocks_df = self.db.get_monitored_stocks()
                
                if stocks_df.empty:
                    logger.warning("数据库为空，暂无监控任务。休眠 60秒...")
                    time.sleep(60)
                    continue
                
                symbols = stocks_df['symbol'].tolist()
                fair_price_map = dict(zip(stocks_df['symbol'], stocks_df['fair_price']))
                
                # 分批处理，防止请求过大
                batch_size = config.BATCH_SIZE
                total_updated = 0
                
                for i in range(0, len(symbols), batch_size):
                    batch_symbols = symbols[i:i+batch_size]
                    
                    # 获取实时数据
                    realtime_data = self.api.fetch_realtime_batch(batch_symbols)
                    
                    if realtime_data:
                        # 更新数据库
                        updated_count = self.db.update_stock_prices(
                            realtime_data, 
                            fair_price_map
                        )
                        total_updated += updated_count
                    
                    # 礼貌性延迟，避免过于频繁请求
                    time.sleep(0.5)
                
                logger.info(f"💤 本轮更新完成，共更新 {total_updated} 只股票，休眠 {config.REFRESH_INTERVAL}秒...")
                time.sleep(config.REFRESH_INTERVAL)
                
            except KeyboardInterrupt:
                logger.info("👋 服务被用户中断")
                break
            except Exception as e:
                logger.error(f"❌ 主循环异常: {e}")
                time.sleep(5)  # 异常后短暂休眠再重试
    
    def run_health_check(self):
        """运行健康检查"""
        try:
            # 测试数据库连接
            stocks_df = self.db.get_monitored_stocks()
            db_status = "正常" if not stocks_df.empty else "空数据"
            
            # 测试API连接
            test_data = self.api.fetch_realtime_batch(['600519'])  # 测试茅台
            api_status = "正常" if test_data else "异常"
            
            logger.info(f"📊 健康检查 - 数据库: {db_status}, API: {api_status}")
            
        except Exception as e:
            logger.error(f"健康检查失败: {e}")

def main():
    """主函数"""
    logger.info("🎯 StockFocus 后端服务启动中...")
    
    service = StockDataService()
    
    # 运行一次健康检查
    service.run_health_check()
    
    # 进入主循环
    service.update_stock_prices_loop()

if __name__ == "__main__":
    main()