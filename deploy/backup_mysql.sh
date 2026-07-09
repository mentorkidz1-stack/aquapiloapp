#!/bin/bash
# Sauvegarde quotidienne MySQL avec rotation 30 jours
# Cron (2h du matin) : 0 2 * * * /opt/poissonnerie/deploy/backup_mysql.sh
set -euo pipefail

DOSSIER=/var/backups/poissonnerie
BASE=poissonnerie
FICHIER="$DOSSIER/${BASE}_$(date +%F).sql.gz"

mkdir -p "$DOSSIER"
# Les identifiants sont lus dans /root/.my.cnf (voir deploy.md)
mysqldump --single-transaction --routines "$BASE" | gzip > "$FICHIER"

# Rotation : suppression des sauvegardes de plus de 30 jours
find "$DOSSIER" -name "${BASE}_*.sql.gz" -mtime +30 -delete

echo "$(date -Is) sauvegarde OK : $FICHIER" >> /var/log/poissonnerie/backup.log
