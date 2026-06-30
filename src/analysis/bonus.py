"""Bono de éxito — cálculo del bono definido en el presupuesto (§11).

Tres piezas independientes (change-order "Motor RAEE — Cálculo del bono de éxito"):

- **Base** = *sub-pago histórico*: la suma, sobre los 53 lotes, de cuánto habría
  rendido la mezcla **óptima** por encima de lo que la refinería **pagó** en
  realidad — el dinero que el modelo "destraba".
- **Disparador** = la *mejora* de uno o varios envíos reales por encima del
  **10%**: prueba de que el modelo funciona (por encima del ruido del ensayo).
- **Bono** = ``tasa_bono`` (15%) × base, una vez cumplido el disparador.

Reglas (del change-order):

- Todas las comparaciones se hacen **a los precios del envío correspondiente**
  (no a los de hoy); como el lado "real" usa las leyes medidas de la liquidación
  y el "óptimo" es proyección del modelo, ambos se valorizan con los **mismos
  precios por lote** para que el mercado no distorsione (§3, §3.4).
- ``sub_pago_i = max(0, valor_optimo_i − valor_real_i)``: el azar de la
  estimación no resta a la base.
- La *mejora* se puede medir sobre una **ventana** de los primeros envíos
  (promediados) para que el disparador sea robusto al ruido (§2).

Este módulo es **aritmética pura** sobre datos ya calculados (``historical.py``);
no toca la valorización ni el optimizador.
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
    modo_subpago: str = "historico_unico"  # | "por_envio"
    baseline_mejora: str = "ingenua_proyeccion"
    modo_liquidacion_bono: str = "proyeccion"  # | "reconciliado_real"


# --------------------------------------------------------------------------- #
# Resultados
# --------------------------------------------------------------------------- #
@dataclass
class SubPagoLot:
    """Sub-pago de un lote: óptimo − real, con su confianza."""

    customer_lot: object
    valor_real_usd: float
    valor_optimo_usd: float
    sub_pago_usd: float
    low_conf_share: float                 # 0..1 del peso en pilas de baja confianza
    valor_aswas_usd: float = 0.0          # valorización del modelo de la mezcla "tal cual"


@dataclass
class SubPagoResult:
    """Sub-pago histórico (la base del bono) con banda de confianza.

    La base ``total_usd = Σ max(0, óptimo − real)`` se descompone en dos partes,
    para no presentar un número inflado:

    - ``mixing_usd``: ganancia **verificable** de re-mezclar (óptimo − "tal cual",
      ambos en el mundo estimado) — el efecto real del optimizador.
    - ``projection_usd``: la brecha entre la valorización estimada y el pago
      **medido** real — proyección que **se reconcilia** contra las liquidaciones.
    """

    total_usd: float                      # base puntual (óptimo − real)
    firm_usd: float                       # piso: porción de alta confianza por pila
    low_conf_usd: float                   # porción apoyada en pilas frágiles
    low_conf_share: float                 # low_conf_usd / total
    n_lots: int                           # lotes que aportan sub-pago (>0)
    mixing_usd: float = 0.0               # ganancia de mezcla verificable (mismo mundo)
    projection_usd: float = 0.0           # brecha de proyección (a reconciliar con real)
    lots: list[SubPagoLot] = field(default_factory=list)


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
    base_usd: float                       # sub-pago histórico
    tasa: float
    umbral: float
    subpago: SubPagoResult
    mejora: Optional[MejoraResult] = None


# --------------------------------------------------------------------------- #
# 1) Sub-pago histórico — la base
# --------------------------------------------------------------------------- #
def subpago_historico(
    lots: Sequence[dict], config: Optional[BonusConfig] = None
) -> SubPagoResult:
    """Suma ``max(0, óptimo − real)`` sobre los lotes resolubles del histórico.

    ``lots`` son los comparativos por lote (``HistoryAnalysis.lots`` serializado):
    cada uno con ``actual_net_usd`` (real, leyes medidas) y ``model_optimal_usd``
    (óptimo del modelo). Si el lote trae ``sub_pago_usd``/``low_conf_share`` se
    usan; si no, ``sub_pago`` se deriva de los dos valores.
    """
    config = config or BonusConfig()
    rows: list[SubPagoLot] = []
    for L in lots:
        opt = L.get("model_optimal_usd")
        if opt is None:
            continue
        real = float(L.get("actual_net_usd") or 0.0)
        sp = L.get("sub_pago_usd")
        sp = max(0.0, opt - real) if sp is None else float(sp)
        if sp <= 0:
            continue
        share = float(L.get("low_conf_share", 0.0) or 0.0)
        aswas = float(L.get("model_aswas_usd") or 0.0)
        rows.append(SubPagoLot(
            customer_lot=L.get("customer_lot"),
            valor_real_usd=real, valor_optimo_usd=float(opt),
            sub_pago_usd=sp, low_conf_share=share, valor_aswas_usd=aswas,
        ))
    total = sum(r.sub_pago_usd for r in rows)
    low = sum(r.sub_pago_usd * r.low_conf_share for r in rows)
    firm = max(0.0, total - low)
    # Descomposición honesta: ganancia de mezcla verificable vs. brecha de proyección.
    mixing = sum(max(0.0, r.valor_optimo_usd - r.valor_aswas_usd)
                 for r in rows if r.valor_aswas_usd > 0)
    projection = max(0.0, total - mixing)
    rows.sort(key=lambda r: -r.sub_pago_usd)
    return SubPagoResult(
        total_usd=total, firm_usd=firm, low_conf_usd=low,
        low_conf_share=(low / total if total else 0.0),
        n_lots=len(rows), mixing_usd=mixing, projection_usd=projection, lots=rows,
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
    el umbral; si no, el bono queda en 0."""
    config = config or BonusConfig()
    sp = subpago_historico(lots, config)
    mj = mejora_envio(envios, config) if envios else None
    activado = bool(mj and mj.supera_umbral)
    monto = config.tasa_bono * sp.total_usd if activado else 0.0
    monto_firme = config.tasa_bono * sp.firm_usd if activado else 0.0
    return BonoResult(
        activado=activado, monto_usd=monto, monto_firme_usd=monto_firme,
        base_usd=sp.total_usd, tasa=config.tasa_bono, umbral=config.umbral_mejora,
        subpago=sp, mejora=mj,
    )
