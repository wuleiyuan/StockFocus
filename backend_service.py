import time
import requests
import json
import os
import logging
from sqlalchemy import create_engine, text
import pandas as pd
from datetime import datetime

# ================= 配置层 =================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [BACKEND] - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 强制本地直连，确保数据库和国内 API 畅通
for k in list(os.environ.keys()):
    if "proxy" in k.lower(): os.environ.pop(k, None)
os.environ["NO_PROXY"] = "*"

# 数据库连接
def get_engine():
    # 建议使用 secrets.toml，这里为演示方便使用硬编码兜底
    url = "postgresql+psycopg2://admin:password123@127.0.0.1:5432/stock_data?sslmode=disable&gssencmode=disable"
    return create_engine(url, pool_pre_ping=True)

engine = get_engine()

# ================= 核心功能 =================

def fetch_realtime_batch(symbols):
    """
    批量获取行情 (东方财富接口支持多只一起查，极大提升效率)
    """
    if not symbols: return {}
    
    # 东方财富批量接口格式: secid=1.600519,0.000858...
    # 沪市(6/9开头)=1, 深市(0/3开头)=0
    secids = []
    for s in symbols:
        prefix = "1" if s.startswith(("6", "9")) else "0"
        secids.append(f"{prefix}.{s}")
    
    secids_str = ",".join(secids)
    url = f"http://push2.eastmoney.com/api/qt/ulist.np/get?secids={secids_str}&fields=f12,f14,f2,f20,f100"
    
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json().get("data", {}).get("diff", [])
            # 格式化返回: {code: {price, name, mkt_cap, industry}}
            results = {}
            for item in data:
                results[item["f12"]] = {
                    "p": item["f2"]/100 if item["f2"] != "-" else 0, # f2是分，转元
                    "n": item["f14"],
                    "m": item["f20"],
                    "i": item["f100"]
                }
            return results
    except Exception as e:
        logger.error(f"批量行情获取失败: {e}")
    return {}

def update_loop():
    """主循环：不断刷新数据库中的资产状态"""
    logger.info("🚀 后端服务已启动，开始守护数据...")
    
    while True:
        try:
            # 1. 从数据库捞出所有需要监控的股票代码
            with engine.connect() as conn:
                # 无论是自动扫描的还是手动录入的，全都要更新
                codes = pd.read_sql("SELECT symbol, fair_price FROM market_scan_results", conn)
            
            if codes.empty:
                logger.warning("数据库为空，暂无任务。休眠 60秒...")
                time.sleep(60)
                continue

            symbols = codes['symbol'].tolist()
            fair_map = dict(zip(codes['symbol'], codes['fair_price']))
            
            # 2. 分批次抓取 (每批 50 只，防止 URL 过长)
            batch_size = 50
            for i in range(0, len(symbols), batch_size):
                batch = symbols[i:i+batch_size]
                realtime_data = fetch_realtime_batch(batch)
                
                if realtime_data:
                    # 3. 写入数据库
                    with engine.begin() as conn:
                        for code, data in realtime_data.items():
                            fair = fair_map.get(code, 0)
                            bias = (data['p'] - fair) / fair * 100 if fair > 0 else 0
                            
                            # 执行更新
                            conn.execute(
                                text("""
                                    UPDATE market_scan_results 
                                    SET current_price=:p, mkt_cap=:m, name=:n, industry=:i, bias=:b 
                                    WHERE symbol=:s
                                """),
                                {"p": data['p'], "m": data['m'], "n": data['n'], "i": data['i'], "b": bias, "s": code}
                            )
                    logger.info(f"✅ 已同步 {len(realtime_data)} 只股票行情")
                
                time.sleep(0.5) # 礼貌请求，防止封 IP

            logger.info("💤 本轮更新完毕，休眠 10秒...")
            time.sleep(10) # 10秒刷新一次，既实时又不暴力

        except Exception as e:
            logger.error(f"主循环异常: {e}")
            time.sleep(5)

if __name__ == "__main__":
    update_loop()