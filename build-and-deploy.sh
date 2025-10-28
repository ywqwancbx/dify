#!/bin/bash

# 设置颜色输出
GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Dify build and deploy script...${NC}"

# 1. 构建 Web 镜像
echo -e "${GREEN}Building web image...${NC}"
docker build -f docker/Dockerfile.web -t custom-dify-web .

# 2. 构建 API 镜像
echo -e "${GREEN}Building api image...${NC}"
docker build -f docker/Dockerfile.api -t custom-dify-api .

# 3. 构建 Worker 镜像
echo -e "${GREEN}Building worker image...${NC}"
docker build -f docker/Dockerfile.worker -t custom-dify-worker .

# 4. 创建或更新 docker-compose.yml
echo -e "${GREEN}Creating docker-compose configuration...${NC}"
cat << EOF > docker/docker-compose.custom.yml
version: '3.8'
services:
  nginx:
    image: nginx:1.25.1-alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./nginx/proxy.conf:/etc/nginx/proxy.conf
    depends_on:
      - api
      - web
    networks:
      - dify

  web:
    image: custom-dify-web
    env_file:
      - .env
    networks:
      - dify

  api:
    image: custom-dify-api
    env_file:
      - .env
    environment:
      - CONSOLE_API_URL=http://api:5001
      - CONSOLE_WEB_URL=http://web:3000
    volumes:
      - ./volumes/uploads:/app/api/storage/uploads
    depends_on:
      - postgres
      - redis
      - weaviate
    networks:
      - dify

  worker:
    image: custom-dify-worker
    env_file:
      - .env
    environment:
      - CONSOLE_API_URL=http://api:5001
      - CONSOLE_WEB_URL=http://web:3000
    depends_on:
      - postgres
      - redis
    networks:
      - dify

  postgres:
    image: postgres:15.2-alpine
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_DB=dify
    volumes:
      - ./volumes/postgres:/var/lib/postgresql/data
    networks:
      - dify

  redis:
    image: redis:7.0.11-alpine
    volumes:
      - ./volumes/redis:/data
    networks:
      - dify

  weaviate:
    image: semitechnologies/weaviate:1.19.6
    volumes:
      - ./volumes/weaviate:/var/lib/weaviate
    environment:
      - QUERY_DEFAULTS_LIMIT=25
      - AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED=true
      - PERSISTENCE_DATA_PATH=/var/lib/weaviate
      - DEFAULT_VECTORIZER_MODULE=text2vec-openai
      - ENABLE_MODULES=text2vec-openai
      - CLUSTER_HOSTNAME=node1
    networks:
      - dify

networks:
  dify:
    driver: bridge
EOF

# 5. 启动服务
echo -e "${GREEN}Starting services...${NC}"
cd docker
docker-compose -f docker-compose.custom.yml up -d

# 6. 检查服务状态
echo -e "${GREEN}Checking service status...${NC}"
docker-compose -f docker-compose.custom.yml ps

echo -e "${GREEN}Deployment completed! Access your Dify instance at http://localhost${NC}"
