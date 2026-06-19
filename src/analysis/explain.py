"""Por qué una mezcla / partición es la mejor decisión (lenguaje natural).

El optimizador no debe ser una caja negra: cada decisión tiene una razón
económica concreta y explicable. Este módulo traduce una valorización a las
**palancas** que la refinería penaliza o premia, y contrasta una partición
contra la alternativa ingenua (todo en una sola mezcla) para justificar el
"por qué" en términos que Gilberto pueda auditar.

Las palancas (sección 3 del brief):
- **Deducción por tonelada**: la refinería descuenta 7 g/t de Au, 100 g/t de
  Ag, 18 g/t de Pd y 3 puntos de Cu *antes* de pagar. Esa deducción se aplica
  sobre TODA la masa del lote, así que diluir una pila rica con relleno pobre
  regala metal.
- **Tope de recuperación (cap)**: Au recupera como máximo 96%, Ag 95%. Si la
  ley ya llega al tope, subirla más no agrega valor; conviene mandar ese
  excedente de riqueza a "levantar" otro lote.
- **Umbral (piso)**: si la ley de la mezcla no supera la deducción, ese metal
  paga 0. Mezclar una pila sub-umbral con una rica lo "rescata".
- **Cargos por tonelada**: tratamiento (600/Dt) y trituración (100/t) cobran
  por peso. El relleno muerto sin metal solo suma cargos.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional, Sequence

from domain.models import METALS, PRECIOUS_METALS, ContractTerms, MetalPrices
from domain.valuation import LotValuation

_METAL_NAME = {"CU": "cobre", "AU": "oro", "AG": "plata", "PT": "platino", "PD": "paladio"}
_USD = "${:,.0f}".format


@dataclass
class MetalDriver:
    """Estado de un metal dentro de un lote: la palanca que explica su aporte."""

    metal: str
    grade: float
    rr: float
    amount_usd: float
    status: str            # "capped" | "productive" | "below_threshold" | "negligible"
    headline: str          # frase corta explicando el estado

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LotRationale:
    """Caracterización de un lote y por qué quedó así."""

    role: str                       # "rico" | "relleno" | "mixto"
    net_usd: float
    per_kg: float
    wmt: float
    drivers: list[MetalDriver] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


@dataclass
class OptimizationExplanation:
    """Explicación completa de una partición frente a la mezcla única."""

    headline: str
    reference_single_usd: float     # valor si se mandara todo en una sola mezcla
    partition_usd: float            # valor de la partición elegida
    gain_usd: float
    gain_pct: float
    lots: list[LotRationale] = field(default_factory=list)
    bullets: list[str] = field(default_factory=list)  # razones de alto nivel

    def to_dict(self) -> dict:
        return {
            "headline": self.headline,
            "reference_single_usd": self.reference_single_usd,
            "partition_usd": self.partition_usd,
            "gain_usd": self.gain_usd,
            "gain_pct": self.gain_pct,
            "lots": [l.to_dict() for l in self.lots],
            "bullets": self.bullets,
        }


# --------------------------------------------------------------------------- #
# Caracterización de un lote
# --------------------------------------------------------------------------- #
def _metal_driver(metal: str, v: LotValuation, terms: ContractTerms) -> MetalDriver:
    r = v.metals[metal]
    name = _METAL_NAME[metal]
    cap = None
    if metal in PRECIOUS_METALS:
        cap = terms.rule(metal).cap

    # Sin aporte significativo.
    if r.amount_usd < 1.0 and r.rr <= 0:
        if metal in PRECIOUS_METALS:
            ded = terms.rule(metal).deduction
            return MetalDriver(
                metal, r.grade, r.rr, r.amount_usd, "below_threshold",
                f"{name.capitalize()}: ley {r.grade:.0f} g/t por debajo de la "
                f"deducción de {ded:.0f} g/t → paga 0 (se rescata mezclándolo).",
            )
        return MetalDriver(metal, r.grade, r.rr, r.amount_usd, "negligible",
                           f"{name.capitalize()}: aporte despreciable.")

    # En el tope de recuperación.
    if cap is not None and abs(r.rr - cap) < 1e-3:
        return MetalDriver(
            metal, r.grade, r.rr, r.amount_usd, "capped",
            f"{name.capitalize()}: recuperación en el tope ({cap*100:.0f}%); "
            f"subir más la ley no agrega valor, conviene usar el excedente en otro lote.",
        )

    return MetalDriver(
        metal, r.grade, r.rr, r.amount_usd, "productive",
        f"{name.capitalize()}: recupera {r.rr*100:.0f}% → {_USD(r.amount_usd)}.",
    )


def explain_lot(v: LotValuation, terms: ContractTerms) -> LotRationale:
    """Caracteriza un lote: su rol y la palanca de cada metal."""
    drivers = [_metal_driver(m, v, terms) for m in METALS]
    paid = {d.metal: d.amount_usd for d in drivers}
    au = v.metals["AU"].grade

    # Rol del lote según riqueza en oro (el metal que suele mandar).
    capped = any(d.status == "capped" for d in drivers if d.metal in ("AU", "AG"))
    if au >= 120 or capped or v.result_per_kg >= 20:
        role = "rico"
    elif au <= 40 and v.result_per_kg < 10:
        role = "relleno"
    else:
        role = "mixto"

    notes: list[str] = []
    lost = [d for d in drivers if d.status == "below_threshold"]
    if lost:
        notes.append(
            "Metal por debajo del umbral en este lote: "
            + ", ".join(_METAL_NAME[d.metal] for d in lost)
            + " (no paga solo)."
        )
    if role == "rico":
        notes.append(
            "Lote de alta ley: concentra el metal valioso para superar topes y "
            "umbrales; no conviene diluirlo con relleno pobre."
        )
    elif role == "relleno":
        notes.append(
            "Lote de relleno: aporta sobre todo cobre/peso. Mandarlo aparte evita "
            "que las deducciones por tonelada del oro/plata se apliquen sobre él."
        )
    return LotRationale(
        role=role,
        net_usd=v.net_value_usd,
        per_kg=v.result_per_kg,
        wmt=v.wmt,
        drivers=drivers,
        notes=notes,
    )


# --------------------------------------------------------------------------- #
# Explicación de una partición frente a la mezcla única
# --------------------------------------------------------------------------- #
def explain_partition(
    lot_valuations: Sequence[LotValuation],
    single_blend: Optional[LotValuation],
    terms: ContractTerms,
) -> OptimizationExplanation:
    """Explica por qué repartir en estos lotes supera a mandar todo junto.

    ``lot_valuations`` son los lotes de la partición; ``single_blend`` es la
    valorización de mandar exactamente el mismo material en una sola mezcla
    (la alternativa ingenua). Si es ``None`` no se computa la ganancia relativa.
    """
    partition_usd = sum(v.net_value_usd for v in lot_valuations)
    ref = single_blend.net_value_usd if single_blend else partition_usd
    gain = partition_usd - ref
    gain_pct = (100.0 * gain / ref) if ref else 0.0

    lots = [explain_lot(v, terms) for v in lot_valuations]

    bullets: list[str] = []
    n = len(lot_valuations)
    if n > 1 and single_blend is not None and gain > 1.0:
        ricos = [l for l in lots if l.role == "rico"]
        relleno = [l for l in lots if l.role == "relleno"]
        if ricos and relleno:
            bullets.append(
                f"Separar el material rico del relleno paga {_USD(gain)} más "
                f"(+{gain_pct:.1f}%) que mandar todo en una sola mezcla: evita "
                f"aplicar las deducciones por tonelada (7 g/t Au, 100 g/t Ag) "
                f"sobre el peso pobre."
            )
        else:
            bullets.append(
                f"Repartir en {n} lotes paga {_USD(gain)} más (+{gain_pct:.1f}%) "
                f"que una sola mezcla."
            )
    elif n == 1:
        bullets.append(
            "Conviene un solo lote: el material es homogéneo y separarlo no "
            "supera umbrales ni evita diluciones que justifiquen otro envío."
        )

    # Palancas concretas observadas en la partición.
    capped_metals = sorted({
        d.metal for l in lots for d in l.drivers if d.status == "capped"
    })
    if capped_metals:
        bullets.append(
            "Lotes con recuperación en el tope ("
            + ", ".join(_METAL_NAME[m] for m in capped_metals)
            + "): la riqueza extra se aprovechó para levantar otros metales en vez "
            "de desperdiciarse sobre el tope."
        )
    rescued = sorted({
        d.metal for l in lots for d in l.drivers
        if d.status == "productive" and d.metal in ("AG", "PD")
    })
    if rescued:
        bullets.append(
            "Metales rescatados por la mezcla ("
            + ", ".join(_METAL_NAME[m] for m in rescued)
            + "): superan el umbral de deducción gracias a combinarse con pilas ricas."
        )

    if gain > 1.0:
        headline = (
            f"Repartir en {n} lote(s) paga {_USD(partition_usd)} "
            f"(+{_USD(gain)}, {gain_pct:+.1f}%) frente a la mezcla única."
        )
    else:
        headline = f"La mejor decisión es {n} lote(s): {_USD(partition_usd)}."

    return OptimizationExplanation(
        headline=headline,
        reference_single_usd=ref,
        partition_usd=partition_usd,
        gain_usd=gain,
        gain_pct=gain_pct,
        lots=lots,
        bullets=bullets,
    )
