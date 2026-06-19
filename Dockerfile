# Optimizador de Mezclas RAEE — imagen para desplegar en un VPS propio.
#
#   docker build -t raee-optimizer .
#   docker run -d --name raee -p 8501:8501 raee-optimizer
#
# Queda servido en http://<tu-vps>:8501  (poné un nginx/caddy delante para TLS).
FROM python:3.11-slim

# CBC (solver del optimizador) viene precompilado en el wheel de PuLP; no hace
# falta toolchain. libgomp1 es la dependencia de runtime de CBC.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app/src \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "src/app/simulator.py"]
