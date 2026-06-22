"""
StockFocus 综合股票扫描器
整合所有Standalone脚本功能，提供ROE分析和数据扫描
"""
import pandas as pd
import akshare as ak
from sqlalchemy import text
import time
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from config import config, setup_network_config, get_db_engine
from valuation import calculate_dynamic_fair_price

# 设置配置
setup_network_config()
logger = config.setup_logging()

class StockScanner:
    """股票扫描器"""
    
    def __init__(self):
        self.engine = get_db_engine()
    
    def clean_numeric_value(self, val) -> float:
        """清理数值数据"""
        s = str(val).replace('%', '').strip()
        if s in ['False', 'None', '--', '', 'nan', 'NaN']:
            return 0.0
        try:
            return float(s)
        except:
            return 0.0
    
    def get_all_stock_codes(self) -> Tuple[Dict[str, str], List[str]]:
        """获取所有A股代码和名称"""
        try:
            logger.info("📥 正在获取A股名册...")
            stock_info_df = ak.stock_info_a_code_name()
            name_map = dict(zip(stock_info_df['code'], stock_info_df['name']))
            all_codes = stock_info_df['code'].tolist()
            logger.info(f"✅ 成功获取 {len(all_codes)} 只股票信息")
            return name_map, all_codes
        except Exception as e:
            logger.error(f"❌ 获取股票名册失败: {e}")
            return {}, []
    
    def analyze_stock_roe(self, code: str, stock_name: str, roe_threshold: float = 15.0, years: int = 10) -> Optional[Dict]:
        """分析单只股票的ROE指标"""
        try:
            # 获取财务指标数据
            df = ak.stock_financial_analysis_indicator(symbol=code, start_year=str(datetime.now().year - years))
            
            if df is None or df.empty:
                return None
            
            # 提取ROE数据 - akshare 返回的中文列名
            roe_col = None
            for col in ['净资产收益率(%)', 'ROE(%)']:
                if col in df.columns:
                    roe_col = col
                    break
            
            if roe_col:
                roe_data = df[roe_col].dropna().head(years)
                roe_values = [self.clean_numeric_value(val) for val in roe_data]
                
                min_required_years = max(5, years // 2)
                if len(roe_values) >= min_required_years:
                    avg_roe = sum(roe_values) / len(roe_values)
                    min_roe = min(roe_values)
                    
                    # 计算综合质量评分
                    quality_score = 0
                    if avg_roe >= roe_threshold:
                        quality_score += 50
                    if min_roe >= roe_threshold * 0.8:  # 允许少量年份略低
                        quality_score += 30
                    if all(roe >= roe_threshold * 0.6 for roe in roe_values):  # 所有年份不能太差
                        quality_score += 20
                    
                    return {
                        'symbol': code,
                        'name': stock_name,
                        'avg_roe': avg_roe,
                        'min_roe': min_roe,
                        'roe_5y': avg_roe,  # 兼容字段
                        'quality_score': quality_score,
                        'data_years': len(roe_values),
                        'scan_date': datetime.now()
                    }
            
        except Exception as e:
            logger.debug(f"分析 {stock_name}({code}) ROE数据失败: {e}")
        
        return None
    
    def calculate_fair_price(self, code: str, avg_roe: float, industry: str = None) -> Optional[Dict]:
        try:
            df = ak.stock_financial_analysis_indicator(symbol=code, start_year=str(datetime.now().year - 2))
            if df is None or df.empty:
                return None
            
            eps_field = None
            for col in ['摊薄每股收益(元)', '加权每股收益(元)', '每股收益_调整后(元)']:
                if col in df.columns:
                    eps_field = col
                    break
            
            if eps_field and eps_field in df:
                latest_eps = self.clean_numeric_value(df[eps_field].iloc[0])
                if latest_eps > 0:
                    dynamic_val = calculate_dynamic_fair_price(
                        eps=latest_eps,
                        industry=industry
                    )
                    return dynamic_val
            
        except Exception as e:
            logger.debug(f"计算 {code} 合理价格失败: {e}")
        
        return None
    
    def scan_high_quality_stocks(self, roe_threshold: float = 15.0, years: int = 10, max_stocks: int = 100) -> List[Dict]:
        """扫描高质量股票"""
        logger.info(f"🚀 启动高质量股票扫描 (ROE > {roe_threshold}%, {years}年)")
        
        # 获取所有股票
        name_map, all_codes = self.get_all_stock_codes()
        if not all_codes:
            return []
        
        quality_stocks = []
        
        for i, code in enumerate(all_codes):
            if len(quality_stocks) >= max_stocks:
                break
            
            stock_name = name_map.get(code, "未知")
            logger.info(f"🔍 [{i+1}/{len(all_codes)}] 正在分析: {stock_name}({code})")
            
            # 分析ROE
            analysis_result = self.analyze_stock_roe(code, stock_name, roe_threshold, years)
            
            if analysis_result and analysis_result['quality_score'] >= 70:
                dynamic_val = self.calculate_fair_price(code, analysis_result['avg_roe'])
                if dynamic_val:
                    analysis_result['fair_price'] = dynamic_val['fair_price_mid']
                    analysis_result['fair_price_low'] = dynamic_val['fair_price_low']
                    analysis_result['fair_price_high'] = dynamic_val['fair_price_high']
                    analysis_result['pe_mid'] = dynamic_val['pe_mid']
                    analysis_result['industry_pe_info'] = dynamic_val['industry_info']
                    quality_stocks.append(analysis_result)
                    logger.info(f"✅ 发现优质股: {stock_name} - ROE: {analysis_result['avg_roe']:.1f}%, 评分: {analysis_result['quality_score']}")
            
            # 礼貌性延迟
            time.sleep(0.1)
        
        logger.info(f"🎉 扫描完成，发现 {len(quality_stocks)} 只高质量股票")
        return quality_stocks
    
    def save_to_database(self, stocks_data: List[Dict]) -> int:
        """保存扫描结果到数据库"""
        if not stocks_data:
            return 0
        
        try:
            saved_count = 0
            with self.engine.begin() as conn:
                for stock in stocks_data:
                    # 检查是否已存在
                    existing = conn.execute(
                        text("SELECT symbol FROM market_scan_results WHERE symbol = :symbol"),
                        {"symbol": stock['symbol']}
                    ).fetchone()
                    
                    if existing:
                        # 更新现有记录
                        conn.execute(
                            text("""
                                UPDATE market_scan_results 
                                SET name = :name, roe_5y = :roe_5y, fair_price = :fair_price,
                                    quality_score = :quality_score, scan_date = :scan_date
                                WHERE symbol = :symbol
                            """),
                            stock
                        )
                    else:
                        # 插入新记录
                        conn.execute(
                            text("""
                                INSERT INTO market_scan_results 
                                (symbol, name, roe_5y, fair_price, quality_score, scan_date, current_price, bias)
                                VALUES (:symbol, :name, :roe_5y, :fair_price, :quality_score, :scan_date, 0, 0)
                            """),
                            stock
                        )
                    
                    saved_count += 1
            
            logger.info(f"✅ 成功保存 {saved_count} 只股票数据到数据库")
            return saved_count
            
        except Exception as e:
            logger.error(f"❌ 保存数据到数据库失败: {e}")
            return 0
    
    def run_full_scan(self, roe_threshold: float = 15.0, years: int = 10, max_stocks: int = 100) -> bool:
        """运行完整扫描流程"""
        try:
            # 扫描高质量股票
            quality_stocks = self.scan_high_quality_stocks(roe_threshold, years, max_stocks)
            
            if not quality_stocks:
                logger.warning("⚠️ 未发现符合条件的高质量股票")
                return False
            
            # 保存到数据库
            saved_count = self.save_to_database(quality_stocks)
            
            if saved_count > 0:
                logger.info(f"🎉 完整扫描成功，发现并保存了 {saved_count} 只高质量股票")
                
                # 显示排名前10的股票
                sorted_stocks = sorted(quality_stocks, key=lambda x: x['quality_score'], reverse=True)
                logger.info("🏆 质量评分前10的股票:")
                for i, stock in enumerate(sorted_stocks[:10]):
                    logger.info(f"  {i+1}. {stock['name']}({stock['symbol']}) - 评分: {stock['quality_score']}, ROE: {stock['avg_roe']:.1f}%")
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ 完整扫描流程失败: {e}")
            return False

def main():
    """主函数"""
    logger.info("🎯 StockFocus 股票扫描器启动")
    
    scanner = StockScanner()
    
    # 运行扫描 (可调整参数)
    success = scanner.run_full_scan(
        roe_threshold=15.0,  # ROE阈值
        years=10,           # 分析年数
        max_stocks=200      # 最大保存数量
    )
    
    if success:
        logger.info("🎊 扫描任务完成！数据已保存到数据库，可以在Web界面查看。")
    else:
        logger.error("💔 扫描任务失败，请检查日志并重试。")

if __name__ == "__main__":
    main()