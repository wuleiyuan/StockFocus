import httpx
from typing import Dict, List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential

from config import config


class EastMoneyAPI:
    def __init__(self, timeout: int = None, retry_count: int = None):
        self.timeout = timeout or config.REQUEST_TIMEOUT
        self.retry_count = retry_count or config.RETRY_COUNT
        self.client = httpx.Client(timeout=self.timeout)
    
    def _get_secid(self, symbol: str) -> str:
        prefix = "1" if symbol.startswith(("6", "9")) else "0"
        return f"{prefix}.{symbol}"
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def fetch_realtime(self, symbol: str) -> Optional[Dict]:
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
                    "price": (data.get("f43") or 0) / 100,
                    "name": data.get("f58", ""),
                    "mkt_cap": data.get("f20", 0),
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
                    "price": item.get("f2", 0) / 100 if item.get("f2") != "-" else 0,
                    "name": item.get("f14", ""),
                    "mkt_cap": item.get("f20", 0),
                    "industry": item.get("f100", "")
                }
            return results
            
        except httpx.HTTPError as e:
            config.setup_logging().error(f"HTTP error in batch fetch: {e}")
        except Exception as e:
            config.setup_logging().error(f"Error in batch fetch: {e}")
        return {}
    
    def __del__(self):
        if hasattr(self, 'client'):
            self.client.close()


api_client = EastMoneyAPI()
