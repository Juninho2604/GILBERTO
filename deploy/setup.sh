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

echo "==> 4/6  Configuración (.env: contraseña + dominio)"
cd "${APP_DIR}"
ENV_FILE="${APP_DIR}/.env"
touch "${ENV_FILE}"; chmod 600 "${ENV_FILE}" 2>/dev/null || true

# Setea KEY=VALUE en .env sin pisar las otras claves. Sin sed: los valores con
# caracteres especiales (& | / \) rompían el patrón de reemplazo y podían dejar
# la contraseña corrupta. grep -v + append es inmune al contenido del valor.
set_env_var() {
  local key="$1" val="$2"
  local tmp="${ENV_FILE}.tmp"
  { grep -v "^${key}=" "${ENV_FILE}" 2>/dev/null || true; } > "${tmp}"
  printf '%s=%s\n' "${key}" "${val}" >> "${tmp}"
  mv "${tmp}" "${ENV_FILE}"
  chmod 600 "${ENV_FILE}" 2>/dev/null || true
}

GENERATED=""
if [ -n "${APP_PASSWORD:-}" ]; then
  set_env_var APP_PASSWORD "${APP_PASSWORD}"
elif ! grep -q '^APP_PASSWORD=' "${ENV_FILE}" 2>/dev/null; then
  GENERATED="$(head -c 32 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | cut -c1-14 || true)"
  set_env_var APP_PASSWORD "${GENERATED}"
fi
[ -n "${DOMAIN:-}" ] && set_env_var DOMAIN "${DOMAIN}"
[ -n "${EXTERNAL_PROXY:-}" ] && set_env_var EXTERNAL_PROXY "${EXTERNAL_PROXY}"
[ -n "${DEMO_MODE:-}" ] && set_env_var DEMO_MODE "${DEMO_MODE}"
[ -n "${DEMO_PIN:-}" ] && set_env_var DEMO_PIN "${DEMO_PIN}"

# Modo "proxy externo": ya tenés tu propio reverse proxy (nginx) en el VPS.
# La app queda solo en 127.0.0.1 y NO se levanta Caddy (evita pelear por el :80).
EXT_PROXY="${EXTERNAL_PROXY:-$(grep '^EXTERNAL_PROXY=' "${ENV_FILE}" 2>/dev/null | cut -d= -f2- || true)}"
EFFECTIVE_DOMAIN="${DOMAIN:-$(grep '^DOMAIN=' "${ENV_FILE}" 2>/dev/null | cut -d= -f2- || true)}"

# El contenedor corre SIN root (uid 1000) y monta ./data como volumen: el
# directorio en el host tiene que ser escribible por ese uid (estado del
# inventario, ledger del bono, logs).
mkdir -p "${APP_DIR}/data/logs"
$SUDO chown -R 1000:1000 "${APP_DIR}/data" 2>/dev/null || true

echo "==> 5/6  Build + run"
if [ "${EXT_PROXY:-}" = "1" ]; then
  echo "    Modo proxy externo: app en 127.0.0.1:${PORT}, sin Caddy (la sirve tu nginx)."
  set_env_var BIND_IP 127.0.0.1
  $SUDO docker compose up -d --build
elif [ -n "${EFFECTIVE_DOMAIN}" ]; then
  echo "    Modo HTTPS con Caddy para ${EFFECTIVE_DOMAIN} (la app no se publica al exterior)"
  set_env_var BIND_IP 127.0.0.1   # app solo en localhost; Caddy la sirve por 443
  $SUDO docker compose -f docker-compose.yml -f docker-compose.tls.yml up -d --build
else
  set_env_var BIND_IP 0.0.0.0
  $SUDO docker compose up -d --build
fi

echo "==> 6/6  Firewall"
if [ "${EXT_PROXY:-}" = "1" ]; then
  echo "    (proxy externo: el firewall lo maneja tu nginx, no toco puertos)"
elif command -v ufw >/dev/null 2>&1 && $SUDO ufw status 2>/dev/null | grep -q "Status: active"; then
  if [ -n "${EFFECTIVE_DOMAIN}" ]; then
    $SUDO ufw allow 80/tcp || true
    $SUDO ufw allow 443/tcp || true
  else
    $SUDO ufw allow "${PORT}/tcp" || true
  fi
fi

IP="$(curl -fsS https://api.ipify.org 2>/dev/null || echo '<IP-DEL-VPS>')"
echo
echo "================================================================"
if [ "${EXT_PROXY:-}" = "1" ]; then
  echo "  Listo. App en 127.0.0.1:${PORT} — publicala desde tu nginx (proxy_pass)."
elif [ -n "${EFFECTIVE_DOMAIN}" ]; then
  echo "  Listo (HTTPS). Abrí:  https://${EFFECTIVE_DOMAIN}"
  echo "  El certificado tarda ~30 s la primera vez (Let's Encrypt)."
  echo "  Requisito: ${EFFECTIVE_DOMAIN} debe apuntar a ${IP}."
else
  echo "  Listo. Abrí:  http://${IP}:${PORT}"
fi
if [ -n "${GENERATED}" ]; then
  echo
  echo "  🔑 CONTRASEÑA GENERADA (guardala, se muestra una sola vez):"
  echo "       ${GENERATED}"
  echo "  Para cambiarla:  editá ${ENV_FILE} y corré el redeploy."
else
  echo "  🔒 Login activo con la contraseña de ${ENV_FILE}."
fi
echo "  Logs:      $SUDO docker compose logs -f"
echo "  Redeploy:  bash ${APP_DIR}/deploy/setup.sh"
echo "================================================================"
