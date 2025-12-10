# Dev 环境 Docker 完整配置指南

## 概述
Dev 环境使用 Docker 运行所有服务，API 和 Web 使用本地代码构建镜像。

## 架构

### 中间件服务（docker-compose.middleware.yaml）
- PostgreSQL (端口 5433)
- Redis (端口 6380)
- Weaviate (端口 8081)
- Plugin Daemon (端口 5004)
- Sandbox (端口 8195)
- SSRF Proxy (端口 3129)

### 应用服务（docker-compose.dev.yaml）
- API (端口 5001) - 使用本地代码构建
- Web (端口 3000) - 使用本地代码构建
- Worker - 使用本地代码构建
- Worker Beat - 使用本地代码构建

## 启动步骤

### 1. 启动中间件服务

\`\`\`bash
cd docker
make prepare-docker
# 或手动启动
docker-compose -f docker-compose.middleware.yaml --env-file middleware.env -p dify-middlewares-dev up -d
\`\`\`

### 2. 构建并启动 API 和 Web 服务

\`\`\`bash
cd docker
docker-compose -f docker-compose.dev.yaml -p dify-dev up -d --build
\`\`\`

### 3. 查看服务状态

\`\`\`bash
# 查看所有 dev 服务
docker-compose -f docker-compose.dev.yaml -p dify-dev ps

# 查看日志
docker-compose -f docker-compose.dev.yaml -p dify-dev logs -f api
docker-compose -f docker-compose.dev.yaml -p dify-dev logs -f web
\`\`\`

## 访问服务

- **Web**: http://localhost:3000
- **API**: http://localhost:5001
- **API Docs**: http://localhost:5001/swagger-ui.html

## 重新构建镜像

当本地代码更新后，需要重新构建：

\`\`\`bash
cd docker
docker-compose -f docker-compose.dev.yaml -p dify-dev build
docker-compose -f docker-compose.dev.yaml -p dify-dev up -d
\`\`\`

## 停止服务

\`\`\`bash
# 停止 API 和 Web
docker-compose -f docker-compose.dev.yaml -p dify-dev down

# 停止中间件（可选，如果不需要）
docker-compose -f docker-compose.middleware.yaml --env-file middleware.env -p dify-middlewares-dev down
\`\`\`

## 注意事项

1. API 和 Web 使用本地代码构建，修改代码后需要重新构建镜像
2. 所有服务连接到 dev 中间件，与生产环境完全隔离
3. 端口映射：
   - API: 5001
   - Web: 3000
   - PostgreSQL: 5433 (dev)
   - Redis: 6380 (dev)
   - Weaviate: 8081 (dev)
