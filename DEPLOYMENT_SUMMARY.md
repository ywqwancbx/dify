# Dify自定义部署完成报告

## 部署概述

已成功完成Dify项目的自定义部署，使用自编译的后端API服务，其他组件使用Dify官方镜像。

## 主要配置修改

### 1. 后端服务配置
- **API服务**: 使用自编译的 `docker-api` 镜像
- **Worker服务**: 使用自编译的 `docker-worker` 镜像  
- **Worker Beat服务**: 使用自编译的 `docker-worker_beat` 镜像
- **Web服务**: 使用Dify官方 `langgenius/dify-web:1.9.2` 镜像

### 2. 端口配置修改
为避免与现有EAM项目服务冲突，修改了以下端口：
- **Nginx HTTP端口**: `80` → `8080`
- **Nginx HTTPS端口**: `443` → `8443`
- **插件调试端口**: `5003` (保持不变)

### 3. 环境配置
创建了 `env.local` 环境配置文件，包含：
- 数据库配置 (PostgreSQL)
- Redis配置
- API URL配置
- 端口配置

## 服务状态

所有服务已成功启动并运行正常：

| 服务名称 | 状态 | 端口映射 | 说明 |
|---------|------|----------|------|
| docker-api-1 | ✅ 运行中 | 5001/tcp | 自编译API服务 |
| docker-web-1 | ✅ 运行中 | 3000/tcp | Dify官方Web前端 |
| docker-nginx-1 | ✅ 运行中 | 8080:80, 8443:443 | 反向代理 |
| docker-db-1 | ✅ 运行中 | 5432/tcp | PostgreSQL数据库 |
| docker-redis-1 | ✅ 运行中 | 6379/tcp | Redis缓存 |
| docker-worker-1 | ✅ 运行中 | 5001/tcp | 自编译Worker服务 |
| docker-worker_beat-1 | ✅ 运行中 | 5001/tcp | 自编译定时任务 |
| docker-sandbox-1 | ✅ 运行中 | - | 代码执行沙箱 |
| docker-plugin_daemon-1 | ✅ 运行中 | 5003:5003 | 插件守护进程 |
| docker-ssrf_proxy-1 | ✅ 运行中 | 3128/tcp | SSRF代理 |

## 访问地址

- **Dify Web界面**: http://localhost:8080
- **Dify API**: http://localhost:8080/api
- **控制台API**: http://localhost:8080/console/api
- **插件调试**: http://localhost:5003

## 管理命令

```bash
# 进入docker目录
cd /home/chenonce/code/gstar/project/manage/code/dify/docker

# 查看服务状态
sudo docker compose ps

# 查看日志
sudo docker compose logs -f

# 停止服务
sudo docker compose down

# 重启服务
sudo docker compose --env-file env.local up -d
```

## 技术架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Nginx:8080    │────│   Web:3000      │────│   API:5001      │
│   (反向代理)     │    │   (前端界面)     │    │   (自编译后端)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
         ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
         │   PostgreSQL    │    │     Redis       │    │    Worker       │
         │   (数据库)       │    │   (缓存)        │    │   (自编译)      │
         └─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 注意事项

1. **环境变量警告**: 启动时会有一些环境变量未设置的警告，但不影响服务正常运行
2. **端口冲突**: 已成功避免与EAM项目的端口冲突
3. **数据持久化**: 数据保存在 `./volumes/` 目录中
4. **服务依赖**: API服务依赖数据库和Redis服务启动完成
5. **首次启动**: 首次启动可能需要1-2分钟时间

## 部署完成

✅ 自定义Dify部署已成功完成！
- 使用自编译后端API
- 使用Dify官方Web前端
- 端口配置已优化避免冲突
- 所有服务运行正常
- 可通过 http://localhost:8080 访问
