import time
from datetime import datetime
import logging

def is_trade_time():
    """判断当前是否为 A 股交易时段""" [cite: 1]
    now = datetime.now()
    if now.weekday() >= 5: return False # 周末不运行
    
    current_time = now.strftime("%H:%M")
    # 9:15-11:35 (含开盘集合竞价), 13:00-15:05
    return ("09:15" <= current_time <= "11:35") or ("13:00" <= current_time <= "15:05")

def run_etl_loop():
    while True:
        try:
            if not is_trade_time():
                logging.info("🕒 非交易时段，进入节能模式（5分钟检查一次）")
                time.sleep(300)
                continue
            
            # --- 执行原有的抓取和数据库写入逻辑 --- 
            logging.info("🚀 交易时间内，正在同步行情...")
            # (fetch_realtime_batch 内容)
            
            time.sleep(10) # 交易时段每 10 秒刷新一次
        except Exception as e:
            logging.error(f"ETL 运行异常: {e}")
            time.sleep(5)