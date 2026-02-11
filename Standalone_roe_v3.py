import pandas as pd
import akshare as ak
from sqlalchemy import create_engine, text
import os
import time

# 1. 数据库配置
DB_URL = "postgresql+psycopg2://admin:password123@127.0.0.1:5432/stock_data?sslmode=disable&gssencmode=disable"
engine = create_engine(DB_URL)

def clean_num(val):
    s = str(val).replace('%', '').strip()
    if s in ['False', 'None', '--', '', 'nan', 'NaN']: return 0.0
    try: return float(s)
    except: return 0.0

def find_super_stocks(roe_threshold=15.0, years=10):
    print(f"🚀 启动【中文补全版】深度扫描 (ROE > {roe_threshold}%)...")
    
    # 强制直连获取代码列表
    os.environ.pop("HTTP_PROXY", None)
    os.environ.pop("HTTPS_PROXY", None)

    try:
        # 获取最全的代码+名称表
        print("📥 正在同步 A 股代码及名称映射表...")
        stock_info_df = ak.stock_info_a_code_name()
        # 建立代码到名称的字典映射
        name_map = dict(zip(stock_info_df['code'], stock_info_df['name']))
        all_codes = stock_info_df['code'].tolist()
        print(f"✅ 成功获取 {len(all_codes)} 只代码，开始深度审计财务...")
    except Exception as e:
        print(f"❌ 获取列表失败: {e}")
        return

    for i, code in enumerate(all_codes):
        # 开启代理抓取财务数据
        os.environ["HTTP_PROXY"] = "http://127.0.0.1:7890"
        os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"

        try:
            # 抓取财务分析指标
            df = ak.stock_financial_analysis_indicator(symbol=code)
            roe_col = [c for c in df.columns if '净资产收益率' in str(c) and '(%)' in str(c)][0]
            annual_df = df[df.index.astype(str).str.contains("-12-31")]
            
            if len(annual_df) < years: continue
            
            # 提取 10 年 ROE
            roe_history = annual_df[roe_col].iloc[:years].apply(clean_num)
            
            # 每一年的 ROE 均达标
            if all(roe_history >= roe_threshold):
                avg_roe = float(round(roe_history.mean(), 2))
                stock_name = name_map.get(code, "未知公司")
                print(f"🌟 [命中] {stock_name} ({code}) | 10年均 ROE: {avg_roe}%")
                
                # 写入数据库 (存入 name 字段)
                os.environ.pop("HTTP_PROXY", None)
                os.environ.pop("HTTPS_PROXY", None)
                with engine.begin() as conn:
                    conn.execute(text("""
                        INSERT INTO market_scan_results (symbol, name, roe_5y, industry) 
                        VALUES (:s, :n, :r, '顶级核心资产') 
                        ON CONFLICT (symbol) DO UPDATE SET name=:n, roe_5y=:r, industry='顶级核心资产'
                    """), {"s": code, "n": stock_name, "r": avg_roe})
            
            if i % 20 == 0:
                print(f"⏳ 扫描进度: {i}/{len(all_codes)}...")

        except Exception:
            continue
        
        time.sleep(0.3)

if __name__ == "__main__":
    # 建议先跑 15% 门槛，这已经是 A 股最强的一批公司了
    find_super_stocks(roe_threshold=15.0, years=10)