#!/bin/bash
set -euo pipefail

BACKUP_DIR="/media/dell/Data1/netfelix_data/backups/immich"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/immich_db_${TIMESTAMP}.sql.gz"

mkdir -p "${BACKUP_DIR}"

echo "[$(date)] Starting Immich database backup..."
docker exec netfelix-immich-postgres pg_dumpall -c -U postgres | gzip > "${BACKUP_FILE}"
FILESIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
echo "[$(date)] Immich database backup completed: ${BACKUP_FILE} (${FILESIZE})"

# Keep last 7 days of backups
find "${BACKUP_DIR}" -name "immich_db_*.sql.gz" -type f -mtime +7 -delete
echo "[$(date)] Cleaned up backups older than 7 days."

# Send Telegram notification if configured
TOKEN="8916726320:AAG0TEoBeV4fovLrR2oLGsuEJz27oSxUp30"
CHAT_ID="850274229"
if [ -n "${TOKEN}" ] && [ -n "${CHAT_ID}" ]; then
  MSG="🛡️ *Immich Backup Completed Successfully!*%0A📁 Size: \`${FILESIZE}\`%0A⏰ Time: \`$(date +'%Y-%m-%d %H:%M')\`"
  curl -s -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" \
    -d "chat_id=${CHAT_ID}&text=${MSG}&parse_mode=Markdown" > /dev/null || true
fi
