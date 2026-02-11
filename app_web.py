import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from fpdf import FPDF
import os

# --- 数据库连接池缓存 --- 
@st.cache_resource
def get_db_engine():
    # 注意：在 Docker 网络中，host 应改为 'db'
    db_url = "postgresql+psycopg2://admin:password123@db:5432/stock_data?sslmode=disable"
    return create_engine(
        db_url, 
        pool_size=10,        # 连接池大小 
        max_overflow=20,     # 允许溢出连接数
        pool_pre_ping=True   # 每次使用前检查连接是否存活
    )

# --- PDF 中文报告生成器 --- 
def generate_pdf_report(df):
    pdf = FPDF()
    pdf.add_page()
    try:
        # 需确保项目根目录下有 simhei.ttf 文件
        pdf.add_font('SimHei', '', 'simhei.ttf', uni=True)
        pdf.set_font('SimHei', size=16)
        pdf.cell(0, 10, 'StockFocus 投研日报', ln=True, align='C')
    except:
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 10, 'StockFocus Daily Report', ln=True, align='C')
    
    # ... 写入数据逻辑 ...
    return pdf.output(dest='S').encode('latin-1', 'replace')

engine = get_db_engine()
# 后续 UI 逻辑调用 engine 即可