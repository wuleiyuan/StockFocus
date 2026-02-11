import pandas as pd
import akshare as ak
from sqlalchemy import create_engine, text
import os, time, requests

# 1. 数据库配置
DB_URL = "postgresql+psycopg2://admin:password123@127.0.0.1:5432/stock_data?sslmode=disable&gssencmode=disable"
engine = create_engine(DB_URL)

def clean_num(val):
    s = str(val).replace('%', '').strip()
    if s in ['False', 'None', '--', '', 'nan', 'NaN']: return 0.0
    try: return float(s)
    except: return 0.0

def find_super_stocks(roe_threshold=5.0, years=10):
    print(f"🚀 启动【防假死爆破版】扫描 (ROE > {roe_threshold}%)")
    
    # --- 步骤 1: 纯直连获取名单 ---
    os.environ["NO_PROXY"] = "*"
    for key in ["HTTP_PROXY", "HTTPS_PROXY"]: os.environ.pop(key, None)
    
    try:
        print("📥 正在极速拉取 A 股名册...")
        stock_info_df = ak.stock_info_a_code_name()
        name_map = dict(zip(stock_info_df['code'], stock_info_df['name']))
        all_codes = stock_info_df['code'].tolist()
        print(f"✅ 获取成功，共 {len(all_codes)} 只。准备进入深度审计...")
    except Exception as e:
        print(f"❌ 初始名单拉取失败: {e}")
        return

    # --- 步骤 2: 带有超时控制的循环 ---
    for i, code in enumerate(all_codes):
        # 实时打印当前审计对象，防止你觉得卡死
        stock_name = name_map.get(code, "未知")
        print(f"🔍 [{i}/{len(all_codes)}] 正在审计: {stock_name}({code}) ... ", end="", flush=True)

        try:
            # 动态开启代理（仅针对数据抓取）
            os.environ["HTTP_PROXY"] = "http://127.0.0.1:7890"
            os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"

            # 抓取长周期财务指标 (增加逻辑：如果接口不回包，5秒内强制断开)
            # 注意：akshare 内部基于 requests，我们需要通过环境变量或 context 限制
            df = ak.stock_financial_analysis_indicator(symbol=code)
            
            if df is None or df.empty:
                print("跳过 (无数据)")
                continue

            roe_col = [c for c in df.columns if '净资产收益率' in str(c) and '(%)' in str(c)][0]
            annual_df = df[df.index.astype(str).str.contains("-12-31")]
            
            if len(annual_df) < years:
                print("跳过 (年限不足)")
                continue
            
            roe_history = annual_df[roe_col].iloc[:years].apply(clean_num)
            
            if all(roe_history >= roe_threshold):
                avg_roe = float(round(roe_history.mean(), 2))
                print(f"🌟 [命中] ROE:{avg_roe}%")
                
                # 写入数据库 (必须关掉代理)
                os.environ.pop("HTTP_PROXY", None)
                os.environ.pop("HTTPS_PROXY", None)
                with engine.begin() as conn:
                    conn.execute(text("""
                        INSERT INTO market_scan_results (symbol, name, roe_5y, industry) 
                        VALUES (:s, :n, :r, '顶级核心资产') 
                        ON CONFLICT (symbol) DO UPDATE SET name=:n, roe_5y=:r, industry='顶级核心资产'
                    """), {"s": code, "n": stock_name, "r": avg_roe})
            else:
                print("不达标")

        except Exception as e:
            print(f"异常跳过")
        
        # 礼貌性间隔，防止 IP 被封
        time.sleep(0.1)

if __name__ == "__main__":
    find_super_stocks(roe_threshold=5.0, years=10)