import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
from datetime import datetime
import logging

from config import Config

config = Config()
logger = config.setup_logging()


INDUSTRY_PE_BENCHMARKS = {
    "白酒": {"low": 20, "mid": 28, "high": 35, "description": "消费稳定"},
    "医药": {"low": 20, "mid": 30, "high": 40, "description": "成长性强"},
    "医疗器械": {"low": 25, "mid": 35, "high": 45, "description": "高成长"},
    "医疗服务": {"low": 25, "mid": 35, "high": 45, "description": "高成长"},
    "新能源": {"low": 20, "mid": 30, "high": 40, "description": "周期成长"},
    "光伏": {"low": 15, "mid": 25, "high": 35, "description": "周期性强"},
    "锂电池": {"low": 20, "mid": 30, "high": 40, "description": "高成长"},
    "半导体": {"low": 30, "mid": 45, "high": 60, "description": "高估值"},
    "芯片": {"low": 30, "mid": 45, "high": 60, "description": "高估值"},
    "软件服务": {"low": 25, "mid": 40, "high": 55, "description": "轻资产"},
    "互联网": {"low": 20, "mid": 35, "high": 50, "description": "平台型"},
    "银行": {"low": 4, "mid": 6, "high": 8, "description": "周期低估值"},
    "保险": {"low": 8, "mid": 12, "high": 16, "description": "金融周期"},
    "证券": {"low": 10, "mid": 18, "high": 25, "description": "周期性强"},
    "房地产": {"low": 5, "mid": 8, "high": 12, "description": "周期低估值"},
    "建筑": {"low": 5, "mid": 8, "high": 12, "description": "周期低估值"},
    "钢铁": {"low": 5, "mid": 8, "high": 12, "description": "强周期"},
    "煤炭": {"low": 6, "mid": 10, "high": 15, "description": "强周期"},
    "有色金属": {"low": 10, "mid": 15, "high": 22, "description": "强周期"},
    "化工": {"low": 10, "mid": 15, "high": 22, "description": "周期中"},
    "汽车": {"low": 10, "mid": 18, "high": 25, "description": "周期制造"},
    "家电": {"low": 12, "mid": 18, "high": 25, "description": "消费稳定"},
    "食品饮料": {"low": 18, "mid": 25, "high": 32, "description": "消费稳定"},
    "纺织服装": {"low": 12, "mid": 18, "high": 25, "description": "传统消费"},
    "零售": {"low": 15, "mid": 22, "high": 30, "description": "渠道为王"},
    "物流": {"low": 15, "mid": 22, "high": 30, "description": "服务型"},
    "航空": {"low": 15, "mid": 25, "high": 35, "description": "强周期"},
    "旅游": {"low": 18, "mid": 28, "high": 38, "description": "疫情周期"},
    "传媒": {"low": 15, "mid": 25, "high": 35, "description": "内容驱动"},
    "环保": {"low": 15, "mid": 22, "high": 30, "description": "政策驱动"},
    "军工": {"low": 40, "mid": 55, "high": 70, "description": "高估值非市场"},
    "电力": {"low": 10, "mid": 15, "high": 20, "description": "公用事业"},
    "公用事业": {"low": 10, "mid": 15, "high": 20, "description": "稳定低波"},
    " default": {"low": 12, "mid": 18, "high": 25, "description": "通用"}
}


def get_industry_pe_range(industry: str) -> Dict:
    if not industry:
        return INDUSTRY_PE_BENCHMARKS[" default"]
    
    for key in INDUSTRY_PE_BENCHMARKS:
        if key != " default" and key in industry:
            return INDUSTRY_PE_BENCHMARKS[key]
    
    return INDUSTRY_PE_BENCHMARKS[" default"]


def calculate_historical_pe_percentile(current_pe: float, pe_history: list) -> float:
    if not pe_history or len(pe_history) < 3:
        return 0.5
    
    pe_series = pd.Series(pe_history)
    percentile = (pe_series < current_pe).sum() / len(pe_series)
    return percentile


def calculate_dynamic_fair_price(
    eps: float,
    industry: str = None,
    market_cycle: str = "neutral"
) -> Dict:
    pe_range = get_industry_pe_range(industry)
    
    market_adjustment = {
        "bull": 1.1,
        "neutral": 1.0,
        "bear": 0.9
    }.get(market_cycle, 1.0)
    
    adjusted_mid_pe = pe_range["mid"] * market_adjustment
    adjusted_low_pe = pe_range["low"] * market_adjustment
    adjusted_high_pe = pe_range["high"] * market_adjustment
    
    fair_price_low = eps * adjusted_low_pe
    fair_price_mid = eps * adjusted_mid_pe
    fair_price_high = eps * adjusted_high_pe
    
    return {
        "eps": eps,
        "industry": industry or "未知",
        "industry_info": pe_range,
        "market_cycle": market_cycle,
        "fair_price_low": round(fair_price_low, 2),
        "fair_price_mid": round(fair_price_mid, 2),
        "fair_price_high": round(fair_price_high, 2),
        "pe_low": adjusted_low_pe,
        "pe_mid": adjusted_mid_pe,
        "pe_high": adjusted_high_pe,
        "calculation_time": datetime.now().isoformat()
    }


