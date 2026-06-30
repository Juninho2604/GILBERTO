"""Bono de éxito — cálculo del bono definido en el presupuesto (§11).

Tres piezas independientes:

- **Base** = *rescate demostrado*: el valor del metal que la mezcla **"tal cual"**
  (el método que ya usaba Gilberto) dejaba en **$0** por caer bajo el umbral de la
  refinería, y que el **optimizador** logra cobrar al mezclarlo por encima del
  umbral. Es, exactamente, "el material que no se hubiese cobrado, pero que con el
  optimizador logramos que se cobrara" — medido en el mismo mundo (leyes
  estimadas), así que aísla el efecto del optimizador sin sesgo de estimación.
- **Disparador** = la *mejora* de uno o varios envíos reales por encima del
  **10%** (piso de ruido del ensayo).
- **Bono** = ``tasa_bono`` (15%) × base, una vez cumplido el disparador.

Reglas (del change-order): comparaciones a los **mismos precios por lote** (no a
los de hoy); el bono es una estimación que **se reconcilia** con los datos reales.
Este módulo es aritmética pura sobre datos ya calculados (``historical.py``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence


# --------------------------------------------------------------------------- #
# Configuración (parametrizable desde la UI — §4)
# --------------------------------------------------------------------------- #
@dataclass
class BonusConfig:
    umbral_mejora: float = 0.10            # disparador del bono (10%)
    tasa_bono: float = 0.15               # 15% de la base
    ventana_envios: int = 1               # nº de envíos reales para medir la mejora
    precios: str = "del_envio"            # nunca "de_hoy"
    modo_liquidacion_bono: str = "proyeccion"  # | "reconciliado_real"


# --------------------------------------------------------------------------- #
# Resultados
# --------------------------------------------------------------------------- #
@dataclass
class RescateLot:
    """Rescate de un lote: metal que pasaba a $0 y el optimizador cobra."""

    customer_lot: object
    rescatado_usd: float
    low_conf_share: float                 # 0..1 del peso en pilas de baja confianza


@dataclass
class RescateResult:
    """Rescate histórico (la base del bono) con banda de confianza."""

    total_usd: float                      # base: Σ rescate por lote
    firm_usd: float                       # piso: porción de alta confianza por pila
    low_conf_usd: float                   # porción apoyada en pilas frágiles
    low_conf_share: float                 # low_conf_usd / total
    n_lots: int                           # lotes que aportan rescate (>0)
    lots: list[RescateLot] = field(default_factory=list)


@dataclass
class MejoraResult:
    """Mejora de un envío (o ventana de envíos) — el disparador."""

    valor_modelo: float                   # lo que pagó la refinería (real)
    valor_base: float                     # contrafáctico "ingenuo" (proyección)
    mejora: float                         # (modelo − base) / base
    supera_umbral: bool
    ventana: int                          # envíos pedidos
    n_envios: int                         # envíos efectivamente usados


@dataclass
class BonoResult:
    """Estado y monto del bono."""

    activado: bool
    monto_usd: float                      # tasa × base (puntual)
    monto_firme_usd: float                # tasa × base de alta confianza (banda baja)
    base_usd: float                       # rescate histórico
    tasa: float
    umbral: float
    rescate: RescateResult
    mejora: Optional[MejoraResult] = None


# --------------------------------------------------------------------------- #
# 1) Rescate histórico — la base
# --------------------------------------------------------------------------- #
def rescate_historico(
    lots: Sequence[dict], config: Optional[BonusConfig] = None
) -> RescateResult:
    """Suma el **rescate demostrado** sobre los lotes resolubles del histórico.

    ``lots`` son los comparativos por lote (``HistoryAnalysis.lots`` serializado):
    cada uno con ``rescued_usd`` (metal que "tal cual" pagaba $0 y el óptimo cobra)
    y ``low_conf_share``.
    """
    config = config or BonusConfig()
    rows: list[RescateLot] = []
    for L in lots:
        resc = L.get("rescued_usd")
        if resc is None:
            continue
        resc = float(resc)
        if resc <= 0:
            continue
        share = float(L.get("low_conf_share", 0.0) or 0.0)
        rows.append(RescateLot(
            customer_lot=L.get("customer_lot"),
            rescatado_usd=resc, low_conf_share=share,
        ))
    total = sum(r.rescatado_usd for r in rows)
    low = sum(r.rescatado_usd * r.low_conf_share for r in rows)
    firm = max(0.0, total - low)
    rows.sort(key=lambda r: -r.rescatado_usd)
    return RescateResult(
        total_usd=total, firm_usd=firm, low_conf_usd=low,
        low_conf_share=(low / total if total else 0.0),
        n_lots=len(rows), lots=rows,
    )


# --------------------------------------------------------------------------- #
# 2) Mejora de un envío — el disparador
# --------------------------------------------------------------------------- #
def _pair(e) -> tuple[float, float]:
    if isinstance(e, (tuple, list)):
        return float(e[0]), float(e[1])
    return float(e["valor_modelo"]), float(e["valor_base"])


def mejora_envio(
    envios: Sequence, config: Optional[BonusConfig] = None
) -> Optional[MejoraResult]:
    """Mejora de los primeros ``ventana_envios`` envíos reales (promediados).

    Cada envío aporta ``(valor_modelo, valor_base)``: lo que pagó la refinería por
    el envío optimizado (real) y lo que ese material habría rendido sin optimizar
    (contrafáctico ingenuo). Promediar la ventana hace el disparador robusto al
    ruido del ensayo. Devuelve ``None`` si no hay envíos.
    """
    config = config or BonusConfig()
    pares = [_pair(e) for e in envios]
    win = max(1, int(config.ventana_envios))
    use = pares[:win]
    if not use:
        return None
    sm = sum(vm for vm, _ in use)
    sb = sum(vb for _, vb in use)
    mejora = (sm - sb) / sb if sb else 0.0
    return MejoraResult(
        valor_modelo=sm, valor_base=sb, mejora=mejora,
        supera_umbral=mejora > config.umbral_mejora,
        ventana=win, n_envios=len(use),
    )


# --------------------------------------------------------------------------- #
# 3) El bono
# --------------------------------------------------------------------------- #
def calcular_bono(
    lots: Sequence[dict],
    envios: Sequence,
    config: Optional[BonusConfig] = None,
) -> BonoResult:
    """Calcula el bono: ``activado`` y ``monto = tasa × base`` si la mejora supera
    el umbral; si no, el bono queda en 0. La base es el rescate demostrado."""
    config = config or BonusConfig()
    rc = rescate_historico(lots, config)
    mj = mejora_envio(envios, config) if envios else None
    activado = bool(mj and mj.supera_umbral)
    monto = config.tasa_bono * rc.total_usd if activado else 0.0
    monto_firme = config.tasa_bono * rc.firm_usd if activado else 0.0
    return BonoResult(
        activado=activado, monto_usd=monto, monto_firme_usd=monto_firme,
        base_usd=rc.total_usd, tasa=config.tasa_bono, umbral=config.umbral_mejora,
        rescate=rc, mejora=mj,
    )
