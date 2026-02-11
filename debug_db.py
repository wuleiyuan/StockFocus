import pandas as pd
from sqlalchemy import create_engine, text
import os

# 1. 物理层强连配置 (强制关闭所有干扰)
DB_URL = "postgresql+psycopg2://admin:password123@127.0.0.1:5432/stock_data?sslmode=disable&gssencmode=disable"
engine = create_engine(DB_URL, connect_args={'connect_timeout': 5})

def check_system():
    print("🔍 开始系统体检...")
    
    # 环境检查：是否有代理干扰
    for key in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
        if key in os.environ:
            print(f"⚠️ 警告：检测到环境变量 {key}={os.environ[key]}，可能会拦截本地数据库连接！")

    try:
        with engine.connect() as conn:
            print("✅ 数据库物理连接：通畅")
            
            # A. 检查表是否存在
            res = conn.execute(text("SELECT COUNT(*) FROM market_scan_results")).fetchone()
            count = res[0]
            print(f"📊 数据库当前总行数：{count}")
            
            if count == 0:
                print("❌ 结果：数据库是空的，之前的强灌脚本未成功运行。")
                print("🪄 正在尝试强制写入一条测试数据 (贵州茅台) 以激活界面...")
                conn.execute(text("""
                    INSERT INTO market_scan_results (symbol, name, roe_5y, fair_price, industry, current_price) 
                    VALUES ('600519', '贵州茅台', 28.5, 1850.5, '白酒', 1600.0)
                    ON CONFLICT (symbol) DO NOTHING
                """))
                conn.commit()
                print("✅ 测试数据已灌入！请刷新 Web 页面查看。")
            else:
                # B. 检查数据质量
                null_data = conn.execute(text("SELECT COUNT(*) FROM market_scan_results WHERE roe_5y = 0")).fetchone()[0]
                print(f"⚠️ 质量检查：有 {null_data} 条数据的 ROE 为 0 (说明财务底座没建立成功)")

    except Exception as e:
        print(f"❌ 数据库连接失败！原因：{e}")
        print("💡 建议：检查 Docker 是否运行，或 Clash 是否拦截了 127.0.0.1")

if __name__ == "__main__":
    check_system()