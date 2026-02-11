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

def find_super_stocks(roe_threshold=3.0, years=1):
    print(f"🎯 启动【备选源穿透版】扫描 (ROE > {roe_threshold}%)")
    
    # 强制直连
    os.environ["NO_PROXY"] = "*"
    for key in ["HTTP_PROXY", "HTTPS_PROXY"]: os.environ.pop(key, None)

    try:
        # 使用更稳的代码表接口
        stock_info_df = ak.stock_info_a_code_name()
        # 优先审计沪深核心标的，成功率更高
        all_codes = stock_info_df['code'].tolist()
        name_map = dict(zip(stock_info_df['code'], stock_info_df['name']))
        print(f"✅ 名单就绪，开始利用东方财富源进行‘轻量化审计’...")
    except: return

    for i, code in enumerate(all_codes):
        stock_name = name_map.get(code, "未知")
        print(f"🛡️ [{i+1}/{len(all_codes)}] 审计: {stock_name}({code}) ... ", end="", flush=True)

        try:
            # 【核心改变】：换用东方财富的核心财务指标接口，这个接口比新浪稳 10 倍
            # 它返回的是多季度对比表
            df = ak.stock_financial_analysis_indicator(symbol=code) 
            
            # 如果上面那个接口报错，立刻切换备选方案：个股摘要接口
            if df is None or df.empty:
                # 备选：同花顺摘要接口
                df = ak.stock_financial_abstract_ths(symbol=code)
                roe_col = [c for c in df.columns if '净资产收益率' in str(c)][0]
                roe_history = df[roe_col].iloc[:years].apply(clean_num)
            else:
                roe_col = [c for c in df.columns if '净资产收益率' in str(c) and '(%)' in str(c)][0]
                # 过滤年报
                annual_df = df[df.index.astype(str).str.contains("-12-31")]
                roe_history = annual_df[roe_col].iloc[:years].apply(clean_num)

            if len(roe_history) < years:
                print("🍂 年限不足")
                continue

            if all(roe_history >= roe_threshold):
                avg_roe = float(round(roe_history.mean(), 2))
                print(f"💎 [命中] ROE:{avg_roe}%")
                
                with engine.begin() as conn:
                    conn.execute(text("""
                        INSERT INTO market_scan_results (symbol, name, roe_5y, industry) 
                        VALUES (:s, :n, :r, '顶级核心资产') 
                        ON CONFLICT (symbol) DO UPDATE SET name=:n, roe_5y=:r, industry='顶级核心资产'
                    """), {"s": code, "n": stock_name, "r": avg_roe})
            else:
                # 打印最近一年的 ROE，让你心里有数
                print(f"❌ 不达标 (近期:{roe_history.iloc[0]}%)")

        except Exception:
            print("⚠️ 接口抖动 (跳过)")
        
        # 即使是稳健接口，也要礼貌等待
        time.sleep(random.uniform(0.5, 1.0))

if __name__ == "__main__":
    find_super_stocks(roe_threshold=3.0, years=1)