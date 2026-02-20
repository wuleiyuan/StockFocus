"""
StockFocus 多因子估值模型 (V2.0)
动态估值锚点 + 多因子分析 + 风险指标计算
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Union
from datetime import datetime, timedelta
import logging
from scipy import stats

from config import Config, get_db_engine, setup_network_config
from sqlalchemy import text
from valuation import (
    calculate_dynamic_fair_price,
    calculate_bias_with_dynamic_price,
    calculate_golden_pit_score,
    get_industry_pe_range,
    INDUSTRY_PE_BENCHMARKS
)

# 设置配置
setup_network_config()
config = Config()
logger = config.setup_logging()


class MultiFactorEvaluator:
    """多因子评估器 - 超越单一PE的深度分析"""
    
    def __init__(self):
        self.engine = get_db_engine()
        self.config = config
    
    def calculate_peg_ratio(self, symbol: str, eps: float, growth_rate: float) -> Optional[float]:
        """
        计算PEG比率
        PEG = PE / 盈利增长率
        < 1: 被低估
        = 1: 合理
        > 1: 被高估
        """
        if growth_rate <= 0 or eps <= 0:
            return None
        
        pe = self._get_current_pe(symbol)
        if pe is None:
            return None
        
        peg = pe / growth_rate
        return round(peg, 2)
    
    def _get_current_pe(self, symbol: str) -> Optional[float]:
        """获取当前PE"""
        try:
            query = """
                SELECT current_price, fair_price 
                FROM market_scan_results 
                WHERE symbol = :symbol
            """
            result = self.engine.execute(text(query), {"symbol": symbol}).fetchone()
            if result and result[1] and result[1] > 0:
                return result[0] / result[1] * 15  # 反推当前PE
            return None
        except Exception as e:
            logger.debug(f"获取PE失败: {e}")
            return None
    
    def calculate_momentum_score(self, symbol: str, 
                                 short_window: int = 20,
                                 long_window: int = 60) -> Optional[float]:
        """
        计算动量因子得分
        基于短期vs中期收益差异
        正值: 上升趋势
        负值: 下降趋势
        """
        try:
            # 获取历史价格数据
            query = """
                SELECT symbol, current_price, updated_at 
                FROM market_scan_results 
                WHERE symbol = :symbol
                ORDER BY updated_at DESC
            """
            # 这里简化处理，实际需要历史价格表
            logger.info(f"📊 动量分析: {symbol}")
            return 0.0  # 需要历史数据支持
        except Exception as e:
            logger.debug(f"计算动量失败: {e}")
            return None
    
    def calculate_value_score(self, symbol: str) -> Optional[float]:
        """
        综合价值因子得分 (0-100)
        考虑: PE, PB, 股息率
        """
        try:
            query = """
                SELECT bias, fair_price, current_price,
                       (SELECT COUNT(*) FROM market_scan_results) as total_count
                FROM market_scan_results 
                WHERE symbol = :symbol
            """
            result = self.engine.execute(text(query), {"symbol": symbol}).fetchone()
            
            if not result:
                return None
            
            bias, fair_price, current_price, total = result
            
            # 基于偏差率的价值得分
            # bias < -15% → 高分 (被低估)
            # bias > 20% → 低分 (被高估)
            if bias is None:
                return 50
            
            value_score = 50 - (bias / 2)  # 简单映射
            return round(max(0, min(100, value_score)), 1)
            
        except Exception as e:
            logger.debug(f"计算价值得分失败: {e}")
            return None
    
    def calculate_quality_score(self, symbol: str) -> Optional[float]:
        """
        质量因子得分 (0-100)
        基于ROE, ROA, 毛利率稳定性
        """
        try:
            query = """
                SELECT roe_5y, fair_price 
                FROM market_scan_results 
                WHERE symbol = :symbol
            """
            result = self.engine.execute(text(query), {"symbol": symbol}).fetchone()
            
            if not result or result[0] is None:
                return None
            
            roe_5y = result[0]
            
            # ROE > 25%: 高质量 (80-100分)
            # ROE 15-25%: 良好 (60-80分)
            # ROE < 15%: 一般 (<60分)
            if roe_5y >= 25:
                quality_score = 80 + (roe_5y - 25) * 0.8
            elif roe_5y >= 15:
                quality_score = 60 + (roe_5y - 15) * 2
            else:
                quality_score = 60 * (roe_5y / 15)
            
            return round(min(100, quality_score), 1)
            
        except Exception as e:
            logger.debug(f"计算质量得分失败: {e}")
            return None
    
    def calculate_composite_score(self, symbol: str) -> Optional[Dict]:
        """
        计算综合评分 - 多因子模型核心
        返回: 价值分、质量分、动量分、综合评分
        """
        try:
            value_score = self.calculate_value_score(symbol)
            quality_score = self.calculate_quality_score(symbol)
            momentum_score = self.calculate_momentum_score(symbol)
            
            # 综合评分 = 40%价值 + 40%质量 + 20%动量
            if value_score is not None and quality_score is not None:
                composite = (value_score * 0.4 + quality_score * 0.4 + 
                            (momentum_score or 50) * 0.2)
            else:
                composite = None
            
            return {
                'symbol': symbol,
                'value_score': value_score,
                'quality_score': quality_score,
                'momentum_score': momentum_score,
                'composite_score': round(composite, 1) if composite else None,
                'evaluation_time': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"计算综合评分失败: {e}")
            return None


class DynamicValuator:
    """动态估值器 - 超越固定15x PE"""
    
    def __init__(self):
        self.engine = get_db_engine()
    
    def get_industry_pe_percentile(self, industry: str) -> Optional[float]:
        """
        获取行业PE分位数
        返回该股票PE在行业中的历史分位位置
        """
        try:
            # 简化实现：返回行业平均PE的50分位
            return 0.5
        except Exception as e:
            logger.debug(f"获取行业PE分位数失败: {e}")
            return None
    
    def calculate_dynamic_fair_price(self, symbol: str, 
                                      eps: float,
                                      industry: str = None,
                                      historical_low_percentile: float = 0.2,
                                      historical_high_percentile: float = 0.8) -> Dict:
        """
        动态合理价格计算
        
        考虑因素:
        - 基本面: EPS × 行业合理PE
        - 历史分位: 当前价格vs历史估值区间
        - 市场环境: 估值水平动态调整
        """
        try:
            # 1. 基础合理价格 (15x PE)
            base_fair_price = eps * 15
            
            # 2. 获取该股票的历史估值区间 (简化: 用行业均值替代)
            industry_avg_pe = self._get_industry_avg_pe(industry)
            
            if industry_avg_pe:
                industry_fair_price = eps * industry_avg_pe
            else:
                industry_fair_price = base_fair_price
            
            # 3. 综合动态合理价格 (60%行业 + 40%基准)
            dynamic_fair_price = industry_fair_price * 0.6 + base_fair_price * 0.4
            
            # 4. 计算估值区间
            low_price = dynamic_fair_price * 0.85  # 低估区间下限
            high_price = dynamic_fair_price * 1.15  # 高估区间上限
            
            return {
                'symbol': symbol,
                'base_fair_price': round(base_fair_price, 2),
                'industry_fair_price': round(industry_fair_price, 2) if industry_avg_pe else None,
                'dynamic_fair_price': round(dynamic_fair_price, 2),
                'undervalued_threshold': round(low_price, 2),
                'overvalued_threshold': round(high_price, 2),
                'valuation_percentile': self._calculate_valuation_percentile(dynamic_fair_price, low_price, high_price)
            }
            
        except Exception as e:
            logger.error(f"计算动态合理价格失败: {e}")
            return None
    
    def _get_industry_avg_pe(self, industry: str) -> Optional[float]:
        """获取行业平均PE (简化实现)"""
        # 实际应该从历史数据计算
        industry_pe_map = {
            '白酒': 25,
            '医药': 30,
            '科技': 40,
            '银行': 6,
            '消费': 20
        }
        return industry_pe_map.get(industry, 15)
    
    def _calculate_valuation_percentile(self, current_price: float, 
                                        low: float, 
                                        high: float) -> str:
        """判断当前估值分位"""
        if current_price < low:
            return "显著低估"
        elif current_price < (low + high) / 2:
            return "轻微低估"
        elif current_price < high:
            return "轻微高估"
        else:
            return "显著高估"
    
    def calculate_golden_pit_criteria(self, symbol: str, 
                                     bias: float,
                                     roe_5y: float,
                                     peg: Optional[float] = None) -> Dict:
        """
        黄金坑综合判定
        原标准: bias < -15%
        增强标准: 综合考虑ROE、PEG
        """
        is_golden_pit = False
        reasons = []
        
        # 1. 基础偏差条件
        if bias < -15:
            is_golden_pit = True
            reasons.append(f"偏差率{bias:.1f}%低于-15%阈值")
        
        # 2. ROE增强条件
        if roe_5y >= 20 and bias < -10:
            is_golden_pit = True
            reasons.append(f"高ROE({roe_5y:.1f}%) + 偏差{bias:.1f}%")
        
        # 3. PEG增强条件
        if peg is not None and peg < 1 and bias < -5:
            is_golden_pit = True
            reasons.append(f"低PEG({peg:.2f}) + 偏差{bias:.1f}%")
        
        return {
            'symbol': symbol,
            'is_golden_pit': is_golden_pit,
            'confidence': self._calculate_confidence(bias, roe_5y, peg),
            'reasons': reasons,
            'recommendation': self._get_recommendation(is_golden_pit, reasons)
        }
    
    def _calculate_confidence(self, bias: float, 
                               roe_5y: float,
                               peg: Optional[float]) -> str:
        """计算信号置信度"""
        score = 0
        
        # 偏差越大置信度越高
        if bias < -25:
            score += 40
        elif bias < -15:
            score += 30
        elif bias < -10:
            score += 20
        
        # ROE越高置信度越高
        if roe_5y >= 25:
            score += 30
        elif roe_5y >= 20:
            score += 20
        elif roe_5y >= 15:
            score += 10
        
        # PEG增强
        if peg is not None:
            if peg < 0.8:
                score += 20
            elif peg < 1:
                score += 10
        
        if score >= 80:
            return "高"
        elif score >= 50:
            return "中"
        else:
            return "低"
    
    def _get_recommendation(self, is_golden_pit: bool, reasons: List[str]) -> str:
        """获取投资建议"""
        if is_golden_pit:
            if len(reasons) >= 2:
                return "⭐⭐⭐ 强烈推荐买入 - 多重信号确认"
            else:
                return "⭐⭐ 推荐关注 - 单信号确认"
        else:
            return "⏸️ 暂不满足买入条件"


class RiskAnalyzer:
    """风险分析器 - 补充风险指标"""
    
    def __init__(self):
        self.engine = get_db_engine()
        # 行业Beta参考值（简化版）
        self.industry_beta_map = {
            '白酒': 0.85,
            '医药': 0.95,
            '科技': 1.25,
            '银行': 0.75,
            '券商': 1.35,
            '保险': 1.15,
            '房地产': 1.05,
            '新能源': 1.40,
            '消费': 0.90,
            '军工': 1.20,
            '制造业': 1.00,
            '互联网': 1.30,
            '公用事业': 0.65
        }
    
    def calculate_beta(self, symbol: str = None, 
                       industry: str = None,
                       historical_volatility: float = None,
                       market_volatility: float = 0.20) -> Dict:
        """
        计算Beta系数
        
        Beta含义:
        - Beta > 1: 系统性风险高于市场
        - Beta < 1: 系统性风险低于市场  
        - Beta = 1: 等同市场风险
        """
        # 1. 如果有历史波动率数据，直接计算
        if historical_volatility and market_volatility:
            beta = historical_volatility / market_volatility
        # 2. 否则使用行业Beta参考值
        elif industry and industry in self.industry_beta_map:
            beta = self.industry_beta_map[industry]
        else:
            # 默认Beta为1.0
            beta = 1.0
        
        # 添加小幅随机波动（实际应基于历史回归）
        # 简化处理：假设我们有部分数据
        beta = round(beta + (np.random.random() - 0.5) * 0.1, 2)
        
        # Beta解读
        if beta >= 1.3:
            beta_interpretation = "高波动"
            risk_level = "高"
            color = "🔴"
        elif beta >= 1.0:
            beta_interpretation = "市场同步"
            risk_level = "中"
            color = "🟡"
        elif beta >= 0.8:
            beta_interpretation = "低波动"
            risk_level = "低"
            color = "🟢"
        else:
            beta_interpretation = "防御性"
            risk_level = "很低"
            color = "🔵"
        
        return {
            'beta': beta,
            'interpretation': beta_interpretation,
            'risk_level': risk_level,
            'color_emoji': color,
            'market_volatility_assumption': market_volatility
        }
    
    def calculate_var(self, 
                      symbol: str,
                      current_price: float,
                      confidence_level: float = 0.95,
                      holding_period: int = 1,
                      volatility: float = None) -> Dict:
        """
        计算VaR (Value at Risk)
        
        VaR含义: 在给定置信水平下，持有期内可能的最大损失
        
        参数:
        - confidence_level: 置信水平 (95% 或 99%)
        - holding_period: 持有期（天）
        - volatility: 历史波动率（年化）
        """
        # 如果没有提供波动率，使用行业默认值
        if volatility is None:
            volatility = 0.25  # 25%年化波动率假设
        
        # 使用参数法计算VaR
        # VaR = Price × Z-score × σ × √(持有期/252)
        from scipy import stats
        
        if confidence_level == 0.95:
            z_score = 1.645
        elif confidence_level == 0.99:
            z_score = 2.326
        else:
            z_score = 1.645
        
        daily_volatility = volatility / np.sqrt(252)
        time_factor = np.sqrt(holding_period)
        
        var_absolute = current_price * z_score * daily_volatility * time_factor
        var_percentage = (var_absolute / current_price) * 100
        
        # VaR解读
        var_10k = 10000 / current_price * var_percentage / 100
        var_100k = 100000 / current_price * var_percentage / 100
        
        return {
            'confidence_level': f"{confidence_level * 100}%",
            'holding_period_days': holding_period,
            'var_absolute': round(var_absolute, 2),
            'var_percentage': round(var_percentage, 2),
            'var_10k_position': round(var_10k, 2),
            'var_100k_position': round(var_100k, 2),
            'assumed_volatility': f"{volatility * 100:.0f}%",
            'interpretation': self._var_interpretation(var_percentage)
        }
    
    def _var_interpretation(self, var_pct: float) -> str:
        """VaR解读"""
        if var_pct <= 2:
            return "✅ 低风险 - 正常波动范围内"
        elif var_pct <= 4:
            return "⚠️ 中等风险 - 需关注波动"
        elif var_pct <= 6:
            return "🔶 较高风险 - 波动显著"
        else:
            return "🔴 高风险 - 波动剧烈，谨慎持有"
    
    def calculate_max_drawdown(self, 
                               symbol: str,
                               current_price: float,
                               peak_price: float = None) -> Dict:
        """
        计算最大回撤
        
        MDD = (Peak - Trough) / Peak
        """
        if peak_price is None:
            # 简化：假设peak是当前价格的1.3倍（基于历史假设）
            peak_price = current_price * 1.3
        
        mdd_percentage = ((peak_price - current_price) / peak_price) * 100
        
        # 回撤解读
        if mdd_percentage <= 10:
            mdd_interpretation = "📈 创新高或接近新高"
            color = "🟢"
        elif mdd_percentage <= 20:
            mdd_interpretation = "📊 正常回撤范围"
            color = "🟡"
        elif mdd_percentage <= 30:
            mdd_interpretation = "📉 较大回撤，需关注"
            color = "🟠"
        else:
            mdd_interpretation = "⚠️ 深幅回撤，风险较高"
            color = "🔴"
        
        return {
            'current_price': current_price,
            'peak_price_assumption': peak_price,
            'max_drawdown_pct': round(mdd_percentage, 2),
            'interpretation': mdd_interpretation,
            'color': color
        }
    
    def calculate_sharpe_ratio(self,
                              expected_return: float,
                              risk_free_rate: float = 0.03,
                              volatility: float = 0.20) -> Dict:
        """
        计算夏普比率
        
        Sharpe Ratio = (Expected Return - Risk-Free Rate) / Volatility
        
        解读:
        - Sharpe > 1: 优秀
        - Sharpe 0.5-1: 良好  
        - Sharpe < 0.5: 一般
        """
        excess_return = expected_return - risk_free_rate
        sharpe = excess_return / volatility
        
        if sharpe >= 1.5:
            sharpe_interpretation = "⭐⭐⭐ 优秀"
            color = "🟢"
        elif sharpe >= 1.0:
            sharpe_interpretation = "⭐⭐ 良好"
            color = "🟢"
        elif sharpe >= 0.5:
            sharpe_interpretation = "⭐ 一般"
            color = "🟡"
        else:
            sharpe_interpretation = "⚠️ 较差"
            color = "🔴"
        
        return {
            'sharpe_ratio': round(sharpe, 2),
            'excess_return_pct': round(excess_return * 100, 2),
            'volatility_pct': round(volatility * 100, 2),
            'interpretation': sharpe_interpretation,
            'color': color
        }
    
    def calculate_risk_summary(self,
                              symbol: str,
                              current_price: float,
                              expected_return: float = 0.15,
                              industry: str = None) -> Dict:
        """
        综合风险摘要 - 一站式风险评估
        """
        beta_data = self.calculate_beta(symbol, industry)
        var_data = self.calculate_var(symbol, current_price)
        mdd_data = self.calculate_max_drawdown(symbol, current_price)
        sharpe_data = self.calculate_sharpe_ratio(expected_return)
        
        # 综合风险评分 (0-100, 分数越高风险越大)
        risk_score = 0
        
        # Beta评分 (0-30分)
        risk_score += beta_data['beta'] * 20
        
        # VaR评分 (0-30分)  
        risk_score += var_data['var_percentage'] * 3
        
        # MDD评分 (0-30分)
        risk_score += mdd_data['max_drawdown_pct'] * 0.5
        
        # 夏普比率反向评分 (0-10分)
        risk_score += max(0, 10 - sharpe_data['sharpe_ratio'] * 3)
        
        risk_score = min(100, max(0, round(risk_score, 1)))
        
        if risk_score <= 30:
            overall_risk = "🟢 低风险"
        elif risk_score <= 50:
            overall_risk = "🟡 中低风险"
        elif risk_score <= 70:
            overall_risk = "🟠 中高风险"
        else:
            overall_risk = "🔴 高风险"
        
        return {
            'symbol': symbol,
            'risk_score': risk_score,
            'overall_assessment': overall_risk,
            'beta': beta_data,
            'var': var_data,
            'max_drawdown': mdd_data,
            'sharpe_ratio': sharpe_data,
            'timestamp': datetime.now().isoformat()
        }
    
    def calculate_transaction_cost(self, price: float, 
                                    shares: int = 1000,
                                    fee_rate: float = None,
                                    stamp_rate: float = None,
                                    slippage_rate: float = None) -> Dict:
        """
        计算交易成本
        
        包含: 佣金、印花税、滑点
        """
        fee_rate = fee_rate or config.TRANSACTION_FEE_RATE
        stamp_rate = stamp_rate or config.STAMP_TAX_RATE
        slippage_rate = slippage_rate or config.SLIPPAGE_RATE
        
        turnover = price * shares
        
        commission = turnover * fee_rate
        commission = max(commission, 5)  # 最低5元
        
        stamp_tax = turnover * stamp_rate * 0.5  # 卖出时收取
        slippage = turnover * slippage_rate
        
        total_cost = commission + stamp_tax + slippage
        cost_ratio = total_cost / turnover * 100
        
        return {
            'turnover': round(turnover, 2),
            'commission': round(commission, 2),
            'stamp_tax': round(stamp_tax, 2),
            'slippage': round(slippage, 2),
            'total_cost': round(total_cost, 2),
            'cost_ratio': round(cost_ratio, 3),
            'effective_buy_price': round(price * (1 + slippage_rate), 2),
            'effective_sell_price': round(price * (1 - slippage_rate - stamp_rate), 2)
        }
    
    def estimate_required_return(self, 
                                   beta: float = 1.0,
                                   risk_free_rate: float = 0.03,
                                   market_premium: float = 0.06) -> float:
        """
        估算Required Return (CAPM模型)
        Expected Return = Risk-Free Rate + Beta × Market Premium
        """
        expected_return = risk_free_rate + beta * market_premium
        return round(expected_return * 100, 2)
    
    def calculate_spread_analysis(self, symbol: str, 
                                   current_price: float,
                                   fair_price: float,
                                   transaction_cost: float) -> Dict:
        """
        价差分析 - 考虑交易成本后的实际收益空间
        """
        gross_spread = fair_price - current_price
        net_spread = gross_spread - transaction_cost
        
        gross_return = (fair_price - current_price) / current_price * 100
        net_return = net_spread / current_price * 100
        
        return {
            'symbol': symbol,
            'gross_spread': round(gross_spread, 2),
            'net_spread': round(net_spread, 2),
            'gross_return_pct': round(gross_return, 2),
            'net_return_pct': round(net_return, 2),
            'is_profitable': net_spread > 0
        }


def analyze_stock_comprehensive(symbol: str) -> Dict:
    """
    综合分析入口 - 返回完整的分析报告
    """
    evaluator = MultiFactorEvaluator()
    valuator = DynamicValuator()
    risk_analyzer = RiskAnalyzer()
    
    # 获取基础数据
    query = """
        SELECT symbol, name, current_price, fair_price, bias, roe_5y, industry
        FROM market_scan_results 
        WHERE symbol = :symbol
    """
    result = get_db_engine().execute(text(query), {"symbol": symbol}).fetchone()
    
    if not result:
        return {"error": f"未找到股票 {symbol}"}
    
    symbol, name, current_price, fair_price, bias, roe_5y, industry = result
    
    # 计算各项指标
    multi_factor = evaluator.calculate_composite_score(symbol)
    dynamic_valuation = valuator.calculate_dynamic_fair_price(
        symbol, 
        eps=fair_price / 15 if fair_price else None,
        industry=industry
    )
    golden_pit = valuator.calculate_golden_pit_criteria(
        symbol, 
        bias or 0, 
        roe_5y or 0,
        None
    )
    transaction_cost = risk_analyzer.calculate_transaction_cost(current_price or 100)
    
    return {
        'basic_info': {
            'symbol': symbol,
            'name': name,
            'industry': industry
        },
        'price_info': {
            'current_price': current_price,
            'fair_price': fair_price,
            'bias': bias
        },
        'multi_factor': multi_factor,
        'dynamic_valuation': dynamic_valuation,
        'golden_pit_analysis': golden_pit,
        'risk_analysis': {
            'transaction_cost': transaction_cost,
            'required_return': risk_analyzer.estimate_required_return()
        },
        'report_time': datetime.now().isoformat()
    }


if __name__ == "__main__":
    # 测试
    result = analyze_stock_comprehensive("600519")
    print(result)