def calculate_bias_with_dynamic_price(
    current_price: float,
    dynamic_valuation: Dict
) -> Dict:
    fair_price_mid = dynamic_valuation["fair_price_mid"]
    fair_price_low = dynamic_valuation["fair_price_low"]
    fair_price_high = dynamic_valuation["fair_price_high"]
    
    bias_mid = ((current_price - fair_price_mid) / fair_price_mid * 100) if fair_price_mid > 0 else 0
    bias_low = ((current_price - fair_price_low) / fair_price_low * 100) if fair_price_low > 0 else 0
    bias_high = ((current_price - fair_price_high) / fair_price_high * 100) if fair_price_high > 0 else 0
    
    if current_price < fair_price_low:
        valuation_status = "显著低估"
        signal = "黄金坑"
    elif current_price < fair_price_mid:
        valuation_status = "轻微低估"
        signal = "建议关注"
    elif current_price < fair_price_high:
        valuation_status = "合理区间"
        signal = "持有"
    else:
        valuation_status = "高估"
        signal = "风险警示"
    
    return {
        "current_price": current_price,
        "bias_mid_pct": round(bias_mid, 2),
        "bias_low_pct": round(bias_low, 2),
        "bias_high_pct": round(bias_high, 2),
        "valuation_status": valuation_status,
        "investment_signal": signal
    }


def get_recommended_pe(industry: str, roe_level: str) -> float:
    pe_range = get_industry_pe_range(industry)
    
    roe_adjustment = {
        "excellent": 1.2,
        "good": 1.0,
        "average": 0.85,
        "poor": 0.7
    }.get(roe_level, 1.0)
    
    return pe_range["mid"] * roe_adjustment


def calculate_golden_pit_score(
    current_price: float,
    fair_price_mid: float,
    roe_5y: float,
    peg: float = None,
    dividend_yield: float = None
) -> Dict:
    bias = ((current_price - fair_price_mid) / fair_price_mid * 100) if fair_price_mid > 0 else 0
    
    score = 0
    reasons = []
    
    if bias < -20:
        score += 40
        reasons.append(f"深度低估({bias:.1f}%)")
    elif bias < -15:
        score += 30
        reasons.append(f"显著低估({bias:.1f}%)")
    elif bias < -10:
        score += 20
        reasons.append(f"轻微低估({bias:.1f}%)")
    elif bias < -5:
        score += 10
        reasons.append(f"接近低估({bias:.1f}%)")
    
    if roe_5y >= 25:
        score += 30
        reasons.append(f"优秀ROE({roe_5y:.1f}%)")
    elif roe_5y >= 20:
        score += 20
        reasons.append(f"良好ROE({roe_5y:.1f}%)")
    elif roe_5y >= 15:
        score += 10
        reasons.append(f"达标ROE({roe_5y:.1f}%)")
    
    if peg is not None and peg < 0.8:
        score += 20
        reasons.append(f"低PEG({peg:.2f})")
    elif peg is not None and peg < 1.0:
        score += 10
        reasons.append(f"合理PEG({peg:.2f})")
    
    if dividend_yield is not None and dividend_yield > 3:
        score += 15
        reasons.append(f"高股息({dividend_yield:.1f}%)")
    elif dividend_yield is not None and dividend_yield > 1.5:
        score += 8
        reasons.append(f"有股息({dividend_yield:.1f}%)")
    
    if score >= 80:
        recommendation = "⭐⭐⭐ 强烈推荐"
        confidence = "高"
    elif score >= 60:
        recommendation = "⭐⭐ 推荐关注"
        confidence = "中"
    elif score >= 40:
        recommendation = "⭐ 可考虑"
        confidence = "低"
    else:
        recommendation = "⏸️ 暂不推荐"
        confidence = "很低"
    
    return {
        "score": score,
        "bias_pct": round(bias, 2),
        "roe_5y": roe_5y,
        "peg": peg,
        "dividend_yield": dividend_yield,
        "reasons": reasons,
        "recommendation": recommendation,
        "confidence": confidence
    }
