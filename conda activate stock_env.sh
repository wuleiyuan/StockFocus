import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import akshare as ak
import os
import warnings
import time
import plotly.express as px
from datetime import datetime, timedelta

# --- 铁律 1: 物理隔离 (必须在最前执行) ---
for k in list(os.environ.keys()):
    if "proxy" in k.lower(): os.environ.pop(k, None)
os.environ["NO_PROXY"] = "127.0.0.1,localhost,0.0.0.0"

# --- 1. AI 引擎核心 ---
try:
    from google import genai
    SDK_VERSION = "NEW"
except ImportError:
    import google.generativeai as genai
    SDK_VERSION = "OLD"

warnings.filterwarnings('ignore')
PROXY_HTTP = "http://127.0.0.1:7892"
API_KEYS = ["AIzaSyCkZ_wy8mHH3puLji5CkUUu6pEvwbyE8sE", "AIzaSyDIOXsDH0GJNqW37WEPwRfu8wxwmTQY2C4"]

def get_ai_response(prompt):
    """AI 调用时通过代理访问外网"""
    old_env = {k: os.environ.get(k) for k in ["http_proxy", "https_proxy", "all_proxy"]}
    try:
        os.environ["http_proxy"] = PROXY_HTTP
        os.environ["https_proxy"] = PROXY_HTTP
        for i, key in enumerate(API_KEYS):
            try:
                if SDK_VERSION == "NEW":
                    client = genai.Client(api_key=key)
                    res = client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
                    return res.text, f"Key_{i+1}"
                else:
                    genai.configure(api_key=key)
                    model = genai.GenerativeModel('gemini-2.0-flash')
                    res = model.generate_content(prompt)
                    return res.text, f"Key_{i+1}"
            except: continue
        return "⚠️ AI 分析异常", None
    finally:
        for k in ["http_proxy", "https_proxy", "all_proxy"]: os.environ.pop(k, None)

# --- 2. 数据库引擎 (解决 RemoteDisconnected 的核心配置) ---
def get_engine():
    # 彻底禁用 SSL 和 GSSAPI 握手，这是防止被代理拦截的必杀技
    # 同时使用极短的连接时间，一旦阻塞立即重连
    db_url = "postgresql+psycopg2://admin:password123@127.0.0.1:5432/stock_data?sslmode=disable&gssencmode=disable"
    return create_engine(
        db_url, 
        pool_pre_ping=True, 
        pool_recycle=30, # 频繁重置池子，对付不稳定的劫持环境
        connect_args={"connect_timeout": 5}
    )

