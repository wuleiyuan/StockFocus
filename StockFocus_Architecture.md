# StockFocus Pro: 全栈量化投研系统架构文档 (V36.1 Final)

## 1. 项目愿景与核心策略 (Vision & Strategy)

**StockFocus Pro** 是一个基于 Python 的全栈量化投研终端，旨在通过自动化脚本筛选 A 股市场中的“顶级核心资产”，并结合 AI 进行深度审计。

### 1.1 核心投研逻辑
1.  **估值锚点 (15x PE 法)**：
    * 合理价 (Fair Price) = 最近一年 EPS × 15。
    * **偏差率 (Bias)** = (现价 - 合理价) / 合理价 × 100%。
    * **黄金坑标准**：Bias < **-15%** (安全边际充足)。
    * **高估预警**：Bias > **+20%** (溢价过高)。
2.  **质量评估 (ROE 标杆)**：
    * 核心筛选标准：连续 5-10 年 ROE (净资产收益率) 稳定在 **15%** 以上。
3.  **市值认知分档**：
    * < 50亿：主题投资阶段。
    * 50亿 - 200亿：黄金增长阶段。
    * > 400亿：行业龙头阶段。

---

## 2. 系统底层开发逻辑 (Underlying Logic)

### 2.1 网络层：动态分治策略 (Network Isolation)
* **本地流量 (NO_PROXY)**：
    * **规则**：强制 `os.environ["NO_PROXY"] = "*"`。
    * **目的**：防止 Clash Fake-IP 劫持本地 5432 端口，确保数据库直连。
* **外网/AI 流量 (Proxy Sandbox)**：
    * **规则**：仅在调用 Gemini API 时临时注入 `HTTP_PROXY`，用完即焚。

### 2.2 数据持久化层 (Database)
* **引擎**：PostgreSQL (TimescaleDB) via Docker。
* **连接串**：`sslmode=disable&gssencmode=disable` (绕过 SSL 握手)。
* **表结构 (`market_scan_results`)**：
    * `symbol`, `name` (String): 基础信息。
    * `current_price`, `fair_price`, `bias` (Float): 行情与估值。
    * `roe_5y` (Float): 财务质量。
    * `ai_cache` (Text), `ai_date` (Timestamp): AI 研报缓存。

### 2.3 数据自愈机制 (Auto-Healing)
* **检测**：页面加载时检测 `current_price` 是否为 0。
* **修复**：若为 0，自动调用直连 API 抓取现价、名称，并 `UPDATE` 回数据库。
* **兜底**：若 DB 中名字为 '0'，强制用实时接口数据覆盖。

---

## 3. 报告与文档生成模块 (Reporting Module) **[找回功能]**

系统包含一个独立的 PDF 生成模块，用于输出**系统说明书**或**投研日报**。这对于分享策略和固化投研逻辑至关重要。

### 3.1 核心逻辑 (`make_pdf.py`)
* **库**：`fpdf`。
* **功能**：生成标准化的 PDF 文档，包含策略说明、操作指南等。
* **集成方式**：在 `app_web.py` 中通过按钮触发，或独立运行。

