# Deploy en un VPS (Contabo / Ubuntu)

Deploy con Docker, accesible en el puerto **8501** (sin HTTPS todavía). La misma
imagen sirve para el VPS de prueba y, después, para el servidor de Gilberto.

## 🔒 Acceso con contraseña (login básico)

La app pide una contraseña antes de mostrar el inventario y la fórmula (datos
comerciales sensibles). La contraseña vive en `APP_PASSWORD`, que el deploy
persiste en `${APP_DIR}/.env` (nunca en el repo).

- **Elegir la tuya:** `APP_PASSWORD='miClave' bash deploy/setup.sh`
- **Si no pasás ninguna:** el script **genera una al azar**, la guarda en `.env`
  y la imprime **una sola vez** al terminar. Anotala.
- **Cambiarla:** editá `${APP_DIR}/.env` y volvé a correr el redeploy.

> ⚠️ Esto es un portón básico y la app corre por **HTTP** (la contraseña viaja
> sin cifrar). Para protección real, poné **Caddy/nginx con HTTPS** delante del
> `:8501` (ver final del documento).

## Opción A — un solo comando (recomendado)

En el VPS (como `root` o con `sudo`):

```bash
curl -fsSL https://raw.githubusercontent.com/Juninho2604/GILBERTO/claude/new-session-5k4aar/deploy/setup.sh | bash
```

El script instala Docker si falta, clona la rama, construye la imagen, levanta el
contenedor y abre el puerto. Al terminar imprime la URL `http://<IP>:8501`.

> **Repo privado:** si el repositorio no es público, el `git clone` fallará.
> Generá un token de GitHub (Settings → Developer settings → Personal access
> tokens, scope `repo`) y corré:
> ```bash
> curl -fsSL https://raw.githubusercontent.com/Juninho2604/GILBERTO/claude/new-session-5k4aar/deploy/setup.sh \
>   | REPO_URL="https://<TOKEN>@github.com/Juninho2604/GILBERTO.git" bash
> ```

## 🔐 HTTPS con dominio gratis (DuckDNS) — recomendado

Para cifrar el tráfico (que la contraseña no viaje en texto plano) el deploy
puede levantar **Caddy**, que saca y renueva el certificado de Let's Encrypt
solo. Solo necesitás un subdominio gratis de DuckDNS.

**1. Creá el subdominio (una sola vez):**
   - Entrá a <https://www.duckdns.org> (login con Google/GitHub).
   - Creá un subdominio, p. ej. `gilberto`.
   - En "current ip" poné la IP de tu VPS y guardá. Queda `gilberto.duckdns.org`.

**2. Deploy con HTTPS:**
   ```bash
   DOMAIN='gilberto.duckdns.org' APP_PASSWORD='miClave' bash deploy/setup.sh
   ```
   El script levanta Caddy, abre 80/443, **cierra el 8501 al público** (la app
   queda solo detrás de HTTPS) y al terminar imprime `https://gilberto.duckdns.org`.
   El certificado tarda ~30 s la primera vez.

> El dominio se guarda en `.env`, así que en los próximos redeploys ya no hace
> falta pasarlo: `bash deploy/setup.sh` mantiene el HTTPS.
> Para **volver a HTTP** sin dominio, borrá la línea `DOMAIN=` del `.env`.

## Opción B — paso a paso

```bash
# 1. Docker (si no está)
curl -fsSL https://get.docker.com | sh

# 2. Código
git clone -b claude/new-session-5k4aar https://github.com/Juninho2604/GILBERTO.git
cd GILBERTO

# 3. Levantar
docker compose up -d --build

# 4. Abrir el puerto (si ufw está activo)
ufw allow 8501/tcp

# 5. Ver
curl -s http://localhost:8501/_stcore/health   # -> "ok"
```

Abrí `http://<IP-DEL-VPS>:8501` en el navegador.

## Operación

```bash
docker compose logs -f                 # ver logs
docker compose restart                 # reiniciar
docker compose down                    # detener
bash deploy/setup.sh                   # actualizar al último commit y redeployar
PORT=9000 bash deploy/setup.sh         # usar otro puerto
```

## Notas para Contabo

- En el panel de Contabo no hay firewall en la nube por defecto: alcanza con
  abrir el puerto en `ufw` si lo tenés activo.
- El contenedor reinicia solo (`restart: unless-stopped`); sobrevive reboots.
- Más adelante, para HTTPS con dominio: poné Caddy o nginx delante del `:8501`.
