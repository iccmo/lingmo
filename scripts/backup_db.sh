#!/bin/bash
BACKUP_DIR="$(dirname "$0")/../data/backups"
mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
cp data/novel_writer.db "$BACKUP_DIR/novel_writer_$TIMESTAMP.db"
ls -t "$BACKUP_DIR"/novel_writer_*.db 2>/dev/null | tail -n +8 | xargs rm -f 2>/dev/null
echo "Backup: $BACKUP_DIR/novel_writer_$TIMESTAMP.db ($(du -h "$BACKUP_DIR/novel_writer_$TIMESTAMP.db" | cut -f1))"
