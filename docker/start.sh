#!/bin/bash

# Dify自定义部署启动脚本
# 使用我们自己的web前端 + 官方的dify API服务

set -e

echo "🚀 启动Dify自定义部署..."

# 检查Docker是否运行
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker未运行，请先启动Docker"
    exit 1
fi

# 检查Docker Compose是否安装
if ! docker compose version > /dev/null 2>&1; then
    echo "❌ Docker Compose未安装"
    exit 1
fi

# 创建必要的目录
echo "📁 创建必要的目录..."
mkdir -p volumes/app/storage
mkdir -p volumes/plugin_daemon/assets
mkdir -p volumes/plugin_daemon/cwd
mkdir -p volumes/db/data
mkdir -p volumes/redis/data
mkdir -p volumes/weaviate

# 设置权限
chmod -R 755 volumes/

# 启动服务
echo "🐳 启动Docker服务..."
docker compose --env-file env.local up -d

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 10

# 检查服务状态
echo "🔍 检查服务状态..."
docker compose ps

echo "✅ Dify自定义部署启动完成！"
echo ""
echo "🌐 访问地址："
echo "   - Dify Web界面: http://localhost:8080"
echo "   - Dify API: http://localhost:8080/api"
echo "   - 控制台API: http://localhost:8080/console/api"
echo ""
echo "📊 服务状态："
echo "   - API服务: http://localhost:5001 (内部)"
echo "   - 数据库: PostgreSQL (内部)"
echo "   - 缓存: Redis (内部)"
echo "   - 向量存储: Weaviate (内部)"
echo ""
echo "🔧 管理命令："
echo "   - 查看日志: docker compose logs"
echo "   - 停止服务: docker compose down"
echo "   - 重启服务: docker compose restart"
echo ""
echo "📝 注意事项："
echo "   - 首次启动可能需要几分钟时间"
echo "   - 确保端口8080、8443未被占用"
echo "   - 数据将保存在 ./volumes/ 目录中"
echo "   - 使用我们自编译的后端和自定义的web前端"
