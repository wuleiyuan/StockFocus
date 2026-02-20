# StockFocus Pro 量化投研系统 - 完整文档

## 一、系统概述

StockFocus Pro 是一套基于 Python 的全栈量化投研系统，专注于 A 股市场的价值投资分析。系统完全复刻了经典的价值投资体系，并将其数字化、自动化。

### 核心投资理念

| 理念 | 说明 |
|------|------|
| **估值锚点** | 合理价格 = EPS × 行业PE (动态) |
| **质量筛选** | 连续多年 ROE > 15% |
| **安全边际** | 股价低于合理价 15% 以上为"黄金坑" |
| **市值认知** | 50亿/200亿/400亿 不同增长逻辑 |

---

## 二、快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone <repository-url>
cd StockFocus

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 复制环境配置
cp .env.example .env
# 编辑 .env 填入数据库账号密码
```

### 2. 启动服务

```bash
# 方式一: Docker 一键部署
docker-compose up -d

# 方式二: 本地开发
docker-compose up -d db              # 启动数据库
python main.py scan                  # 初始化扫描
python main.py etl-pipeline --continuous  # 启动ETL
python main.py web                   # 启动Web界面
```

### 3. 访问系统

- Web界面: http://localhost:8501
- 数据库: localhost:5432

---

## 三、命令行工具

### 3.1 股票扫描

```bash
# 扫描高质量股票 (ROE >= 15%, 分析10年)
python main.py scan

# 自定义参数
python main.py scan --roe-threshold 18 --max-stocks 100 --years 5
```

参数说明:
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--roe-threshold` | 15.0 | ROE筛选阈值 |
| `--years` | 10 | ROE分析年数 |
| `--max-stocks` | 200 | 最大扫描数量 |
| `--debug` | False | 调试模式 |

### 3.2 后端服务

```bash
# 启动后端价格更新服务
python main.py backend

# 自定义刷新间隔
python main.py backend --refresh-interval 5 --debug
```

### 3.3 ETL管道

```bash
# 单次ETL执行
python main.py etl-pipeline

# 持续运行模式
python main.py etl-pipeline --continuous --interval 60

# 指定股票代码
python main.py etl-pipeline --symbols 600519,000858 --continuous
```

参数说明:
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--continuous` | False | 持续运行模式 |
| `--interval` | 60 | 循环间隔(秒) |
| `--max-iterations` | 无限 | 最大迭代次数 |
| `--symbols` | 全部 | 指定股票列表 |

### 3.4 Web界面

```bash
# 启动Web界面
python main.py web

# 调试模式
python main.py web --debug --log-level DEBUG
```

---

## 四、模块说明

### 4.1 核心模块

| 文件 | 功能 |
|------|------|
| `main.py` | 命令行入口 |
| `config.py` | 配置管理 |
| `stock_api.py` | 东方财富API封装 |
| `valuation.py` | 动态估值模型 |
| `risk_analyzer.py` | 风险分析 |
| `report_generator.py` | PDF报告生成 |
| `validators.py` | 数据校验 |
| `cache_utils.py` | 缓存管理 |
| `etl_pipeline.py` | 专业ETL管道 |

### 4.2 业务模块

| 文件 | 功能 |
|------|------|
| `stock_scanner.py` | 股票质量扫描器 |
| `backend_service.py` | 后端数据服务 |
| `backend_etl.py` | ETL数据处理 |
| `evaluation_models.py` | 多因子评估模型 |
| `app_web.py` | Streamlit Web界面 |

---

## 五、估值模型

### 5.1 动态行业PE

系统内置32个行业PE基准:

```python
# valuation.py
INDUSTRY_PE_BENCHMARKS = {
    "白酒": {"low": 20, "mid": 28, "high": 35},
    "医药": {"low": 20, "mid": 30, "high": 40},
    "银行": {"low": 4, "mid": 6, "high": 8},
    "半导体": {"low": 30, "mid": 45, "high": 60},
    ...
}
```

### 5.2 黄金坑判定

```python
calculate_golden_pit_score(
    current_price=55,
    fair_price_mid=70,
    roe_5y=22.5,
    peg=0.8,
    dividend_yield=2.5
)
# 返回: score=80, recommendation="⭐⭐⭐ 强烈推荐"
```

评分规则:
- 深度低估(bias < -20%): +40分
- 高ROE(>= 25%): +30分
- 低PEG(< 0.8): +20分
- 高股息(> 3%): +15分

---

## 六、缓存配置

### 6.1 Web界面配置

在Web侧边栏可以实时调整:
- AI报告缓存时间 (60-7200秒)
- 清空所有缓存

### 6.2 编程方式

```python
from cache_utils import CacheConfig, AICache, invalidate_cache

