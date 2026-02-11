import pandas as pd
import akshare as ak
from sqlalchemy import create_engine, text
import os
import time

# 1. 数据库配置
DB_URL = "postgresql+psycopg2://admin:password123@127.0.0.1:5432/stock_data?sslmode=disable&gssencmode=disable"
engine = create_engine(DB_URL)

def clean_val(val):
    """强力清洗函数：处理百分号、布尔字符和异常值"""
    s = str(val).replace('%', '').strip()
    if s in ['False', 'None', '--', '', 'nan', 'NaN']:
        return 0.0
    try:
        return float(s)
    except:
        return 0.0

def force_sync_targets(watchlist):
    print(f"🚀 启动【原生数据版】强灌，目标: {watchlist}")
    
    # 网络代理设置 (仅针对 AkShare)
    os.environ["HTTP_PROXY"] = "http://127.0.0.1:7890"
    os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"

    for code in watchlist:
        print(f"📡 正在获取 {code} ...", end="", flush=True)
        try:
            # 抓取数据
            df = ak.stock_financial_abstract_ths(symbol=code)
            
            # 定位列名
            roe_col = [c for c in df.columns if '净资产收益率' in c][0]
            eps_col = [c for c in df.columns if '每股收益' in c][0]
            
            # 清洗并计算 (确保最终结果是原生 float)
            # 【修复核心】：这里使用 float() 强制转换，杜绝 np.float64
            roe_5y = float(round(df[roe_col].apply(clean_val).iloc[:5].mean(), 2))
            latest_eps = float(clean_val(df[eps_col].iloc[0]))
            fair_price = float(round(latest_eps * 15, 2))
            
            # 写入数据库 (切断代理)
            os.environ.pop("HTTP_PROXY", None)
            os.environ.pop("HTTPS_PROXY", None)
            
            with engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO market_scan_results (symbol, roe_5y, fair_price) 
                    VALUES (:s, :r, :f) 
                    ON CONFLICT (symbol) DO UPDATE SET roe_5y=:r, fair_price=:f
                """), {"s": code, "r": roe_5y, "f": fair_price})
            
            print(f" ✅ 成功! (ROE: {roe_5y}%, 公允价: {fair_price})")
            
            # 恢复代理
            os.environ["HTTP_PROXY"] = "http://127.0.0.1:7890"
            os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"
            
        except Exception as e:
            print(f" ❌ 仍失败: {e}")
        
        time.sleep(1)

if __name__ == "__main__":
    my_watchlist = ["600519", "000858", "603288", "600036", "002594", "601318"]
    force_sync_targets(my_watchlist)