# StockFocus 部署指南

## 快速启动

### 1. 环境配置
```bash
# 复制环境变量模板
cp .env.example .env

# 编辑配置文件，设置安全的数据库密码
nano .env
```

### 2. Docker 一键启动
```bash
# 构建并启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

### 3. 访问应用
- Web界面: http://localhost:8501
- 数据库: localhost:5432 (用户: admin, 密码: 你在.env中设置的)

### 4. 初始化数据
```bash
# 运行股票质量扫描，初始化数据库
docker-compose exec backend python stock_scanner.py
```

## 服务组件

- **web**: Streamlit Web界面 (端口8501)
- **backend**: 数据更新服务
- **db**: PostgreSQL + TimescaleDB数据库 (端口5432)

## 故障排除

### 常见问题

1. **端口冲突**: 修改docker-compose.yaml中的端口映射
2. **数据库连接失败**: 检查.env中的数据库配置
3. **权限问题**: 确保Docker有足够的权限

### 重置环境
```bash
# 停止并删除所有容器
docker-compose down

# 删除数据卷（会清空数据库）
docker-compose down -v

# 重新构建并启动
docker-compose up -d --build
```