# 设置自定义TTL
CacheConfig.set_ttl('ai_report', 1800)  # 30分钟

# 获取带缓存的报告
from cache_utils import StreamlitCacheHelper
report = StreamlitCacheHelper.get_ai_report_with_cache(
    symbol='600519',
    generate_func=generate_ai_report
)
```

---

## 七、ETL管道

### 7.1 架构

```
┌─────────┐    ┌──────────┐    ┌─────────┐
│ Extract │ -> │ Transform│ -> │  Load  │
└─────────┘    └──────────┘    └─────────┘
    (API)        (校验/清洗)    (数据库)
```

### 7.2 使用示例

```python
from etl_pipeline import ETLScheduler, StockPriceETL

# 创建调度器
scheduler = ETLScheduler()

# 添加股票价格ETL
scheduler.add_price_etl(['600519', '000858'])

# 单次执行
results = scheduler.run_once()

# 持续运行
scheduler.run_continuous(interval_seconds=60)
```

---

## 八、配置说明

### 8.1 环境变量 (.env)

```env
# 数据库 (必需)
POSTGRES_DB=stock_data
POSTGRES_USER=admin
POSTGRES_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432

# 应用配置
LOG_LEVEL=INFO
REFRESH_INTERVAL=10
BATCH_SIZE=50

# 网络配置
NO_PROXY=*
REQUEST_TIMEOUT=5
RETRY_COUNT=3
```

### 8.2 命令行参数

所有模块共享以下核心参数:

```bash
--roe-threshold 15.0    # ROE阈值
--batch-size 50         # 批处理大小
--refresh-interval 10   # 刷新间隔
--debug                 # 调试模式
--log-level INFO        # 日志级别
```

---

## 九、Docker部署

### 9.1 一键启动

```bash
# 构建并启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

### 9.2 服务架构

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Web UI    │ -> │   Backend   │ -> │  PostgreSQL │
│  (Streamlit)│     │ (价格更新)  │     │   (数据)    │
└─────────────┘     └─────────────┘     └─────────────┘
```

---

## 十、常见问题

### Q1: 数据库连接失败

```bash
# 检查 .env 配置
cat .env

# 测试数据库连接
docker-compose exec db psql -U admin -d stock_data -c "SELECT 1"
```

### Q2: 数据获取失败

```bash
# 检查网络
curl http://push2.eastmoney.com/api/qt/stock/get?secid=1.600519

# 关闭代理
export NO_PROXY=*
```

### Q3: 性能优化

```bash
# 减少扫描数量
python main.py scan --max-stocks 100

# 增加批处理大小
python main.py --batch-size 100
```

---

## 十一、技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Streamlit + Plotly |
| 后端 | Python + SQLAlchemy |
| 数据库 | PostgreSQL + TimescaleDB |
| 数据源 | AKShare + 东方财富API |
| 部署 | Docker + Docker Compose |

---

## 十二、目录结构

```
StockFocus/
├── main.py                 # 命令行入口
├── config.py              # 配置管理
├── stock_api.py           # 统一API模块
├── valuation.py           # 动态估值
├── risk_analyzer.py       # 风险分析
├── report_generator.py    # PDF报告
├── validators.py          # 数据校验
├── cache_utils.py         # 缓存管理
├── etl_pipeline.py       # 专业ETL
├── stock_scanner.py       # 股票扫描
├── backend_service.py     # 后端服务
├── backend_etl.py        # ETL处理
├── evaluation_models.py   # 评估模型
├── app_web.py            # Web界面
├── docker-compose.yaml   # 容器编排
└── .env.example         # 环境变量模板
```

---

*本系统仅供学习和研究使用，投资有风险，请谨慎决策。*
