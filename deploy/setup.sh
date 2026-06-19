#!/usr/bin/env bash
#
# Deploy del Optimizador de Mezclas RAEE en un VPS (Contabo, Ubuntu/Debian).
# Idempotente: instala Docker si falta, clona/actualiza el repo, construye la
# imagen y levanta el contenedor en el puerto elegido. Re-ejecutable sin romper.
#
# Uso (en el VPS):
#   curl -fsSL <raw-url>/deploy/setup.sh | bash          # primera vez
#   # o, tras clonar el repo:
#   bash deploy/setup.sh
#
# Variables que podés sobreescribir:
#   REPO_URL  (default repo público en GitHub)
#   BRANCH    (default claude/new-session-5k4aar)
#   APP_DIR   (default $HOME/raee-optimizer)
#   PORT      (default 8501)
#
# Repo privado: pasá REPO_URL con token, p.ej.:
#   REPO_URL="https://<TOKEN>@github.com/Juninho2604/GILBERTO.git" bash deploy/setup.sh
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/Juninho2604/GILBERTO.git}"
BRANCH="${BRANCH:-claude/new-session-5k4aar}"
APP_DIR="${APP_DIR:-$HOME/raee-optimizer}"
PORT="${PORT:-8501}"

SUDO=""
if [ "$(id -u)" -ne 0 ]; then SUDO="sudo"; fi

echo "==> 1/5  Paquetes base (git, curl)"
if ! command -v git >/dev/null 2>&1 || ! command -v curl >/dev/null 2>&1; then
  $SUDO apt-get update -y
  $SUDO apt-get install -y git curl
fi

echo "==> 2/5  Docker"
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | $SUDO sh
fi
$SUDO systemctl enable --now docker >/dev/null 2>&1 || true

echo "==> 3/5  Código (rama ${BRANCH})"
if [ -d "${APP_DIR}/.git" ]; then
  git -C "${APP_DIR}" fetch origin "${BRANCH}"
  git -C "${APP_DIR}" checkout "${BRANCH}"
  git -C "${APP_DIR}" reset --hard "origin/${BRANCH}"
else
  git clone -b "${BRANCH}" "${REPO_URL}" "${APP_DIR}"
fi

echo "==> 4/5  Build + run (puerto ${PORT})"
cd "${APP_DIR}"
PORT="${PORT}" $SUDO docker compose up -d --build

echo "==> 5/5  Firewall"
if command -v ufw >/dev/null 2>&1 && $SUDO ufw status 2>/dev/null | grep -q "Status: active"; then
  $SUDO ufw allow "${PORT}/tcp" || true
fi

IP="$(curl -fsS https://api.ipify.org 2>/dev/null || echo '<IP-DEL-VPS>')"
echo
echo "================================================================"
echo "  Listo. Abrí:  http://${IP}:${PORT}"
echo "  Logs:        docker compose -f ${APP_DIR}/docker-compose.yml logs -f"
echo "  Redeploy:    bash ${APP_DIR}/deploy/setup.sh"
echo "================================================================"
