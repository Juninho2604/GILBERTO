"""Logging de la aplicación: archivo rotativo en ``data/logs/app.log``.

Primera observabilidad real del sistema: si algo falla en producción, acá queda
la traza (antes no había ningún log que mirar). Módulo en la raíz de ``src``
para que lo puedan importar tanto ``app`` como ``data`` sin cruzar capas.
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parents[1] / "data" / "logs"


def get_logger(name: str = "aurix") -> logging.Logger:
    """Logger con rotación (2 MB × 3 archivos). Idempotente por proceso."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            LOG_DIR / "app.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        logger.addHandler(handler)
    except OSError:
        # Sin permiso de escritura (contenedor de solo lectura): loguear a stderr
        # antes que perder las trazas.
        logger.addHandler(logging.StreamHandler())
    return logger
