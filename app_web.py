"""
StockFocus Web应用 - 重构版本
采用模块化设计，增强错误处理和日志记录
"""
import streamlit as st
import pandas as pd
import time
import warnings
from datetime import datetime
from typing import Dict, Any
from plotly.subplots import make_subplots
import plotly.express as px
import plotly.graph_objects as go
from fpdf import FPDF
from sqlalchemy import text

from config import config, setup_network_config, get_db_engine
from stock_api import EastMoneyAPI

@st.cache_data(ttl=60)
def get_cached_stock_data(symbols: list) -> pd.DataFrame:
    if not symbols:
        return pd.DataFrame()
    try:
        engine = get_db_engine()
        placeholders = ", ".join([f":s{i}" for i in range(len(symbols))])
        params = {f"s{i}": s for i, s in enumerate(symbols)}
        query = f"SELECT * FROM market_scan_results WHERE symbol IN ({placeholders})"
        return pd.read_sql(text(query), engine, params=params).fillna(0)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"获取数据失败: {e}")
        return pd.DataFrame()

# 应用配置
st.set_page_config(
    page_title="StockFocus Pro", 
    layout="wide", 
    page_icon="🦅",
    initial_sidebar_state="expanded"
)

# 设置网络和日志
setup_network_config()
warnings.filterwarnings('ignore')
logger = config.setup_logging()

