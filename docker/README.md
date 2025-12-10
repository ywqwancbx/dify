# Dify自定义部署

这个配置使用我们自己的web前端 + 官方的dify API服务，实现自定义的Dify部署。

## 🏗️ 架构说明

- **Web前端**: 使用我们修改过的web代码，包含认证集成功能
- **API服务**: 使用官方的dify-api镜像
- **数据库**: PostgreSQL
- **缓存**: Redis
- **向量存储**: Weaviate
- **反向代理**: Nginx

## 📁 文件结构

```
docker/
├── Dockerfile.web              # Web前端Dockerfile
├── docker-compose.yaml         # 修改后的官方Docker Compose配置
├── start.sh                    # 启动脚本
└── README.md                   # 说明文档
```

## 🚀 快速开始

### 1. 启动服务

```bash
cd docker
./start.sh
```

### 2. 访问应用

- **Web前端**: http://localhost:3000
- **Nginx代理**: http://localhost:80

### 3. 管理服务

```bash
# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs

# 停止服务
docker-compose down

# 重启服务
docker-compose restart
```

## 🔧 配置说明

### 环境变量

主要配置在 `env.custom` 文件中：

- **数据库配置**: DB_USERNAME, DB_PASSWORD, DB_HOST等
- **Redis配置**: REDIS_HOST, REDIS_PASSWORD等
- **API URL配置**: CONSOLE_API_URL, APP_API_URL等
- **向量存储配置**: VECTOR_STORE, WEAVIATE_ENDPOINT等

### 端口配置

- **80**: Nginx反向代理
- **3000**: Web前端
- **5001**: API服务
- **5432**: PostgreSQL数据库
- **6379**: Redis缓存
- **8080**: Weaviate向量存储

## 📊 服务说明

### Web前端 (web)
- 使用我们修改过的web代码
- 包含认证集成功能
- 端口: 3000

### API服务 (api)
- 使用官方dify-api:1.9.2镜像
- 提供REST API接口
- 端口: 5001

### Worker服务 (worker)
- 处理异步任务
- 使用Celery

### Worker Beat服务 (worker_beat)
- 定时任务调度
- 使用Celery Beat

### 数据库 (db)
- PostgreSQL 15
- 存储应用数据

### 缓存 (redis)
- Redis 6
- 缓存和会话存储

### 向量存储 (weaviate)
- Weaviate 1.27.0
- 向量数据库

### 反向代理 (nginx)
- Nginx
- 统一入口

## 🔍 故障排除

### 1. 端口冲突

如果端口被占用，修改 `env.custom` 文件中的端口配置：

```bash
EXPOSE_NGINX_PORT=8080
```

### 2. 服务启动失败

检查Docker日志：

```bash
docker-compose -f docker-compose.custom.yml --env-file env.custom logs [service_name]
```

### 3. 数据库连接问题

确保数据库服务已启动：

```bash
docker-compose -f docker-compose.custom.yml --env-file env.custom ps db
```

### 4. 权限问题

确保volumes目录有正确权限：

```bash
chmod -R 755 volumes/
```

## 📝 注意事项

1. **首次启动**: 首次启动可能需要几分钟时间，等待所有服务就绪
2. **数据持久化**: 数据保存在 `./volumes/` 目录中
3. **资源要求**: 建议至少4GB内存
4. **网络要求**: 确保端口80、3000、5001未被占用

## 🔄 更新部署

### 更新Web前端

1. 修改web代码
2. 重新构建镜像：

```bash
docker-compose -f docker-compose.custom.yml --env-file env.custom build web
```

3. 重启服务：

```bash
docker-compose -f docker-compose.custom.yml --env-file env.custom up -d web
```

### 更新API服务

1. 修改 `docker-compose.custom.yml` 中的API镜像版本
2. 重启服务：

```bash
docker-compose -f docker-compose.custom.yml --env-file env.custom up -d api
```

## 📞 支持

如果遇到问题，请检查：

1. Docker和Docker Compose版本
2. 系统资源（内存、磁盘空间）
3. 网络连接
4. 日志文件

## 🎯 特性

- ✅ 使用我们自己的web前端
- ✅ 包含认证集成功能
- ✅ 使用官方API服务
- ✅ 完整的Docker化部署
- ✅ 数据持久化
- ✅ 反向代理支持
- ✅ 易于管理和维护