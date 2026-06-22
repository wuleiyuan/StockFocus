import httpx
import time
from typing import Dict, List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential
from collections import deque

from config import config

_clients: Dict[int, httpx.Client] = {}
_request_times = deque(maxlen=100)
RATE_LIMIT = 20
RATE_WINDOW = 60

def check_rate_limit():
    now = time.time()
    while _request_times and _request_times[0] < now - RATE_WINDOW:
        _request_times.popleft()
    
    if len(_request_times) >= RATE_LIMIT:
        wait_time = RATE_WINDOW - (now - _request_times[0])
        if wait_time > 0:
            time.sleep(wait_time)
    
    _request_times.append(time.time())


def _get_value(obj, key: str, default=0):
    """Safely extract numeric value from API response field.
    
    East Money API returns some fields as strings (e.g. "-" for N/A),
    others as numbers. This normalizes to a float.
    """
    val = obj.get(key, default)
    if val is None or val == "-" or val == "--" or val == "":
        return 0.0
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


class EastMoneyAPI:
    def __init__(self, timeout: int = None, retry_count: int = None):
        self.timeout = timeout or config.REQUEST_TIMEOUT
        self.retry_count = retry_count or config.RETRY_COUNT
        # Use per-timeout client cache instead of single global
        if self.timeout not in _clients:
            _clients[self.timeout] = httpx.Client(timeout=self.timeout)
        self.client = _clients[self.timeout]
    
    def _get_secid(self, symbol: str) -> str:
        prefix = "1" if symbol.startswith(("6", "9")) else "0"
        return f"{prefix}.{symbol}"
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def fetch_realtime(self, symbol: str) -> Optional[Dict]:
        check_rate_limit()
        try:
            secid = self._get_secid(symbol)
            url = "http://push2.eastmoney.com/api/qt/stock/get"
            params = {"secid": secid, "fields": "f43,f58,f20,f100"}
            
            response = self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json().get("data")
            
            if data:
                return {
                    "symbol": symbol,
                    "price": _get_value(data, "f43") / 100,
                    "name": data.get("f58", ""),
                    "mkt_cap": _get_value(data, "f20"),
                    "industry": data.get("f100", "")
                }
        except httpx.HTTPError as e:
            config.setup_logging().error(f"HTTP error fetching {symbol}: {e}")
        except Exception as e:
            config.setup_logging().error(f"Error fetching {symbol}: {e}")
        return None
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def fetch_realtime_batch(self, symbols: List[str]) -> Dict[str, Dict]:
        if not symbols:
            return {}
        
        check_rate_limit()
        secids = [self._get_secid(s) for s in symbols]
        
        try:
            url = "http://push2.eastmoney.com/api/qt/ulist.np/get"
            params = {"secids": ",".join(secids), "fields": "f12,f14,f2,f20,f100"}
            
            response = self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json().get("data", {}).get("diff", [])
            
            results = {}
            for item in data:
                symbol = item.get("f12", "")
                results[symbol] = {
                    "symbol": symbol,
                    "price": _get_value(item, "f2") / 100,
                    "name": item.get("f14", ""),
                    "mkt_cap": _get_value(item, "f20"),
                    "industry": item.get("f100", "")
                }
            return results
            
        except httpx.HTTPError as e:
            config.setup_logging().error(f"HTTP error in batch fetch: {e}")
        except Exception as e:
            config.setup_logging().error(f"Error in batch fetch: {e}")
        return {}


api_client = EastMoneyAPI()
