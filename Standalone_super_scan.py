import pandas as pd
import akshare as ak
from sqlalchemy import create_engine, text
import os, time, random

# 1. 数据库配置
DB_URL = "postgresql+psycopg2://admin:password123@127.0.0.1:5432/stock_data?sslmode=disable&gssencmode=disable"
engine = create_engine(DB_URL)

def clean_num(val):
    s = str(val).replace('%', '').strip()
    if s in ['False', 'None', '--', '', 'nan', 'NaN']: return 0.0
    try: return float(s)
    except: return 0.0

def find_super_stocks(roe_threshold=5.0, years=10):
    print(f"🕵️ 启动【特种渗透版】扫描 (目标：连续 {years} 年 ROE > {roe_threshold}%)")
    
    # 强制直连获取核心名单 (沪深300)
    os.environ["NO_PROXY"] = "*"
    try:
        print("📥 正在拉取【沪深300】核心名册进行精准审计...")
        hs300_df = ak.stock_zh_a_hist_names_em() # 备选更稳的接口
        # 为了提高成功率，我们先从前 300 只大蓝筹开始扫
        all_codes = hs300_df['代码'].head(500).tolist()
        name_map = dict(zip(hs300_df['代码'], hs300_df['名称']))
        print(f"✅ 核心池锁定 {len(all_codes)} 只标的。")
    except:
        all_codes = ["600519", "000858", "603288", "600036", "601318", "002594", "000333", "600276"]
        name_map = {"600519":"贵州茅台", "000858":"五粮液", "603288":"海天味业"}

    for i, code in enumerate(all_codes):
        stock_name = name_map.get(code, code)
        print(f"🔎 [{i+1}/{len(all_codes)}] 审计: {stock_name} ... ", end="", flush=True)

        try:
            # 彻底关闭代理，国内财务数据直连最稳
            for key in ["HTTP_PROXY", "HTTPS_PROXY"]: os.environ.pop(key, None)
            
            # 抓取财务指标
            df = ak.stock_financial_analysis_indicator(symbol=code)
            
            if df is None or df.empty:
                print("⏳ 接口无响应 (跳过)")
                time.sleep(2) # 被限频了，多歇会儿
                continue

            # 提取年报 ROE
            roe_col = [c for c in df.columns if '净资产收益率' in str(c) and '(%)' in str(c)][0]
            annual_df = df[df.index.astype(str).str.contains("-12-31")]
            
            if len(annual_df) < years:
                print("🍂 年限不足")
                continue
            
            roe_history = annual_df[roe_col].iloc[:years].apply(clean_num)
            
            # 判断神级资产
            if all(roe_history >= roe_threshold):
                avg_roe = float(round(roe_history.mean(), 2))
                print(f"💎 [发现神级资产] ROE:{avg_roe}%")
                
                with engine.begin() as conn:
                    conn.execute(text("""
                        INSERT INTO market_scan_results (symbol, name, roe_5y, industry) 
                        VALUES (:s, :n, :r, '顶级核心资产') 
                        ON CONFLICT (symbol) DO UPDATE SET name=:n, roe_5y=:r, industry='顶级核心资产'
                    """), {"s": code, "n": stock_name, "r": avg_roe})
            else:
                print("❌ 不达标")

        except Exception as e:
            print(f"⚠️ 异常 (通常是频率限制)")
        
        # 核心：随机睡眠 1-2 秒，防止被封 IP
        time.sleep(random.uniform(1.2, 2.5))

if __name__ == "__main__":
    find_super_stocks(roe_threshold=5.0, years=10)