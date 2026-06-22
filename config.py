"""
StockFocus 配置模块 (V2.0)
统一管理所有配置项，支持环境变量和默认值
增强版：数据库稳定性、多因子模型支持、风险指标计算
"""
import os
import logging
import time
import random
from dotenv import load_dotenv
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text, event
from sqlalchemy.pool import QueuePool

# 加载环境变量
load_dotenv()

class Config:
    """配置类 - 统一管理所有配置"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        
        self.POSTGRES_DB = os.getenv('POSTGRES_DB', 'stock_data')
        self.POSTGRES_USER = os.getenv('POSTGRES_USER')
        self.POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD')
        self.DB_HOST = os.getenv('DB_HOST', 'localhost')
        self.DB_PORT = int(os.getenv('DB_PORT', '5432'))
        
        if not self.POSTGRES_USER or not self.POSTGRES_PASSWORD:
            raise ValueError("POSTGRES_USER and POSTGRES_PASSWORD must be set in .env file")
    
    # 📊 应用配置
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    REFRESH_INTERVAL = int(os.getenv('REFRESH_INTERVAL', '10'))
    BATCH_SIZE = int(os.getenv('BATCH_SIZE', '50'))
    
    # 🌐 网络配置
    REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '5'))
    RETRY_COUNT = int(os.getenv('RETRY_COUNT', '3'))
    NO_PROXY = os.getenv('NO_PROXY', '*')
    
    # 📈 估值配置
    DEFAULT_PE = float(os.getenv('DEFAULT_PE', '15'))  # 默认PE倍数
    GOLDEN_PIT_THRESHOLD = float(os.getenv('GOLDEN_PIT_THRESHOLD', '-15'))  # 黄金坑阈值
    OVERVALUED_THRESHOLD = float(os.getenv('OVERVALUED_THRESHOLD', '20'))  # 高估阈值
    
    # 💰 交易成本配置
    TRANSACTION_FEE_RATE = float(os.getenv('TRANSACTION_FEE_RATE', '0.001'))  # 佣金费率
    STAMP_TAX_RATE = float(os.getenv('STAMP_TAX_RATE', '0.001'))  # 印花税
    SLIPPAGE_RATE = float(os.getenv('SLIPPAGE_RATE', '0.002'))  # 滑点成本
    
    @property
    def database_url(self):
        password = quote_plus(self.POSTGRES_PASSWORD)
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{password}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.POSTGRES_DB}"
            f"?sslmode=disable&gssencmode=disable"
        )
    
    def setup_logging(self):
        """设置日志配置"""
        logging.basicConfig(
            level=getattr(logging, self.LOG_LEVEL.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(__name__)


class DatabaseManager:
    """增强版数据库连接管理 - 稳定性优化"""
    
    _instance = None
    
    def __new__(cls, config=None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, config=None):
        if self._initialized:
            return
        self.config = config or Config()
        self._engine = None
        self._connection_retries = 3
        self._base_delay = 1
        self._max_delay = 30
        self._backoff_factor = 2
        self._jitter = 0.3
        self._initialized = True
    
    def _get_backoff_delay(self, attempt):
        delay = min(self._base_delay * (self._backoff_factor ** attempt), self._max_delay)
        jitter = delay * self._jitter * (2 * random.random() - 1)
        return delay + jitter
    
    @property
    def engine(self):
        """获取数据库引擎（增强稳定性）"""
        if self._engine is None:
            self._engine = create_engine(
                self.config.database_url,
                poolclass=QueuePool,
                pool_size=5,  # 减少连接数，提高稳定性
                max_overflow=10,
                pool_pre_ping=True,  # 连接前检查
                pool_recycle=1800,  # 30分钟回收
                pool_timeout=30,  # 获取连接超时
                echo=False
            )
            
            # 添加连接事件监听
            @event.listens_for(self._engine, "connect")
            def on_connect(dbapi_connection, connection_record):
                # 设置连接参数，提高稳定性
                dbapi_connection.set_session(autocommit=False)
            
            # 添加断开重连监听
            @event.listens_for(self._engine, "engine_disposed")
            def on_dispose(engine):
                logging.warning("数据库连接池已销毁，尝试重新创建...")
                self._engine = None
        
        return self._engine
    
    def test_connection(self):
        """增强版连接测试 - 带指数退避"""
        for attempt in range(self._connection_retries):
            try:
                with self.engine.connect() as conn:
                    result = conn.execute(text("SELECT 1"))
                    result.fetchone()
                logging.info("✅ 数据库连接测试成功")
                return True
            except Exception as e:
                logging.warning(f"🔄 数据库连接尝试 {attempt + 1} 失败: {e}")
                if attempt < self._connection_retries - 1:
                    delay = self._get_backoff_delay(attempt)
                    logging.info(f"⏳ 等待 {delay:.1f} 秒后重试...")
                    time.sleep(delay)
                else:
                    logging.error(f"❌ 数据库连接最终失败: {e}")
                    return False
        return False
    
    def execute_with_retry(self, query, params=None, max_retries=3):
        """带指数退避的查询执行"""
        for attempt in range(max_retries):
            try:
                with self.engine.begin() as conn:
                    if params:
                        result = conn.execute(text(query), params)
                    else:
                        result = conn.execute(text(query))
                    return result
            except Exception as e:
                logging.warning(f"⚠️ 查询执行尝试 {attempt + 1} 失败: {e}")
                if attempt < max_retries - 1:
                    delay = self._get_backoff_delay(attempt)
                    time.sleep(delay)
                else:
                    raise e

# 全局配置实例
config = Config()
database = DatabaseManager(config)

def get_db_engine():
    return database.engine

def setup_network_config():
    for k in list(os.environ.keys()):
        if "proxy" in k.lower():
            os.environ.pop(k, None)
    os.environ["NO_PROXY"] = config.NO_PROXY

_config = None
_database = None

def get_config():
    global _config
    if _config is None:
        _config = Config()
    return _config

def get_database():
    global _database
    if _database is None:
        _database = DatabaseManager(get_config())
    return _database