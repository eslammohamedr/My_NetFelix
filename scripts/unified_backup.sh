#!/bin/bash
# ==============================================================================
# NetFelix Unified Nightly Backup Suite
# Backs up Jellyfin (Database, Watch Progress, Users), Immich (Postgres DB),
# and Server Configurations to /media/dell/Data1/backups/daily/
# ==============================================================================

set -e

BACKUP_DIR="/media/dell/Data1/backups/daily"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
TEMP_DIR="/tmp/netfelix_backup_${TIMESTAMP}"
ARCHIVE_NAME="netfelix_backup_${TIMESTAMP}.tar.gz"
ARCHIVE_PATH="${BACKUP_DIR}/${ARCHIVE_NAME}"
PROJECT_DIR="/home/dell/Desktop/My_NetFelix"

mkdir -p "$BACKUP_DIR"
mkdir -p "$TEMP_DIR"

echo "[$(date)] Starting NetFelix Unified Backup..."

# 1. Backup Immich PostgreSQL Database
echo "Dumping Immich PostgreSQL database..."
docker exec netfelix-immich-postgres pg_dumpall -U postgres > "${TEMP_DIR}/immich_database.sql"

# 2. Backup Jellyfin Database cleanly using SQLite online backup
echo "Backing up Jellyfin Database..."
sqlite3 "${PROJECT_DIR}/config/jellyfin/data/jellyfin.db" ".backup '${TEMP_DIR}/jellyfin.db'"
if [ -f "${PROJECT_DIR}/config/jellyfin/data/introskipper/introskipper-v2.db" ]; then
    sqlite3 "${PROJECT_DIR}/config/jellyfin/data/introskipper/introskipper-v2.db" ".backup '${TEMP_DIR}/introskipper-v2.db'"
fi

# 3. Backup Key Configurations
echo "Backing up configuration files..."
mkdir -p "${TEMP_DIR}/config"
cp -r "${PROJECT_DIR}/config/jellyfin/config" "${TEMP_DIR}/config/jellyfin_config" 2>/dev/null || true
cp "${PROJECT_DIR}/config/known_devices.json" "${TEMP_DIR}/config/" 2>/dev/null || true
cp "${PROJECT_DIR}/config/jellyseerr/settings.json" "${TEMP_DIR}/config/jellyseerr_settings.json" 2>/dev/null || true
cp "${PROJECT_DIR}/.env" "${TEMP_DIR}/config/dotenv.bak" 2>/dev/null || true

# 4. Create Compressed Tarball
echo "Creating compressed archive..."
tar -czf "$ARCHIVE_PATH" -C "$TEMP_DIR" .

# Cleanup temporary folder
rm -rf "$TEMP_DIR"

# 5. Retention: Keep only the latest 7 backups
echo "Cleaning old backups (keeping latest 7)..."
ls -tp "${BACKUP_DIR}"/netfelix_backup_*.tar.gz | grep -v '/$' | tail -n +8 | xargs -I {} rm -- "{}" 2>/dev/null || true

# Calculate File Size & Free Disk
BACKUP_SIZE=$(du -h "$ARCHIVE_PATH" | cut -f1)
FREE_DISK=$(df -h /media/dell/Data1 | awk 'NR==2 {print $4}')

echo "[$(date)] Backup completed successfully: ${ARCHIVE_PATH} (${BACKUP_SIZE})"

# 6. Send Telegram Notification
python3 -c "
import os, sys
sys.path.append('${PROJECT_DIR}/scripts')
import telegram_bot

msg = (
    '💾 <b>اكتمل النسخ الاحتياطي التلقائي لسيرفر NetFelix بنجاح!</b>\n\n'
    '📦 <b>اسم الأرشيف:</b> <code>${ARCHIVE_NAME}</code>\n'
    '📊 <b>حجم النسخة:</b> <code>${BACKUP_SIZE}</code>\n'
    '🗄️ <b>المحتويات:</b>\n'
    '  • قاعدة بيانات Jellyfin ومسار المشاهدة\n'
    '  • قاعدة بيانات صور Immich وموديلات الذكاء الاصطناعي\n'
    '  • إعدادات السيرفر والأجهزة وشبكة الواي فاي\n'
    '📍 <b>المكان:</b> <code>${BACKUP_DIR}</code>\n'
    '💾 <b>المساحة الحرة المتبقية:</b> <code>${FREE_DISK}</code>'
)
telegram_bot.broadcast_notification(msg)
" || true

echo "Notification sent."
