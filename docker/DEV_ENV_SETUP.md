# Dev 环境配置说明

## 概述
dev 环境已配置为与生产环境并行运行，使用不同的端口和数据目录。

## 端口配置

### Dev 环境端口（避免与生产环境冲突）
- **PostgreSQL**: 5433 (生产: 5432)
- **Redis**: 6380 (生产: 6379)
- **Weaviate**: 8081 (生产: 8080)
- **Weaviate GRPC**: 50052 (生产: 50051)
- **Plugin Daemon**: 5004 (生产: 5002)
- **Plugin Debugging**: 5005 (生产: 5003)
- **SSRF Proxy**: 3129 (生产: 3128)
- **Sandbox**: 8195 (生产: 8194)

## Volume 配置

### Dev 环境数据目录（独立于生产环境）
所有 dev 环境的数据存储在 `./volumes-dev/` 目录下：
- `./volumes-dev/db/data` - PostgreSQL 数据
- `./volumes-dev/redis/data` - Redis 数据
- `./volumes-dev/weaviate` - Weaviate 向量数据库数据
- `./volumes-dev/plugin_daemon` - Plugin Daemon 数据
- `./volumes-dev/sandbox/dependencies` - Sandbox 依赖
- `./volumes-dev/sandbox/conf` - Sandbox 配置

## 启动 Dev 环境

使用 Makefile 命令启动：
\`\`\`bash
make prepare-docker
\`\`\`

或直接使用 docker compose：
\`\`\`bash
cd docker
docker compose -f docker-compose.middleware.yaml --env-file middleware.env -p dify-middlewares-dev up -d
\`\`\`

## 停止 Dev 环境

\`\`\`bash
cd docker
docker compose -f docker-compose.middleware.yaml --env-file middleware.env -p dify-middlewares-dev down
\`\`\`

## 清理 Dev 环境数据

\`\`\`bash
make dev-clean
\`\`\`

或手动删除：
\`\`\`bash
rm -rf docker/volumes-dev
\`\`\`

## 注意事项

1. Dev 环境和生产环境完全隔离，数据不会互相影响
2. 确保系统有足够的资源（内存、磁盘）同时运行两套环境
3. 当前配置已避免端口冲突，可以安全并行运行
