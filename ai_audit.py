from typing import Dict, List, Optional
from datetime import datetime
import pandas as pd

from valuation import (
    calculate_dynamic_fair_price,
    calculate_bias_with_dynamic_price,
    calculate_golden_pit_score,
    get_industry_pe_range
)
from risk_analyzer import RiskAnalyzer


class AIAuditor:
    def __init__(self):
        self.risk_analyzer = RiskAnalyzer()
    
    def audit_stock(self, stock_data: Dict, eps: float = None) -> Dict:
        symbol = stock_data.get('symbol', '')
        name = stock_data.get('name', '')
        current_price = float(stock_data.get('current_price', 0))
        fair_price = float(stock_data.get('fair_price', 0))
        roe_5y = float(stock_data.get('roe_5y', 0))
        industry = stock_data.get('industry', '')
        bias = float(stock_data.get('bias', 0))
        
        pe_range = get_industry_pe_range(industry)
        
        if eps is None and fair_price > 0:
            eps = fair_price / pe_range['mid']
        
        valuation = calculate_dynamic_fair_price(eps=eps or 1, industry=industry)
        bias_analysis = calculate_bias_with_dynamic_price(current_price, valuation)
        
        golden_pit = calculate_golden_pit_score(
            current_price=current_price,
            fair_price_mid=valuation['fair_price_mid'],
            roe_5y=roe_5y
        )
        
        golden_pit['is_golden_pit'] = golden_pit['score'] >= 60
        
        risk = self.risk_analyzer.calculate_risk_summary(
            symbol=symbol,
            current_price=current_price,
            industry=industry
        )
        
        overall_score = self._calculate_overall_score(
            golden_pit['score'],
            risk['risk_score'],
            roe_5y
        )
        
        recommendation = self._generate_recommendation(
            golden_pit,
            risk,
            bias_analysis,
            roe_5y
        )
        
        return {
            'symbol': symbol,
            'name': name,
            'audit_time': datetime.now().isoformat(),
            'valuation': {
                'current_price': current_price,
                'fair_price_low': valuation['fair_price_low'],
                'fair_price_mid': valuation['fair_price_mid'],
                'fair_price_high': valuation['fair_price_high'],
                'industry': industry,
                'industry_pe_info': pe_range
            },
            'bias_analysis': bias_analysis,
            'golden_pit': golden_pit,
            'risk': {
                'risk_score': risk['risk_score'],
                'overall_assessment': risk['overall_assessment'],
                'beta': risk['beta'],
                'var': risk['var'],
                'max_drawdown': risk['max_drawdown']
            },
            'quality': {
                'roe_5y': roe_5y,
                'roe_level': self._get_roe_level(roe_5y)
            },
            'overall_score': overall_score,
            'recommendation': recommendation
        }
    
    def audit_dataframe(self, df: pd.DataFrame) -> List[Dict]:
        results = []
        for _, row in df.iterrows():
            audit = self.audit_stock(row.to_dict())
            results.append(audit)
        return results
    
    def _calculate_overall_score(self, golden_pit_score: int, risk_score: int, roe: float) -> int:
        score = 0
        score += golden_pit_score * 0.4
        score += (100 - risk_score) * 0.3
        
        if roe >= 25:
            score += 30
        elif roe >= 20:
            score += 25
        elif roe >= 15:
            score += 20
        else:
            score += 10
        
        return min(100, max(0, int(score)))
    
    def _get_roe_level(self, roe: float) -> str:
        if roe >= 25:
            return "优秀"
        elif roe >= 20:
            return "良好"
        elif roe >= 15:
            return "一般"
        else:
            return "较差"
    
    def _generate_recommendation(self, golden_pit: Dict, risk: Dict, bias_analysis: Dict, roe: float) -> Dict:
        reasons = []
        action = "持有"
        confidence = "中"
        
        if golden_pit['is_golden_pit']:
            reasons.extend(golden_pit['reasons'])
            action = "买入"
            confidence = golden_pit['confidence']
        
        if bias_analysis.get('valuation_status') in ['显著低估', '轻微低估']:
            reasons.append(f"估值{bias_analysis['valuation_status']}")
            if action != "买入":
                action = "关注"
        
        if roe >= 20:
            reasons.append(f"高ROE({roe:.1f}%)")
        
        if risk['risk_score'] > 70:
            reasons.append(f"风险较高(评分{risk['risk_score']})")
            if action == "买入":
                action = "谨慎买入"
        
        return {
            'action': action,
            'confidence': confidence,
            'reasons': reasons[:5],
            'summary': " | ".join(reasons[:3]) if reasons else "无明显信号"
        }


def audit_stock(symbol: str, stock_data: Dict, eps: float = None) -> Dict:
    auditor = AIAuditor()
    return auditor.audit_stock(stock_data, eps)


def audit_stock_list(df: pd.DataFrame) -> List[Dict]:
    auditor = AIAuditor()
    return auditor.audit_dataframe(df)
