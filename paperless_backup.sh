#!/bin/bash
# -----------------------------------------------------------------------------
# SCRIPT: Paperless Export & Rclone Sync
# -----------------------------------------------------------------------------

# CONFIGURATION
# -------------------------
CONTAINER_NAME="paperless-ngx"
LOCAL_EXPORT_PATH="/mnt/user/documents/paperless_backup" # Change this
REMOTE_NAME="gdrive"                                     # Change this
DEST_PATH="Backups/Paperless"                            # Change this

# 1. EXPORT
echo "Starting Export..."
# -na (No Archive), -nt (No Thumbnails), -d (Delete old), -f (Use filename)
docker exec $CONTAINER_NAME document_exporter ../export -na -nt -d -f

if [ $? -ne 0 ]; then
    echo "❌ Export Failed."
    exit 1
fi

# 2. SYNC
echo "Starting Rclone Sync..."
rclone sync "$LOCAL_EXPORT_PATH" "$REMOTE_NAME:$DEST_PATH" \
    --create-empty-src-dirs \
    --transfers=8 \
    --checkers=8 \
    --drive-chunk-size=32M \
    --delete-excluded \
    -v \
    --stats 5s

echo "✅ Backup Complete."
