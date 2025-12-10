#!/bin/bash

# 设置颜色输出
GREEN='\033[0;32m'
NC='\033[0m'

# 设置备份目录和时间戳
BACKUP_DIR="./backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_PATH="${BACKUP_DIR}/dify_backup_${TIMESTAMP}"

echo -e "${GREEN}Starting Dify data backup...${NC}"

# 创建备份目录
mkdir -p "${BACKUP_PATH}"

# 备份 Docker volumes 数据
echo -e "${GREEN}Backing up Docker volumes...${NC}"
cd docker

# 创建数据目录的压缩备份
echo -e "${GREEN}Backing up uploads...${NC}"
tar -czf "${BACKUP_PATH}/uploads.tar.gz" ./volumes/uploads 2>/dev/null || true

echo -e "${GREEN}Backing up PostgreSQL data...${NC}"
tar -czf "${BACKUP_PATH}/postgres.tar.gz" ./volumes/postgres 2>/dev/null || true

echo -e "${GREEN}Backing up Redis data...${NC}"
tar -czf "${BACKUP_PATH}/redis.tar.gz" ./volumes/redis 2>/dev/null || true

echo -e "${GREEN}Backing up Weaviate data...${NC}"
tar -czf "${BACKUP_PATH}/weaviate.tar.gz" ./volumes/weaviate 2>/dev/null || true

# 备份环境配置文件
echo -e "${GREEN}Backing up configuration files...${NC}"
cp .env "${BACKUP_PATH}/" 2>/dev/null || true
cp docker-compose.yml "${BACKUP_PATH}/" 2>/dev/null || true
cp docker-compose.custom.yml "${BACKUP_PATH}/" 2>/dev/null || true

echo -e "${GREEN}Backup completed! Files are stored in: ${BACKUP_PATH}${NC}"
echo -e "${GREEN}To restore this backup, use: restore-data.sh ${TIMESTAMP}${NC}"

# 创建恢复脚本
cat << 'EOF' > restore-data.sh
#!/bin/bash
if [ -z "$1" ]; then
    echo "Please provide backup timestamp"
    echo "Usage: ./restore-data.sh TIMESTAMP"
    exit 1
fi

BACKUP_PATH="./backups/dify_backup_$1"
if [ ! -d "$BACKUP_PATH" ]; then
    echo "Backup directory not found: $BACKUP_PATH"
    exit 1
fi

echo "Stopping services..."
docker-compose down

echo "Restoring data..."
cd docker
rm -rf ./volumes
mkdir -p ./volumes

tar -xzf "${BACKUP_PATH}/uploads.tar.gz" -C . 2>/dev/null || true
tar -xzf "${BACKUP_PATH}/postgres.tar.gz" -C . 2>/dev/null || true
tar -xzf "${BACKUP_PATH}/redis.tar.gz" -C . 2>/dev/null || true
tar -xzf "${BACKUP_PATH}/weaviate.tar.gz" -C . 2>/dev/null || true

# 恢复配置文件
cp "${BACKUP_PATH}/.env" . 2>/dev/null || true
cp "${BACKUP_PATH}/docker-compose.yml" . 2>/dev/null || true
cp "${BACKUP_PATH}/docker-compose.custom.yml" . 2>/dev/null || true

echo "Starting services..."
docker-compose up -d

echo "Restore completed!"
EOF

chmod +x restore-data.sh