def force_init_db():
    """初始化逻辑：建表+补全字段+同步核心票"""
    try:
        engine = get_engine()
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS market_scan_results (
                    symbol TEXT PRIMARY KEY, name TEXT, industry TEXT DEFAULT '未分类',
                    current_price FLOAT, fair_price FLOAT DEFAULT 0, bias FLOAT DEFAULT 0,
                    ai_cache TEXT, ai_date TIMESTAMP, scan_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )"""))
            # 自愈逻辑：补全字段
            for col in [("industry", "TEXT"), ("ai_cache", "TEXT"), ("ai_date", "TIMESTAMP")]:
                try: conn.execute(text(f"ALTER TABLE market_scan_results ADD COLUMN {col[0]} {col[1]}"))
                except: pass
        
        # 实时同步价格 (确保看板有数)
        df_spot = ak.stock_zh_a_spot_em()
        with engine.begin() as conn:
            for a in [{"s":"000858", "n":"五粮液", "i":"白酒"}, {"s":"600519", "n":"贵州茅台", "i":"白酒"}, {"s":"603288", "n":"海天味业", "i":"调味品"}]:
                row = df_spot[df_spot['代码'] == a['s']]
                if not row.empty:
                    p = float(row.iloc[0]['最新价'])
                    conn.execute(text("""
                        INSERT INTO market_scan_results (symbol, name, industry, current_price, scan_date)
                        VALUES (:s, :n, :i, :p, CURRENT_TIMESTAMP)
                        ON CONFLICT (symbol) DO UPDATE SET current_price = EXCLUDED.current_price
                    """), {"s": a['s'], "n": a['n'], "i": a['i'], "p": p})
        return True
    except Exception as e:
        st.error(f"❌ 内核级自愈失败: {e}")
        return False

# --- 3. UI 界面逻辑 (全量回归) ---
st.set_page_config(page_title="StockFocus Pro", layout="wide", page_icon="🦅")
st.title("🦅 StockFocus 决策终端")

with st.sidebar:
    st.header("⚙️ 系统管理")
    category = st.selectbox("分池切换", ["自选核心", "高优排雷", "行业观察"])
    if 'watchlist' not in st.session_state:
        st.session_state.watchlist = {"自选核心": ["000858", "600519", "603288"], "高优排雷": [], "行业观察": []}
    
    st.markdown("---")
    if st.button("🚀 暴力物理穿透连接"):
        if force_init_db(): st.success("🎉 连接已彻底穿透！"); st.rerun()
    
    st.download_button("📑 导出操作指南", data="1.AI 24h缓存\n2.手动资产录入\n3.偏离度自动打标", file_name="guide.txt")

tab1, tab2, tab3, tab4 = st.tabs(["📊 实时看板", "🛡️ AI 审计", "🗺️ 热力图", "📑 清单维护"])

with tab1:
    st.subheader(f"📡 {category} 监控中心")
    try:
        codes = st.session_state.watchlist[category]
        if codes:
            c_str = f"('{codes[0]}')" if len(codes) == 1 else str(tuple(codes))
            df = pd.read_sql(f"SELECT * FROM market_scan_results WHERE symbol IN {c_str}", get_engine())
            if not df.empty:
                df['状态'] = df['bias'].apply(lambda x: "🟢 黄金坑" if x and x < 0 else "⚪ 正常")
                st.dataframe(df.style.background_gradient(subset=['bias'], cmap='RdYlGn_r'), use_container_width=True, hide_index=True)
    except: st.info("请先尝试侧边栏修复。")

with tab2:
    st.subheader("🤖 AI 穿透审计 (24h 缓存逻辑)")
    t_code = st.text_input("股票代码", value="603288")
    if st.button("启动排雷分析"):
        engine = get_engine()
        # 缓存逻辑找回：检查 ai_date
        cache = pd.read_sql(text("SELECT ai_cache, ai_date FROM market_scan_results WHERE symbol=:s"), engine, params={"s":t_code})
        if not cache.empty and cache.iloc[0]['ai_date'] and cache.iloc[0]['ai_date'] > datetime.now() - timedelta(days=1):
            st.info("📌 调取 24h 内缓存数据：")
            st.markdown(cache.iloc[0]['ai_cache'])
        else:
            with st.spinner("AI 正在穿透审计..."):
                res, k = get_ai_response(f"深度分析股票 {t_code}")
                if k:
                    st.markdown(res)
                    with engine.begin() as conn:
                        conn.execute(text("UPDATE market_scan_results SET ai_cache=:c, ai_date=CURRENT_TIMESTAMP WHERE symbol=:s"), {"c":res, "s":t_code})

with tab4:
    st.subheader("📑 资产维护与手动录入")
    with st.expander("➕ 手动新增/编辑资产"):
        c1, c2, c3 = st.columns(3)
        s_in = c1.text_input("代码")
        n_in = c2.text_input("名称")
        f_in = c3.number_input("合理价", value=0.0)
        p_in = st.selectbox("分配池", ["自选核心", "高优排雷", "行业观察"])
        if st.button("💾 确认入库并加入分池"):
            if s_in and n_in:
                with get_engine().begin() as conn:
                    conn.execute(text("INSERT INTO market_scan_results (symbol,name,fair_price) VALUES (:s,:n,:f) ON CONFLICT (symbol) DO UPDATE SET fair_price=EXCLUDED.fair_price"), {"s":s_in,"n":n_in,"f":f_in})
                if s_in not in st.session_state.watchlist[p_in]: st.session_state.watchlist[p_in].append(s_in)
                st.success("入库成功！"); st.rerun()
    
    try:
        df_list = pd.read_sql("SELECT * FROM market_scan_results ORDER BY symbol ASC", get_engine())
        st.data_editor(df_list, use_container_width=True, hide_index=True)
    except: pass