class StockDataService:
    def __init__(self, engine):
        self.engine = engine
        self.api = EastMoneyAPI()
    
    def fetch_realtime(self, symbol: str) -> Dict[str, Any]:
        return self.api.fetch_realtime(symbol)
    
    def fetch_realtime_batch(self, symbols: list) -> Dict[str, Any]:
        return self.api.fetch_realtime_batch(symbols)
    
    def get_stock_data(self, symbols: list) -> pd.DataFrame:
        return get_cached_stock_data(symbols)
    
    def update_stock_prices(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        
        needs_update = (df['current_price'].sum() == 0) or st.sidebar.button("⚡ 强制刷新数据")
        
        if needs_update:
            get_cached_stock_data.clear()
            get_cached_stock_data(df['symbol'].tolist())
            
            with st.spinner("🚀 正在更新实时数据..."):
                try:
                    symbols = df['symbol'].tolist()
                    fair_price_map = dict(zip(df['symbol'], df['fair_price']))
                    realtime_data = self.fetch_realtime_batch(symbols)
                    
                    if realtime_data:
                        with self.engine.begin() as conn:
                            for symbol, data in realtime_data.items():
                                fair_price = float(fair_price_map.get(symbol, 0))
                                bias = ((data['price'] - fair_price) / fair_price * 100) if fair_price > 0 else 0
                                
                                conn.execute(
                                    text("""
                                        UPDATE market_scan_results 
                                        SET current_price=:price, name=:name, 
                                            mkt_cap=:mkt_cap, industry=:industry, bias=:bias 
                                        WHERE symbol=:symbol
                                    """),
                                    {
                                        "price": data['price'], 
                                        "name": data['name'],
                                        "mkt_cap": data['mkt_cap'], 
                                        "industry": data['industry'], 
                                        "bias": bias, 
                                        "symbol": symbol
                                    }
                                )
                        
                        df = self.get_stock_data(symbols)
                        st.success("✅ 数据更新完成")
                except Exception as e:
                    st.error(f"❌ 数据更新失败: {e}")
                    logger.error(f"数据更新失败: {e}")
        
        return df

class PDFReportGenerator:
    """PDF报告生成器"""
    
    @staticmethod
    def generate_report(df: pd.DataFrame) -> str:
        """生成投研日报PDF"""
        try:
            pdf = FPDF()
            pdf.add_page()
            
            # 尝试使用中文字体
            try:
                pdf.add_font('SimHei', '', 'simhei.ttf', uni=True)
                pdf.set_font('SimHei', size=16)
                title = 'StockFocus 投研日报'
            except:
                pdf.set_font("Arial", 'B', 16)
                title = 'StockFocus Daily Report'
            
            pdf.cell(0, 10, title, ln=True, align='C')
            pdf.ln(10)
            
            pdf.set_font("Arial", size=12)
            date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            pdf.cell(0, 10, f'Generated: {date_str}', ln=True)
            pdf.ln(5)
            
            # 黄金坑资产
            golden_pits = df[df['bias'] < -15]
            pdf.cell(0, 10, 'Golden Pit Assets (Bias < -15%):', ln=True)
            
            if not golden_pits.empty:
                for _, row in golden_pits.iterrows():
                    line = f"{row['symbol']} - {row['name']} - Bias: {row['bias']:.2f}% - ROE: {row['roe_5y']}%"
                    pdf.cell(0, 8, line, ln=True)
            else:
                pdf.cell(0, 8, "No assets currently in Golden Pit zone.", ln=True)
            
            filename = f"StockFocus_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            pdf.output(filename)
            return filename
            
        except Exception as e:
            logger.error(f"生成PDF报告失败: {e}")
            st.error(f"生成PDF报告失败: {e}")
            return ""

def create_visualization(df: pd.DataFrame, chart_type: str = "bias_heatmap"):
    """创建可视化图表"""
    if df.empty:
        return go.Figure()
    
    fig = None
    
    if chart_type == "bias_heatmap":
        fig = px.scatter(
            df, 
            x='symbol', 
            y='bias', 
            size='mkt_cap',
            color='roe_5y',
            hover_data=['name', 'current_price', 'fair_price'],
            title="股票估值偏差热力图",
            color_continuous_scale='RdYlGn_r'
        )
        fig.add_hline(y=-15, line_dash="dash", line_color="green", annotation_text="黄金坑线")
        fig.add_hline(y=20, line_dash="dash", line_color="red", annotation_text="高估线")
        
    elif chart_type == "industry_analysis":
        if 'industry' in df.columns and df['industry'].nunique() > 1:
            industry_df = df.groupby('industry').agg({
                'bias': 'mean',
                'roe_5y': 'mean',
                'mkt_cap': 'sum'
            }).reset_index()
            
            fig = px.bar(
                industry_df, 
                x='industry', 
                y='bias',
                color='roe_5y',
                title="行业估值偏差分析",
                labels={'bias': '平均偏差率(%)', 'industry': '行业'}
            )
        else:
            fig = go.Figure()
            fig.add_annotation(text="数据不足以进行行业分析", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
    
    return fig or go.Figure()

def main():
    """主函数"""
    # 初始化服务
    engine = get_db_engine()
    data_service = StockDataService(engine)
    
    # 侧边栏控制面板
    with st.sidebar:
        st.header("⚙️ 投研控制台")
        
        user_input = st.text_area(
            "自选股票池", 
            "600519,000858,603288",
            help="输入股票代码，用逗号分隔"
        )
        
        watchlist = [c.strip() for c in user_input.replace('\n', ',').split(',') if c.strip()]
        
        st.markdown("---")
        st.markdown("### 数据刷新设置")
        auto_refresh = st.checkbox("自动刷新", value=True)
        refresh_interval = st.slider("刷新间隔(秒)", 5, 60, 10)
    
    # 获取数据
    df = pd.DataFrame()
    if watchlist:
        df = data_service.get_stock_data(watchlist)
        df = data_service.update_stock_prices(df)
    
    # 主要内容区域
    if not df.empty:
        # 指标卡片
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_stocks = len(df)
            st.metric("总股票数", total_stocks)
        
        with col2:
            golden_pits = len(df[df['bias'] < -15])
            st.metric("黄金坑股票", golden_pits, delta=f"{golden_pits/total_stocks*100:.1f}%")
        
        with col3:
            overvalued = len(df[df['bias'] > 20])
            st.metric("高估股票", overvalued, delta=f"{overvalued/total_stocks*100:.1f}%")
        
        with col4:
            avg_roe = df['roe_5y'].mean()
            st.metric("平均ROE", f"{avg_roe:.1f}%")
        
        # 标签页
        t1, t2, t3, t4, t5 = st.tabs(["📊 全景看板", "🧠 AI 审计", "🗺️ 行业分析", "📈 风险分析", "📄 报告导出"])
        
        with t1:
            st.markdown("### 📊 全景看板")
            
            if not df.empty:
                c1, c2, c3, c4, c5 = st.columns(5)
                
                with c1:
                    total = len(df)
                    st.metric("自选股数", total)
                
                with c2:
                    golden = len(df[df['bias'] < -15])
                    st.metric("黄金坑", golden, delta=f"{golden/total*100:.1f}%" if total > 0 else "0%")
                
                with c3:
                    buy = len(df[(df['bias'] >= -15) & (df['bias'] < 0)])
                    st.metric("关注", buy, delta=f"{buy/total*100:.1f}%" if total > 0 else "0%")
                
                with c4:
                    sell = len(df[df['bias'] > 20])
                    st.metric("高估", sell, delta=f"{sell/total*100:.1f}%" if total > 0 else "0%")
                
                with c5:
                    avg_roe = df['roe_5y'].mean()
                    st.metric("平均ROE", f"{avg_roe:.1f}%")
            
            st.markdown("---")
            
            if not df.empty:
                def get_action(bias):
                    if bias < -15:
                        return "💎 Buy"
                    elif bias < 0:
                        return "👀 关注"
                    elif bias > 20:
                        return "🔴 Sell"
                    return "➖ 持有"
                
                df['action'] = df['bias'].apply(get_action)
                
                def color_action(action):
                    if action == "💎 Buy":
                        return 'background-color: #c6efce; color: #006100; font-weight: bold'
                    elif action == "👀 关注":
                        return 'background-color: #ffeb9c; color: #9c5700'
                    elif action == "🔴 Sell":
                        return 'background-color: #ffc7ce; color: #9c0006; font-weight: bold'
                    return ''
                
                table_cols = ['symbol', 'name', 'current_price', 'fair_price', 'bias', 'roe_5y', 'action', 'industry']
                display_df = df[table_cols].copy()
                
                styled = display_df.style.format({
                    'current_price': '¥{:.2f}',
                    'fair_price': '¥{:.2f}',
                    'bias': '{:+.2f}%',
                    'roe_5y': '{:.1f}%'
                }).applymap(lambda x: 'background-color: #c6efce; color: #006100' if x < -15 else ('background-color: #ffc7ce; color: #9c0006' if x > 20 else ''), subset=['bias']).applymap(color_action, subset=['action'])
                
                st.dataframe(styled, use_container_width=True, height=400)
            
            st.markdown("---")
            
            col_chart1, col_chart2 = st.columns(2)
            
            with col_chart1:
                if not df.empty:
                    colors = []
                    for b in df['bias']:
                        if b < -15:
                            colors.append('#00C853')
                        elif b < 0:
                            colors.append('#FFD600')
                        elif b > 20:
                            colors.append('#FF1744')
                        else:
                            colors.append('#2196F3')
                    
                    fig = go.Figure(data=[
                        go.Bar(x=df['symbol'], y=df['bias'], marker_color=colors)
                    ])
                    fig.add_hline(y=-15, line_dash="dash", line_color="green", annotation_text="黄金坑")
                    fig.add_hline(y=0, line_dash="dot", line_color="gray")
                    fig.add_hline(y=20, line_dash="dash", line_color="red", annotation_text="高估")
                    fig.update_layout(title="估值偏差", height=300, xaxis_tickangle=-45)
                    st.plotly_chart(fig, use_container_width=True)
            
            with col_chart2:
                if not df.empty:
                    fig2 = px.scatter(df, x='bias', y='roe_5y', size='mkt_cap', hover_name='symbol', color='bias', color_continuous_scale='RdYlGn_r', title="ROE vs 估值偏差")
                    fig2.add_vline(x=-15, line_dash="dash", line_color="green")
                    fig2.add_vline(x=0, line_dash="dot", line_color="gray")
                    fig2.add_vline(x=20, line_dash="dash", line_color="red")
                    fig2.update_layout(height=300)
                    st.plotly_chart(fig2, use_container_width=True)
        
        with t2:
            st.subheader("AI 深度审计")
            
            try:
                from ai_audit import AIAuditor
                
                selected = st.selectbox("选择股票", df['symbol'].tolist() if len(df) > 0 else [], key="ai_audit_select")
                
                if selected:
                    stock_row = df[df['symbol'] == selected].iloc[0]
                    auditor = AIAuditor()
                    audit = auditor.audit_stock(stock_row.to_dict())
                    
                    col_a, col_b = st.columns(2)
                    
                    with col_a:
                        st.markdown("### 📊 估值分析")
                        v = audit['valuation']
                        st.markdown(f"""
                        - **当前价格**: ¥{v['current_price']:.2f}
                        - **合理价(低)**: ¥{v['fair_price_low']:.2f}
                        - **合理价(中)**: ¥{v['fair_price_mid']:.2f}
                        - **合理价(高)**: ¥{v['fair_price_high']:.2f}
                        - **行业**: {v['industry']}
                        """)
                        
                        st.markdown("### 💎 黄金坑")
                        gp = audit['golden_pit']
                        st.markdown(f"""
                        - **评分**: {gp['score']}/100
                        - **建议**: {gp['recommendation']}
                        - **置信度**: {gp['confidence']}
                        - **原因**: {', '.join(gp['reasons']) if gp['reasons'] else '无'}
                        """)
                    
                    with col_b:
                        st.markdown("### ⚠️ 风险评估")
                        r = audit['risk']
                        st.markdown(f"""
                        - **风险评分**: {r['risk_score']}/100
                        - **总体评估**: {r['overall_assessment']}
                        - **Beta**: {r['beta']['beta']} ({r['beta']['interpretation']})
                        - **VaR**: {r['var']['var_percentage']}% (单日)
                        - **最大回撤**: {r['max_drawdown']['max_drawdown_pct']}%
                        """)
                        
                        st.markdown("### 🎯 综合评分")
                        st.metric("综合得分", audit['overall_score'],"/100")
                        rec = audit['recommendation']
                        st.markdown(f"**操作建议**: {rec['action']}")
                        
            except Exception as e:
                st.error(f"AI审计加载失败: {e}")
                st.info("AI审计功能正在开发中...")
        
        with t3:
            st.subheader("行业分析")
            if 'industry' in df.columns and df['industry'].nunique() > 1:
                st.plotly_chart(create_visualization(df, "industry_analysis"), use_container_width=True)
            else:
                st.warning("数据不足以进行行业分析")
        
        with t4:
            st.subheader("📈 风险分析")
            
            # 导入风险分析模块
            try:
                from evaluation_models import RiskAnalyzer
                
                risk_analyzer = RiskAnalyzer()
                
                if len(df) > 0:
                    # 选择单只股票进行风险分析
                    selected_symbol = st.selectbox("选择股票", df['symbol'].tolist(), key="risk_analysis_select")
                    
                    if selected_symbol:
                        # 获取选中股票数据
                        stock_data = df[df['symbol'] == selected_symbol].iloc[0]
                        current_price = float(stock_data['current_price'])
                        industry = stock_data.get('industry', None)
                        
                        # 计算综合风险指标
                        risk_summary = risk_analyzer.calculate_risk_summary(
                            selected_symbol, 
                            current_price, 
                            expected_return=0.15,
                            industry=industry
                        )
                        
                        # 显示风险概览
                        st.markdown(f"""
                        ### 🎯 风险评估: {risk_summary['overall_assessment']}
                        **综合风险评分**: {risk_summary['risk_score']}/100
                        """)
                        
                        # 三列展示主要风险指标
                        rc1, rc2, rc3 = st.columns(3)
                        
                        with rc1:
                            beta_data = risk_summary['beta']
                            st.markdown(f"""
                            #### 📊 Beta系数: {beta_data['beta']}
                            {beta_data['color_emoji']} **{beta_data['interpretation']}**
                            - 风险等级: {beta_data['risk_level']}
                            - 市场波动假设: {beta_data['market_volatility_assumption']*100:.0f}%
                            """)
                            
                            # Beta图表
                            beta_gauge = go.Figure(go.Indicator(
                                mode = "gauge+number",
                                value = beta_data['beta'],
                                title = {'text': "Beta"},
                                gauge = {
                                    'axis': {'range': [0.5, 1.8]},
                                    'bar': {'color': "darkblue"},
                                    'steps': [
                                        {'range': [0.5, 0.8], 'color': "lightgreen"},
                                        {'range': [0.8, 1.0], 'color': "lightyellow"},
                                        {'range': [1.0, 1.3], 'color': "orange"},
                                        {'range': [1.3, 1.8], 'color': "lightcoral"}
                                    ]
                                }
                            ))
                            st.plotly_chart(beta_gauge, use_container_width=True)
                        
                        with rc2:
                            var_data = risk_summary['var']
                            st.markdown(f"""
                            #### ⚠️ VaR风险值: {var_data['var_percentage']}%
                            **置信水平**: {var_data['confidence_level']}
                            - 1万元持仓风险: ¥{var_data['var_10k_position']}
                            - 10万元持仓风险: ¥{var_data['var_100k_position']}
                            - 假设波动率: {var_data['assumed_volatility']}
                            
                            {var_data['interpretation']}
                            """)
                        
                        with rc3:
                            mdd_data = risk_summary['max_drawdown']
                            st.markdown(f"""
                            #### 📉 最大回撤: {mdd_data['max_drawdown_pct']}%
                            {mdd_data['color']} {mdd_data['interpretation']}
                            - 当前价格: ¥{mdd_data['current_price']}
                            """)
                            
                            # 夏普比率
                            sharpe = risk_summary['sharpe_ratio']
                            st.markdown(f"""
                            #### 📈 夏普比率: {sharpe['sharpe_ratio']}
                            {sharpe['color']} {sharpe['interpretation']}
                            - 超额收益: {sharpe['excess_return_pct']}%
                            - 波动率: {sharpe['volatility_pct']}%
                            """)
                        
                        # 交易成本分析
                        st.markdown("### 💰 交易成本分析")
                        tc1, tc2 = st.columns(2)
                        
                        with tc1:
                            shares = st.number_input("买入股数", min_value=100, value=1000, step=100)
                            transaction_cost = risk_analyzer.calculate_transaction_cost(
                                current_price, 
                                shares=shares
                            )
                            
                            st.markdown(f"""
                            #### 买入 {shares} 股 @ ¥{current_price}
                            
                            **成本明细:**
                            - 成交额: ¥{transaction_cost['turnover']:,.2f}
                            - 佣金: ¥{transaction_cost['commission']:.2f}
                            - 印花税: ¥{transaction_cost['stamp_tax']:.2f}
                            - 滑点成本: ¥{transaction_cost['slippage']:.2f}
                            
                            **总计成本**: ¥{transaction_cost['total_cost']:.2f} ({transaction_cost['cost_ratio']}%)
                            - 实际买入价: ¥{transaction_cost['effective_buy_price']}
                            - 实际卖出价: ¥{transaction_cost['effective_sell_price']}
                            """)
                        
                        with tc2:
                            # 风险收益分析
                            expected_return = st.slider("预期收益率(%)", 0, 50, 15) / 100
                            risk_free_rate = 0.03
                            volatility = 0.20
                            
                            sharpe_analysis = risk_analyzer.calculate_sharpe_ratio(
                                expected_return,
                                risk_free_rate,
                                volatility
                            )
                            
                            st.markdown(f"""
                            #### 风险收益分析
                            
                            **输入参数:**
                            - 预期收益率: {expected_return*100:.1f}%
                            - 无风险利率: {risk_free_rate*100:.1f}%
                            - 年化波动率: {volatility*100:.0f}%
                            
                            **分析结果:**
                            - 夏普比率: {sharpe_analysis['sharpe_ratio']}
                            - 超额收益: {sharpe_analysis['excess_return_pct']:.1f}%
                            
                            {sharpe_analysis['interpretation']}
                            """)
                        
                        # 风险预警
                        st.markdown("### 🚨 风险提示")
                        warnings = []
                        
                        if risk_summary['risk_score'] > 70:
                            warnings.append("⚠️ 综合风险评分较高，建议谨慎")
                        if beta_data['beta'] > 1.2:
                            warnings.append("⚠️ Beta系数偏高，系统性风险较大")
                        if var_data['var_percentage'] > 4:
                            warnings.append("⚠️ VaR较高，单日最大损失可能超过4%")
                        if mdd_data['max_drawdown_pct'] > 20:
                            warnings.append("⚠️ 回撤风险较大，需关注")
                        
                        if warnings:
                            for warning in warnings:
                                st.warning(warning)
                        else:
                            st.success("✅ 当前风险水平在可接受范围内")
                            
                else:
                    st.info("请先选择股票进行风险分析")
                    
            except ImportError as e:
                st.error(f"风险分析模块加载失败: {e}")
            except Exception as e:
                st.error(f"风险分析计算失败: {e}")
                logger.error(f"风险分析错误: {e}")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("📄 生成投研日报 (PDF)"):
                    with st.spinner("正在生成PDF报告..."):
                        filename = PDFReportGenerator.generate_report(df)
                        if filename:
                            st.success(f"✅ 报告已生成: {filename}")
                            with open(filename, "rb") as f:
                                st.download_button(
                                    "⬇️ 下载报告",
                                    f,
                                    file_name=filename,
                                    mime="application/pdf"
                                )
            
            with col2:
                if st.button("📊 导出Excel数据"):
                    excel_filename = f"StockFocus_Data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                    csv_data = df.to_csv(index=False)
                    st.download_button(
                        "⬇️ 下载CSV",
                        csv_data,
                        file_name=excel_filename,
                        mime="text/csv"
                    )
    
    else:
        st.warning("📝 请在左侧输入股票代码开始分析")
        st.info("💡 提示：您可以输入如 600519,000858,603288 这样的股票代码")

if __name__ == "__main__":
    main()