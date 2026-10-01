#!/bin/bash
set -euo pipefail

BACKUP_DIR="/media/dell/Data1/netfelix_data/backups/immich"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/immich_db_${TIMESTAMP}.sql.gz"

mkdir -p "${BACKUP_DIR}"

echo "[$(date)] Starting Immich database backup..."
docker exec netfelix-immich-postgres pg_dumpall -c -U postgres | gzip > "${BACKUP_FILE}"
echo "[$(date)] Immich database backup completed: ${BACKUP_FILE} ($(du -h "${BACKUP_FILE}" | cut -f1))"

# Keep last 7 days of backups
find "${BACKUP_DIR}" -name "immich_db_*.sql.gz" -type f -mtime +7 -delete
echo "[$(date)] Cleaned up backups older than 7 days."
