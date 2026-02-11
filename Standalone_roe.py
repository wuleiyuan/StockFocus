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
    print(f"🚀 启动全市场深度扫描 (ROE > {roe_threshold}%，连续 {years} 年)...")
    
    # --- 第一阶段：禁用代理获取股票列表 (国内直连最稳) ---
    os.environ["NO_PROXY"] = "*"
    os.environ.pop("HTTP_PROXY", None)
    os.environ.pop("HTTPS_PROXY", None)
    
    try:
        print("📥 正在同步全 A 股代码列表 (直连模式)...")
        stock_list = ak.stock_zh_a_spot_em()
        all_codes = stock_list['代码'].tolist()
        print(f"✅ 成功获取 {len(all_codes)} 只标的。")
    except Exception as e:
        print(f"❌ 获取列表失败: {e}")
        return

    # --- 第二阶段：逐个分析 ---
    for i, code in enumerate(all_codes):
        # 每隔 10 只标的清理一次网络环境，防止代理挂起
        if i % 10 == 0:
            os.environ["HTTP_PROXY"] = "http://127.0.0.1:7890"
            os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"

        try:
            # 抓取长周期财务指标
            df = ak.stock_financial_analysis_indicator(symbol=code)
            
            # 找到 ROE 列并过滤年报
            roe_col = [c for c in df.columns if '净资产收益率' in str(c) and '(%)' in str(c)][0]
            # 筛选 12-31 的年度数据
            annual_df = df[df.index.astype(str).str.contains("-12-31")]
            
            if len(annual_df) < years: continue
            
            # 提取最近 10 年数据并转换
            roe_history = annual_df[roe_col].iloc[:years].apply(clean_num)
            
            # 【神级筛选】：所有年份均大于阈值
            if all(roe_history >= roe_threshold):
                avg_roe = float(round(roe_history.mean(), 2))
                print(f"🌟 [命中] {code} | 10年均 ROE: {avg_roe}%")
                
                # 写入数据库，标记为“顶级核心资产”
                os.environ.pop("HTTP_PROXY", None) # 写入数据库时关掉代理
                with engine.begin() as conn:
                    conn.execute(text("""
                        INSERT INTO market_scan_results (symbol, roe_5y, industry) 
                        VALUES (:s, :r, '顶级核心资产') 
                        ON CONFLICT (symbol) DO UPDATE SET roe_5y=:r, industry='顶级核心资产'
                    """), {"s": code, "r": avg_roe})
            
            if i % 50 == 0:
                print(f"⏳ 扫描进度: {i}/{len(all_codes)}...")

        except Exception:
            continue
        
        time.sleep(0.2) # 规避频率限制

if __name__ == "__main__":
    find_super_stocks(roe_threshold=15.0, years=10)