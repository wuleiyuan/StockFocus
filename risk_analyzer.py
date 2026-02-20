import numpy as np
from typing import Dict, Optional
from datetime import datetime


INDUSTRY_BETA_MAP = {
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

DEFAULT_MARKET_VOLATILITY = 0.20
DEFAULT_ANNUAL_VOLATILITY = 0.25


class RiskAnalyzer:
    def __init__(self, engine=None):
        self.engine = engine
    
    def calculate_beta(
        self,
        symbol: str = None,
        industry: str = None,
        historical_volatility: float = None,
        market_volatility: float = DEFAULT_MARKET_VOLATILITY
    ) -> Dict:
        if historical_volatility and market_volatility:
            beta = historical_volatility / market_volatility
        elif industry:
            beta = INDUSTRY_BETA_MAP.get(industry, 1.0)
        else:
            beta = 1.0
        
        beta = round(beta, 2)
        
        if beta >= 1.3:
            interpretation = "高波动"
            risk_level = "高"
            emoji = "🔴"
        elif beta >= 1.0:
            interpretation = "市场同步"
            risk_level = "中"
            emoji = "🟡"
        elif beta >= 0.8:
            interpretation = "低波动"
            risk_level = "低"
            emoji = "🟢"
        else:
            interpretation = "防御性"
            risk_level = "很低"
            emoji = "🔵"
        
        return {
            'beta': beta,
            'interpretation': interpretation,
            'risk_level': risk_level,
            'color_emoji': emoji,
            'market_volatility_assumption': market_volatility
        }
    
    def calculate_var(
        self,
        symbol: str,
        current_price: float,
        confidence_level: float = 0.95,
        holding_period: int = 1,
        volatility: float = None
    ) -> Dict:
        if volatility is None:
            volatility = DEFAULT_ANNUAL_VOLATILITY
        
        z_scores = {0.95: 1.645, 0.99: 2.326}
        z_score = z_scores.get(confidence_level, 1.645)
        
        daily_vol = volatility / np.sqrt(252)
        time_factor = np.sqrt(holding_period)
        
        var_abs = current_price * z_score * daily_vol * time_factor
        var_pct = (var_abs / current_price) * 100
        
        return {
            'confidence_level': f"{confidence_level * 100}%",
            'holding_period_days': holding_period,
            'var_absolute': round(var_abs, 2),
            'var_percentage': round(var_pct, 2),
            'var_10k_position': round(10000 / current_price * var_pct / 100, 2),
            'var_100k_position': round(100000 / current_price * var_pct / 100, 2),
            'assumed_volatility': f"{volatility * 100:.0f}%",
            'interpretation': self._var_interpretation(var_pct)
        }
    
    def _var_interpretation(self, var_pct: float) -> str:
        if var_pct <= 2:
            return "✅ 低风险 - 正常波动范围内"
        elif var_pct <= 4:
            return "⚠️ 中等风险 - 需关注波动"
        elif var_pct <= 6:
            return "🔶 较高风险 - 波动显著"
        else:
            return "🔴 高风险 - 波动剧烈，谨慎持有"
    
    def calculate_max_drawdown(
        self,
        symbol: str,
        current_price: float,
        peak_price: float = None
    ) -> Dict:
        if peak_price is None:
            peak_price = current_price * 1.3
        
        mdd_pct = ((peak_price - current_price) / peak_price) * 100
        
        if mdd_pct <= 10:
            interpretation = "📈 创新高或接近新高"
            color = "🟢"
        elif mdd_pct <= 20:
            interpretation = "📊 正常回撤范围"
            color = "🟡"
        elif mdd_pct <= 30:
            interpretation = "📉 较大回撤，需关注"
            color = "🟠"
        else:
            interpretation = "⚠️ 深幅回撤，风险较高"
            color = "🔴"
        
        return {
            'current_price': current_price,
            'peak_price_assumption': peak_price,
            'max_drawdown_pct': round(mdd_pct, 2),
            'interpretation': interpretation,
            'color': color
        }
    
    def calculate_sharpe_ratio(
        self,
        expected_return: float,
        risk_free_rate: float = 0.03,
        volatility: float = 0.20
    ) -> Dict:
        excess_return = expected_return - risk_free_rate
        sharpe = excess_return / volatility
        
        if sharpe >= 1.5:
            interpretation = "⭐⭐⭐ 优秀"
            color = "🟢"
        elif sharpe >= 1.0:
            interpretation = "⭐⭐ 良好"
            color = "🟢"
        elif sharpe >= 0.5:
            interpretation = "⭐ 一般"
            color = "🟡"
        else:
            interpretation = "⚠️ 较差"
            color = "🔴"
        
        return {
            'sharpe_ratio': round(sharpe, 2),
            'excess_return_pct': round(excess_return * 100, 2),
            'volatility_pct': round(volatility * 100, 2),
            'interpretation': interpretation,
            'color': color
        }
    
    def calculate_risk_summary(
        self,
        symbol: str,
        current_price: float,
        expected_return: float = 0.15,
        industry: str = None
    ) -> Dict:
        beta_data = self.calculate_beta(symbol, industry)
        var_data = self.calculate_var(symbol, current_price)
        mdd_data = self.calculate_max_drawdown(symbol, current_price)
        sharpe_data = self.calculate_sharpe_ratio(expected_return)
        
        risk_score = 0
        risk_score += beta_data['beta'] * 20
        risk_score += var_data['var_percentage'] * 3
        risk_score += mdd_data['max_drawdown_pct'] * 0.5
        risk_score += max(0, 10 - sharpe_data['sharpe_ratio'] * 3)
        
        risk_score = min(100, max(0, round(risk_score, 1)))
        
        if risk_score <= 30:
            overall = "🟢 低风险"
        elif risk_score <= 50:
            overall = "🟡 中低风险"
        elif risk_score <= 70:
            overall = "🟠 中高风险"
        else:
            overall = "🔴 高风险"
        
        return {
            'symbol': symbol,
            'risk_score': risk_score,
            'overall_assessment': overall,
            'beta': beta_data,
            'var': var_data,
            'max_drawdown': mdd_data,
            'sharpe_ratio': sharpe_data,
            'timestamp': datetime.now().isoformat()
        }
    
    def calculate_transaction_cost(
        self,
        price: float,
        shares: int = 1000,
        fee_rate: float = 0.001,
        stamp_rate: float = 0.001,
        slippage_rate: float = 0.002
    ) -> Dict:
        turnover = price * shares
        commission = max(turnover * fee_rate, 5)
        stamp_tax = turnover * stamp_rate * 0.5
        slippage = turnover * slippage_rate
        
        total_cost = commission + stamp_tax + slippage
        
        return {
            'turnover': round(turnover, 2),
            'commission': round(commission, 2),
            'stamp_tax': round(stamp_tax, 2),
            'slippage': round(slippage, 2),
            'total_cost': round(total_cost, 2),
            'cost_ratio': round(total_cost / turnover * 100, 3),
            'effective_buy_price': round(price * (1 + slippage_rate), 2),
            'effective_sell_price': round(price * (1 - slippage_rate - stamp_rate), 2)
        }
    
    def estimate_required_return(
        self,
        beta: float = 1.0,
        risk_free_rate: float = 0.03,
        market_premium: float = 0.06
    ) -> float:
        return round((risk_free_rate + beta * market_premium) * 100, 2)
