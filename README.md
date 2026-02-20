# StockFocus Pro - 量化投研系统

## 项目简介

StockFocus Pro 是一个基于 Python 的全栈量化投研系统，专注于 A 股市场的价值投资分析。

### 核心功能

1. **ROE 质量筛选**: 基于连续多年 ROE > 15% 的标准筛选高质量股票
2. **15倍PE估值**: 使用合理价格法计算安全边际
3. **实时数据更新**: 自动获取并更新股票实时价格
4. **可视化分析**: 提供丰富的图表和热力图分析
5. **PDF报告**: 自动生成投研日报和分析报告

## 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone <repository-url>
cd StockFocus

# 安装依赖
pip install -r requirements.txt

# 复制环境变量配置
cp .env.example .env
# 编辑 .env 文件，设置数据库密码等配置
```

### 2. Docker 部署 (推荐)

```bash
# 构建并启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

服务启动后访问:
- Web界面: http://localhost:8501
- 数据库: localhost:5432

### 3. 本地开发模式

```bash
# 启动数据库
docker-compose up -d db

# 运行股票扫描器 (初始化数据)
python stock_scanner.py

# 启动后端服务
python backend_service.py

# 启动Web界面
streamlit run app_web.py --server.port=8501
```

## 项目结构

```
StockFocus/
├── app_web.py              # Web主界面
├── backend_service.py       # 后端数据服务
├── backend_etl.py          # ETL数据处理
├── stock_scanner.py         # 股票质量扫描器
├── config.py               # 配置管理模块
├── docker-compose.yaml      # Docker编排文件
├── Dockerfile              # Docker镜像构建
├── requirements.txt         # Python依赖
├── init_db.sql            # 数据库初始化脚本
├── .env.example           # 环境变量模板
└── .gitignore             # Git忽略文件
```

## 核心逻辑

### 估值方法
- **合理价格** = 最近一年 EPS × 15倍PE
- **偏差率** = (现价 - 合理价) / 合理价 × 100%
- **黄金坑标准**: 偏差率 < -15% (安全边际充足)
- **高估预警**: 偏差率 > +20% (溢价过高)

### 质量评估
- **ROE门槛**: 连续 5-10 年 ROE > 15%
- **质量评分**: 综合平均ROE、最低ROE、稳定性等多维度
- **市值分档**: 50亿以下、50-200亿、400亿以上

## 使用说明

### 1. 股票扫描
```bash
# 扫描高质量股票
python stock_scanner.py
```

### 2. 实时监控
后端服务会自动在交易时间内更新股票价格，非交易时间进入节能模式。

### 3. Web分析界面
- **全景看板**: 查看所有监控股票的估值状态
- **AI审计**: 深度分析个股投资价值
- **行业分析**: 按行业维度分析估值分布
- **报告导出**: 生成PDF投研报告

## 配置说明

主要配置项在 `.env` 文件中:

```env
# 数据库配置
POSTGRES_DB=stock_data
POSTGRES_USER=admin
POSTGRES_PASSWORD=your_secure_password
DB_HOST=localhost
DB_PORT=5432

# 应用配置
LOG_LEVEL=INFO
REFRESH_INTERVAL=10
BATCH_SIZE=50

# 网络配置
REQUEST_TIMEOUT=5
RETRY_COUNT=3
```

## 技术栈

- **前端**: Streamlit + Plotly
- **后端**: Python + SQLAlchemy
- **数据库**: PostgreSQL + TimescaleDB
- **容器化**: Docker + Docker Compose
- **数据源**: 东方财富API + AKShare

## 安全说明

1. **环境变量**: 敏感信息通过环境变量管理，不硬编码在代码中
2. **数据库**: 支持SSL连接，建议生产环境启用
3. **网络**: 本地数据库直连，外网API访问有重试和超时机制

## 故障排除

### 常见问题

1. **数据库连接失败**
   - 检查 `.env` 配置是否正确
   - 确认数据库服务已启动

2. **数据获取失败**
   - 检查网络连接
   - 确认 API 访问权限

3. **Docker启动问题**
   - 检查 Docker 版本兼容性
   - 查看容器日志排查具体错误

### 日志查看

```bash
# Docker环境
docker-compose logs web
docker-compose logs backend
docker-compose logs db

# 本地环境
# 日志会输出到控制台，配置日志级别可控制详细程度
```

## 贡献指南

1. Fork 项目
2. 创建功能分支
3. 提交更改
4. 推送到分支
5. 创建 Pull Request

## 许可证

本项目仅供学习和研究使用，投资有风险，请谨慎决策。

## 联系方式

如有问题或建议，请通过 Issue 或 Pull Request 联系。