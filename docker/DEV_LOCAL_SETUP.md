# Dev 环境本地开发配置指南

## 概述
Dev 环境使用 Docker 运行中间件（PostgreSQL, Redis, Weaviate 等），但 API 和 Web 服务使用本地代码运行。

## 中间件服务（Docker）
已启动的中间件服务：
- **PostgreSQL**: localhost:5433
- **Redis**: localhost:6380  
- **Weaviate**: localhost:8081
- **Plugin Daemon**: localhost:5004
- **Sandbox**: localhost:8195
- **SSRF Proxy**: localhost:3129

## API 配置

### 1. 创建/更新 API .env 文件

在 `api/.env` 中配置连接到 dev 中间件：

\`\`\`bash
# Database - 连接到 dev 环境的 PostgreSQL
DB_HOST=localhost
DB_PORT=5433
DB_USERNAME=postgres
DB_PASSWORD=difyai123456
DB_DATABASE=dify

# Redis - 连接到 dev 环境的 Redis
REDIS_HOST=localhost
REDIS_PORT=6380
REDIS_PASSWORD=difyai123456
REDIS_DB=0

# Weaviate - 连接到 dev 环境的 Weaviate
WEAVIATE_ENDPOINT=http://localhost:8081
WEAVIATE_API_KEY=WVF5YThaHlkYwhGUSmCRgsX3tD5ngdN8pkih

# Sandbox - 连接到 dev 环境的 Sandbox
CODE_EXECUTION_ENDPOINT=http://localhost:8195
CODE_EXECUTION_API_KEY=dify-sandbox

# Plugin Daemon - 连接到 dev 环境的 Plugin Daemon
PLUGIN_DAEMON_URL=http://localhost:5004
PLUGIN_DAEMON_KEY=lYkiYYT6owG+71oLerGzA7GXCgOT++6ovaezWAjpCjf+Sjc3ZtU+qUEi

# SSRF Proxy
SSRF_PROXY_HTTP_URL=http://localhost:3129
SSRF_PROXY_HTTPS_URL=http://localhost:3129
\`\`\`

### 2. 启动 API 服务

\`\`\`bash
cd api
uv run flask run --host 0.0.0.0 --port=5001 --debug
\`\`\`

## Web 配置

### 1. 创建/更新 Web .env.local 文件

在 `web/.env.local` 中配置连接到本地 API：

\`\`\`bash
# 开发环境
NEXT_PUBLIC_DEPLOY_ENV=DEVELOPMENT
NEXT_PUBLIC_EDITION=SELF_HOSTED

# API 地址 - 连接到本地 API
NEXT_PUBLIC_API_PREFIX=http://localhost:5001/console/api
NEXT_PUBLIC_PUBLIC_API_PREFIX=http://localhost:5001/api
\`\`\`

### 2. 启动 Web 服务

\`\`\`bash
cd web
pnpm run dev
\`\`\`

访问 http://localhost:3000

## 完整启动流程

\`\`\`bash
# 1. 启动中间件（如果还没启动）
make prepare-docker

# 2. 配置并启动 API
cd api
cp .env.example .env
# 编辑 .env，设置上述配置
uv sync --dev
uv run flask db upgrade
uv run flask run --host 0.0.0.0 --port=5001 --debug

# 3. 配置并启动 Web（新终端）
cd web
cp .env.example .env.local
# 编辑 .env.local，设置上述配置
pnpm install
pnpm run dev
\`\`\`

## 注意事项

1. API 和 Web 使用本地代码运行，便于开发和调试
2. 中间件使用 Docker 运行，与生产环境隔离
3. 确保端口不冲突：
   - API: 5001
   - Web: 3000
   - PostgreSQL: 5433 (dev)
   - Redis: 6380 (dev)
   - Weaviate: 8081 (dev)
