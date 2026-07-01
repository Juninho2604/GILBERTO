#!/usr/bin/env bash
#
# Backup diario del estado de la app (inventario editado, ledger del bono,
# datos y logs). Guarda tarballs rotados en ${BACKUP_DIR} (default
# /var/backups/raee-optimizer), conservando los últimos ${KEEP} (default 14).
#
# Instalar como cron (una vez, en el VPS):
#   crontab -l 2>/dev/null | { cat; echo "20 3 * * * bash ${HOME}/raee-optimizer/deploy/backup.sh"; } | crontab -
#
# Restaurar:
#   tar xzf /var/backups/raee-optimizer/data-<fecha>.tar.gz -C ~/raee-optimizer
set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/raee-optimizer}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/raee-optimizer}"
KEEP="${KEEP:-14}"

mkdir -p "${BACKUP_DIR}"
STAMP="$(date +%Y%m%d-%H%M%S)"
tar czf "${BACKUP_DIR}/data-${STAMP}.tar.gz" -C "${APP_DIR}" data

# Rotación: conservar solo los KEEP más recientes.
ls -1t "${BACKUP_DIR}"/data-*.tar.gz 2>/dev/null | tail -n "+$((KEEP + 1))" | xargs -r rm -f

echo "Backup OK: ${BACKUP_DIR}/data-${STAMP}.tar.gz"
