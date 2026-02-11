import pandas as pd
import akshare as ak
from sqlalchemy import create_engine, text
import os
import time
import requests

# 1. 数据库配置
DB_URL = "postgresql+psycopg2://admin:password123@127.0.0.1:5432/stock_data?sslmode=disable&gssencmode=disable"
engine = create_engine(DB_URL)

def clean_num(val):
    s = str(val).replace('%', '').strip()
    if s in ['False', 'None', '--', '', 'nan', 'NaN']: return 0.0
    try: return float(s)
    except: return 0.0

def find_super_stocks(roe_threshold=10.0, years=10):
    print(f"🚀 启动【暴力穿透版】深度扫描 (ROE > {roe_threshold}%)...")
    
    # 强制清理环境，确保初始状态干净
    for key in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
        os.environ.pop(key, None)

    # 策略：如果全量列表拉不动，我们直接从数据库里现有的 symbol 或者是核心宽基指数里拿代码
    try:
        print("📥 正在通过‘沪深京A股’稳定接口获取代码...")
        # 换一个更稳定的代码获取接口
        stock_list = ak.stock_info_a_code_name()
        all_codes = stock_list['code'].tolist()
        print(f"✅ 成功获取 {len(all_codes)} 只代码种子。")
    except Exception as e:
        print(f"⚠️ 列表接口依旧受限，启动备选方案：扫描你自选池中的历史数据...")
        with engine.connect() as conn:
            res = conn.execute(text("SELECT symbol FROM market_scan_results"))
            all_codes = [r[0] for r in res]

    for i, code in enumerate(all_codes):
        # 每次循环都强制确保网络逻辑：抓取数据时开启代理（针对新浪/同花顺），写入数据库时关闭
        os.environ["HTTP_PROXY"] = "http://127.0.0.1:7890"
        os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"

        try:
            # 抓取长周期财务指标 (这个接口通常比实时行情稳)
            df = ak.stock_financial_analysis_indicator(symbol=code)
            
            # 定位 ROE 列并过滤年报
            roe_col = [c for c in df.columns if '净资产收益率' in str(c) and '(%)' in str(c)][0]
            annual_df = df[df.index.astype(str).str.contains("-12-31")]
            
            if len(annual_df) < years: continue
            
            # 提取最近 10 年数据
            roe_history = annual_df[roe_col].iloc[:years].apply(clean_num)
            
            # 核心判断：每一年的 ROE 都在线
            if all(roe_history >= roe_threshold):
                avg_roe = float(round(roe_history.mean(), 2))
                print(f"🌟 [命中神级资产] {code} | 10年均 ROE: {avg_roe}%")
                
                # 写入数据库，标记为“顶级核心资产”
                os.environ.pop("HTTP_PROXY", None)
                os.environ.pop("HTTPS_PROXY", None)
                with engine.begin() as conn:
                    conn.execute(text("""
                        INSERT INTO market_scan_results (symbol, roe_5y, industry) 
                        VALUES (:s, :r, '顶级核心资产') 
                        ON CONFLICT (symbol) DO UPDATE SET roe_5y=:r, industry='顶级核心资产'
                    """), {"s": code, "r": avg_roe})
            
            if i % 20 == 0:
                print(f"⏳ 已扫描 {i}/{len(all_codes)} 只标的...")

        except Exception:
            continue
        
        time.sleep(0.5) # 增加延迟，防止被封 IP

if __name__ == "__main__":
    find_super_stocks(roe_threshold=10.0, years=10)