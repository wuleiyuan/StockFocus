from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
from datetime import datetime


class ValidationError(Exception):
    pass


class DataValidator:
    @staticmethod
    def validate_stock_symbol(symbol: str) -> Tuple[bool, Optional[str]]:
        if not symbol:
            return False, "Symbol cannot be empty"
        if not isinstance(symbol, str):
            return False, "Symbol must be a string"
        if not symbol.isdigit():
            return False, "Symbol must contain only digits"
        if len(symbol) not in [6, 8]:
            return False, "Symbol must be 6 or 8 digits"
        return True, None
    
    @staticmethod
    def validate_price(price: Any) -> Tuple[bool, Optional[str]]:
        try:
            p = float(price)
            if p <= 0:
                return False, "Price must be positive"
            if p > 100000:
                return False, "Price seems unrealistic"
            return True, None
        except (TypeError, ValueError):
            return False, "Price must be a number"
    
    @staticmethod
    def validate_roe(roe: Any) -> Tuple[bool, Optional[str]]:
        try:
            r = float(roe)
            if r < -100 or r > 100:
                return False, "ROE must be between -100% and 100%"
            return True, None
        except (TypeError, ValueError):
            return False, "ROE must be a number"
    
    @staticmethod
    def validate_bias(bias: Any) -> Tuple[bool, Optional[str]]:
        try:
            b = float(bias)
            if b < -50 or b > 500:
                return False, "Bias out of expected range (-50% to 500%)"
            return True, None
        except (TypeError, ValueError):
            return False, "Bias must be a number"
    
    @classmethod
    def validate_stock_row(cls, row: Dict) -> List[str]:
        errors = []
        
        if 'symbol' in row:
            valid, err = cls.validate_stock_symbol(row['symbol'])
            if not valid:
                errors.append(f"symbol: {err}")
        
        if 'current_price' in row:
            valid, err = cls.validate_price(row['current_price'])
            if not valid:
                errors.append(f"current_price: {err}")
        
        if 'fair_price' in row:
            valid, err = cls.validate_price(row['fair_price'])
            if not valid:
                errors.append(f"fair_price: {err}")
        
        if 'roe_5y' in row:
            valid, err = cls.validate_roe(row['roe_5y'])
            if not valid:
                errors.append(f"roe_5y: {err}")
        
        if 'bias' in row:
            valid, err = cls.validate_bias(row['bias'])
            if not valid:
                errors.append(f"bias: {err}")
        
        return errors
    
    @classmethod
    def validate_dataframe(cls, df: pd.DataFrame) -> Dict:
        result = {
            'is_valid': True,
            'total_rows': len(df),
            'valid_rows': 0,
            'invalid_rows': 0,
            'errors': []
        }
        
        for idx, row in df.iterrows():
            errors = cls.validate_stock_row(row.to_dict())
            if errors:
                result['is_valid'] = False
                result['invalid_rows'] += 1
                result['errors'].append({
                    'row': idx,
                    'symbol': row.get('symbol', 'unknown'),
                    'errors': errors
                })
            else:
                result['valid_rows'] += 1
        
        return result
    
    @staticmethod
    def sanitize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        numeric_cols = ['current_price', 'fair_price', 'roe_5y', 'bias', 'mkt_cap']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        if 'bias' in df.columns:
            df.loc[df['bias'] > 500, 'bias'] = 500
            df.loc[df['bias'] < -50, 'bias'] = -50
        
        if 'roe_5y' in df.columns:
            df.loc[df['roe_5y'] > 100, 'roe_5y'] = 100
            df.loc[df['roe_5y'] < -100, 'roe_5y'] = -100
        
        if 'current_price' in df.columns:
            df.loc[df['current_price'] <= 0, 'current_price'] = 0
        
        return df


def validate_stock_data(data: Dict) -> Tuple[bool, List[str]]:
    validator = DataValidator()
    errors = validator.validate_stock_row(data)
    return len(errors) == 0, errors


def sanitize_stock_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    return DataValidator.sanitize_dataframe(df)
