# Deploy en un VPS (Contabo / Ubuntu)

Deploy con Docker, accesible en el puerto **8501** (sin HTTPS todavía). La misma
imagen sirve para el VPS de prueba y, después, para el servidor de Gilberto.

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
