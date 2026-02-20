import os
import time
import hashlib
import json
import logging
from typing import Any, Callable, Optional, Dict
from functools import wraps

logger = logging.getLogger(__name__)


class CacheConfig:
    DEFAULT_TTL = 300
    STOCK_DATA_TTL = 60
    AI_REPORT_TTL = 3600
    INDUSTRY_DATA_TTL = 1800
    
    _custom_ttls: Dict[str, int] = {}
    
    @classmethod
    def get_ttl(cls, cache_type: str) -> int:
        if cache_type in cls._custom_ttls:
            return cls._custom_ttls[cache_type]
        return getattr(cls, f"{cache_type.upper()}_TTL", cls.DEFAULT_TTL)
    
    @classmethod
    def set_ttl(cls, cache_type: str, ttl: int):
        cls._custom_ttls[cache_type] = ttl
        logger.info(f"Cache TTL updated: {cache_type} = {ttl}s")
    
    @classmethod
    def reset_ttl(cls, cache_type: str = None):
        if cache_type:
            cls._custom_ttls.pop(cache_type, None)
        else:
            cls._custom_ttls.clear()
    
    @classmethod
    def get_all_ttls(cls) -> Dict[str, int]:
        return {
            'default': cls.DEFAULT_TTL,
            'stock_data': cls.STOCK_DATA_TTL,
            'ai_report': cls.AI_REPORT_TTL,
            'industry_data': cls.INDUSTRY_DATA_TTL,
            'custom': cls._custom_ttls.copy()
        }


class MemoryCache:
    def __init__(self):
        self._cache: Dict[str, Dict] = {}
    
    def get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            entry = self._cache[key]
            if time.time() < entry['expires']:
                return entry['value']
            else:
                del self._cache[key]
        return None
    
    def set(self, key: str, value: Any, ttl: int = None):
        ttl = ttl or CacheConfig.DEFAULT_TTL
        self._cache[key] = {
            'value': value,
            'expires': time.time() + ttl,
            'created': time.time()
        }
    
    def delete(self, key: str):
        if key in self._cache:
            del self._cache[key]
    
    def clear(self):
        self._cache.clear()
    
    def cleanup(self):
        now = time.time()
        expired = [k for k, v in self._cache.items() if now >= v['expires']]
        for k in expired:
            del self._cache[k]
    
    def keys(self):
        return list(self._cache.keys())


_global_cache = MemoryCache()


def get_cache() -> MemoryCache:
    return _global_cache


def generate_cache_key(*args, **kwargs) -> str:
    key_data = json.dumps({'args': args, 'kwargs': kwargs}, sort_keys=True, default=str)
    return hashlib.md5(key_data.encode()).hexdigest()


def cached(ttl: int = None, cache_key_prefix: str = ""):
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache = get_cache()
            key_prefix = cache_key_prefix or func.__name__
            key = f"{key_prefix}:{generate_cache_key(*args, **kwargs)}"
            
            cached_value = cache.get(key)
            if cached_value is not None:
                logger.debug(f"Cache hit: {key}")
                return cached_value
            
            result = func(*args, **kwargs)
            cache.set(key, result, ttl)
            logger.debug(f"Cache set: {key}")
            return result
        return wrapper
    return decorator


def invalidate_cache(prefix: str = None):
    cache = get_cache()
    if prefix:
        keys_to_delete = [k for k in cache.keys() if k.startswith(prefix)]
        for k in keys_to_delete:
            cache.delete(k)
    else:
        cache.clear()


class StockDataCache:
    @staticmethod
    def get_stock_price(symbol: str, ttl: int = None) -> Optional[Dict]:
        cache = get_cache()
        ttl = ttl or CacheConfig.get_ttl('stock_data')
        return cache.get(f"stock:{symbol}")
    
    @staticmethod
    def cache_stock_price(symbol: str, data: Dict, ttl: int = None):
        cache = get_cache()
        ttl = ttl or CacheConfig.get_ttl('stock_data')
        cache.set(f"stock:{symbol}", data, ttl)
    
    @staticmethod
    def get_cached_stock_price(symbol: str) -> Optional[Dict]:
        return get_cache().get(f"stock:{symbol}")


class AICache:
    @staticmethod
    def get_ai_report(symbol: str, ttl: int = None) -> Optional[Dict]:
        cache = get_cache()
        ttl = ttl or CacheConfig.get_ttl('ai_report')
        return cache.get(f"ai_report:{symbol}")
    
    @staticmethod
    def cache_ai_report(symbol: str, report: Dict, custom_ttl: int = None):
        cache = get_cache()
        ttl = custom_ttl or CacheConfig.get_ttl('ai_report')
        cache.set(f"ai_report:{symbol}", report, ttl)
    
    @staticmethod
    def get_cached_ai_report(symbol: str) -> Optional[Dict]:
        return get_cache().get(f"ai_report:{symbol}")
    
    @staticmethod
    def invalidate_ai_report(symbol: str = None):
        if symbol:
            get_cache().delete(f"ai_report:{symbol}")
        else:
            invalidate_cache("ai_report")


def get_cache_stats() -> Dict:
    cache = get_cache()
    cache.cleanup()
    return {
        'total_entries': len(cache.keys()),
        'stock_entries': len([k for k in cache.keys() if k.startswith('stock:')]),
        'ai_report_entries': len([k for k in cache.keys() if k.startswith('ai_report:')]),
        'ttl_settings': CacheConfig.get_all_ttls()
    }


class StreamlitCacheHelper:
    @staticmethod
    def render_cache_settings():
        try:
            import streamlit as st
            
            st.sidebar.markdown("### ⚡ 缓存设置")
            
            current_ttls = CacheConfig.get_all_ttls()
            
            ai_ttl = st.sidebar.slider(
                "AI报告缓存时间(秒)",
                min_value=60,
                max_value=7200,
                value=current_ttls.get('ai_report', 3600),
                step=60,
                help="AI报告缓存有效期，过期后重新生成"
            )
            
            if st.sidebar.button("更新AI缓存设置"):
                CacheConfig.set_ttl('ai_report', ai_ttl)
                st.sidebar.success(f"已更新: AI报告缓存 = {ai_ttl}秒")
            
            if st.sidebar.button("清空所有缓存"):
                invalidate_cache()
                st.sidebar.success("缓存已清空")
            
            stats = get_cache_stats()
            st.sidebar.markdown(f"""
            ---
            **缓存状态:**
            - 总条目: {stats['total_entries']}
            - 股票数据: {stats['stock_entries']}
            - AI报告: {stats['ai_report_entries']}
            """)
            
        except ImportError:
            pass
    
    @staticmethod
    def get_ai_report_with_cache(symbol: str, generate_func: Callable, ttl: int = None) -> Dict:
        ttl = ttl or CacheConfig.get_ttl('ai_report')
        
        cached = AICache.get_cached_ai_report(symbol)
        if cached:
            cached['from_cache'] = True
            return cached
        
        report = generate_func(symbol)
        if report:
            AICache.cache_ai_report(symbol, report, ttl)
            report['from_cache'] = False
        return report