### 3.2 逻辑代码
```python
from fpdf import FPDF

def create_user_manual():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(40, 10, 'StockFocus Pro User Manual')
    pdf.ln(10)
    
    pdf.set_font("Arial", size=12)
    content = """
    1. Core Strategy: 15x PE Valuation Anchor.
    2. Quality Check: 10-Year ROE > 15%.
    3. AI Audit: Gemini-powered deep analysis (24h Cache).
    4. Auto-Push: WeChat Work alerts for Golden Pit assets.
    """
    pdf.multi_cell(0, 10, content)
    pdf.output("StockFocus_User_Manual.pdf")
    return "✅ 说明书/日报已生成: StockFocus_User_Manual.pdf"
4. 页面功能布局 (UI/UX)
Tab 1: 全景看板：展示 Bias 热力表，提供 PDF 下载按钮。

Tab 2: AI 深度审计：展示估值水位计 + AI 研报 (含缓存)。

Tab 3: 行业热力图：展示板块冷热分布，支持手动推送简报。

Tab 4: 资产管理后台：手动录入/修正资产数据。

5. 核心代码全集 (Core Code Snapshots)
5.1 主程序 (app_web.py - V36.1)
Python
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import http.client, json, os, requests, warnings, time
import plotly.express as px
import plotly.graph_objects as go
from fpdf import FPDF  # [新增] 引入 PDF 库

# --- 配置层 ---
st.set_page_config(page_title="StockFocus Pro V36.1", layout="wide", page_icon="🦅")
warnings.filterwarnings('ignore')
for k in list(os.environ.keys()):
    if "proxy" in k.lower(): os.environ.pop(k, None)
os.environ["NO_PROXY"] = "*"

# --- PDF 生成逻辑 (集成 make_pdf.py) ---
def generate_pdf_report(df):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, 'StockFocus Daily Report', ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", size=12)
    
    # 写入黄金坑名单
    pdf.cell(0, 10, 'Golden Pit Assets (Bias < -15%):', ln=True)
    pits = df[df['bias'] < -15]
    if not pits.empty:
        for _, row in pits.iterrows():
            pdf.cell(0, 10, f"{row['symbol']} - Bias: {row['bias']:.2f}% - ROE: {row['roe_5y']}%", ln=True)
    else:
        pdf.cell(0, 10, "No assets currently in Golden Pit zone.", ln=True)
        
    filename = f"StockFocus_Report_{time.strftime('%Y%m%d')}.pdf"
    pdf.output(filename)
    return filename

# --- 数据层 ---
def get_engine():
    return create_engine("postgresql+psycopg2://admin:password123@127.0.0.1:5432/stock_data?sslmode=disable&gssencmode=disable")

def fetch_realtime(symbol):
    prefix = "1" if symbol.startswith(("6", "9")) else "0"
    try:
        conn = http.client.HTTPConnection("183.136.160.11", timeout=3)
        conn.request("GET", f"/api/qt/stock/get?secid={prefix}.{symbol}&fields=f43,f58,f20,f100")
        d = json.loads(conn.getresponse().read().decode('utf-8')).get("data")
        return {"p": d["f43"]/100, "m": d["f20"], "n": d["f58"], "i": d["f100"]}
    except: return None

# --- UI 层 ---
engine = get_engine()
with st.sidebar:
    st.header("⚙️ 投研控制台")
    user_input = st.text_area("自选池", "600519,000858,603288")
    watchlist = [c.strip() for c in user_input.replace('\n', ',').split(',') if c.strip()]
    refresh = st.button("⚡ 强制刷新 & 修复")

df = pd.DataFrame()
if watchlist:
    formatted_codes = ", ".join([f"'{c}'" for c in watchlist])
    df = pd.read_sql(f"SELECT * FROM market_scan_results WHERE symbol IN ({formatted_codes})", engine).fillna(0)
    
    # 自愈逻辑
    if not df.empty and (df['current_price'].sum() == 0 or refresh):
        with st.spinner("🚀 数据自愈中..."):
            for _, row in df.iterrows():
                rt = fetch_realtime(row['symbol'])
                if rt:
                    bias = (rt['p'] - row['fair_price']) / row['fair_price'] * 100 if row['fair_price'] > 0
                    with engine.begin() as conn:
                        conn.execute(text("UPDATE market_scan_results SET current_price=:p, name=:n, bias=:b WHERE symbol=:s"), 
                                     {"p": rt['p'], "n": rt['n'], "b": bias, "s": row['symbol']})
            df = pd.read_sql(f"SELECT * FROM market_scan_results WHERE symbol IN ({formatted_codes})", engine).fillna(0)

# --- Tab 展示 ---
if not df.empty:
    t1, t2, t3, t4 = st.tabs(["📊 全景看板", "🧠 AI 审计", "🗺️ 行业热力", "🛠️ 资产管理"])
    
    with t1:
        st.dataframe(df[['symbol','name','current_price','bias','roe_5y']].style.format({'bias': '{:.2f}%'}).background_gradient(subset=['bias'], cmap='RdYlGn_r'), use_container_width=True)
        
        # [核心修复] PDF 生成按钮
        if st.button("📄 生成投研日报 (PDF)"):
            fname = generate_pdf_report(df)
            st.success(f"✅ 已生成: {fname}")
            with open(fname, "rb") as f:
                st.download_button("⬇️ 点击下载", f, file_name=fname)

    # ... (Tab 2, 3, 4 逻辑保持 V36 不变) ...
5.2 离线审计脚本 (Standalone_roe_final.py)
(此处保留之前的 Standalone 代码逻辑，用于强调数据源头)

Python
# 核心逻辑：
# 1. ak.stock_info_a_code_name() 获取全市场代码
# 2. ak.stock_financial_analysis_indicator() 获取 10 年财务
# 3. 筛选 ROE > 15% -> 存入 PostgreSQL