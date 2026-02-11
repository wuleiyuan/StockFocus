from sqlalchemy import create_engine, text
import os

# 强制直连
os.environ["NO_PROXY"] = "*"

# 数据库连接 (使用默认密码)
DB_URL = "postgresql+psycopg2://admin:password123@127.0.0.1:5432/stock_data?sslmode=disable&gssencmode=disable"
engine = create_engine(DB_URL)

def init_db():
    with engine.begin() as conn:
        # 1. 确保主表存在
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS market_scan_results (
                symbol TEXT PRIMARY KEY,
                name TEXT,
                current_price FLOAT,
                fair_price FLOAT,
                bias FLOAT,
                roe_5y FLOAT,
                industry TEXT,
                mkt_cap FLOAT,
                ai_cache TEXT,
                ai_date TIMESTAMP
            );
        """))
        
        # 2. 创建历史记录表 (TimescaleDB 风格)
        # 记录：代码、时间、价格、偏差率、市盈率(PE)
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS stock_history (
                symbol TEXT,
                record_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                price FLOAT,
                bias FLOAT,
                pe_ttm FLOAT,
                PRIMARY KEY (symbol, record_time)
            );
        """))
        print("✅ 数据库表结构升级完成：已新增 stock_history 表。")

if __name__ == "__main__":
    init_db()