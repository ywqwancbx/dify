#!/bin/bash

# Dify Web 优化构建脚本
# 使用预构建依赖镜像来加速构建过程

set -e

# 配置
REGISTRY=${REGISTRY:-"your-registry.com"}
PROJECT_NAME=${PROJECT_NAME:-"dify"}
WEB_DEPS_TAG=${WEB_DEPS_TAG:-"web-deps-latest"}
WEB_TAG=${WEB_TAG:-"web-latest"}

echo "🚀 开始优化构建 Dify Web..."

# 步骤1: 构建依赖镜像（仅在依赖文件变化时执行）
echo "📦 步骤1: 检查是否需要构建依赖镜像..."

# 检查依赖文件是否有变化
DEPS_HASH=$(find ../web -name "package.json" -o -name "pnpm-lock.yaml" | xargs cat | md5sum | cut -d' ' -f1)
CURRENT_DEPS_HASH=$(docker images --format "{{.Tag}}" | grep "deps-${DEPS_HASH}" || echo "")

if [ -z "$CURRENT_DEPS_HASH" ]; then
    echo "🔄 依赖文件有变化，构建新的依赖镜像..."
    docker build \
        --target web-deps-base \
        -f Dockerfile.web.deps \
        -t ${PROJECT_NAME}-web-deps:${DEPS_HASH} \
        -t ${PROJECT_NAME}-web-deps:latest \
        ..
    
    # 可选：推送到registry
    if [ "$PUSH_TO_REGISTRY" = "true" ]; then
        echo "📤 推送依赖镜像到registry..."
        docker tag ${PROJECT_NAME}-web-deps:latest ${REGISTRY}/${PROJECT_NAME}-web-deps:latest
        docker push ${REGISTRY}/${PROJECT_NAME}-web-deps:latest
    fi
else
    echo "✅ 依赖镜像已存在，跳过依赖构建"
fi

# 步骤2: 使用依赖镜像构建最终镜像
echo "🔨 步骤2: 构建最终Web镜像..."

# 修改Dockerfile以使用预构建的依赖镜像
sed "s/FROM web-deps-base AS web-builder/FROM ${PROJECT_NAME}-web-deps:latest AS web-builder/" \
    Dockerfile.web.deps > Dockerfile.web.temp

docker build \
    -f Dockerfile.web.temp \
    -t ${PROJECT_NAME}-web:${WEB_TAG} \
    ..

# 清理临时文件
rm -f Dockerfile.web.temp

echo "✅ Web镜像构建完成！"
echo "📊 构建统计:"
echo "  - 依赖镜像: ${PROJECT_NAME}-web-deps:latest"
echo "  - 最终镜像: ${PROJECT_NAME}-web:${WEB_TAG}"

# 可选：推送到registry
if [ "$PUSH_TO_REGISTRY" = "true" ]; then
    echo "📤 推送最终镜像到registry..."
    docker tag ${PROJECT_NAME}-web:${WEB_TAG} ${REGISTRY}/${PROJECT_NAME}-web:${WEB_TAG}
    docker push ${REGISTRY}/${PROJECT_NAME}-web:${WEB_TAG}
fi
