"""Modelo de datos del dominio (sección 4 del brief).

Estructuras puras (dataclasses) para inventario, precios y términos del
contrato. Sin lógica de UI ni de cálculo de valorización (eso vive en
``valuation.py``). Todos los parámetros del contrato son editables: nada
está hardcodeado dentro de la fórmula.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

# Gramos por onza troy. Constante exacta usada por la refinería para
# convertir gramos de metal precioso a onzas al valorizar.
TROY_OUNCE_G: float = 31.1034768

# Metales considerados en el contrato (sección 2 del brief).
METALS: tuple[str, ...] = ("CU", "AU", "AG", "PT", "PD")
PRECIOUS_METALS: tuple[str, ...] = ("AU", "AG", "PT", "PD")


class Category(str, Enum):
    """Categorías de inventario. Solo ``RAEE`` entra en las mezclas para JX."""

    RAEE = "RAEE"            # 630 — Inventory RAEE (alcance del simulador)
    NON_FERROUS = "NON_FERROUS"  # 650 — No ferroso (se vende aparte)
    FERROUS = "FERROUS"          # 651 — Ferroso (se vende aparte)


class GradeSource(str, Enum):
    """Origen de una ley, para que el usuario sepa de cuál fiarse (sección 6)."""

    MANUAL = "manual"
    ESTIMATED = "estimada"      # despejada del histórico por regresión
    MARKET = "mercado"          # estimada por tipo de material (piso conservador)
    LAB = "laboratorio"         # ensayo real


@dataclass
class InventoryItem:
    """Una pila clasificada en inventario (sección 4.1).

    Las leyes son ``grade_cu`` en fracción (0.21 = 21%) y el resto en g/t.
    Hoy no existen en el inventario real: se cargan por estimación (sección 6)
    o por laboratorio, y deben poder editarse en la UI.
    """

    code: str
    name: str
    category: Category = Category.RAEE
    quantity_kg: float = 0.0          # stock disponible (WMT)
    moisture: float = 0.01            # fracción de humedad (default editable)
    grade_cu: float = 0.0             # ley de cobre (fracción)
    grade_au: float = 0.0             # ley de oro (g/t)
    grade_ag: float = 0.0             # ley de plata (g/t)
    grade_pt: float = 0.0             # ley de platino (g/t)
    grade_pd: float = 0.0             # ley de paladio (g/t)
    grade_source: GradeSource = GradeSource.MANUAL
    grade_confidence: Optional[float] = None  # 0..1, opcional

    def grade(self, metal: str) -> float:
        """Devuelve la ley de un metal por su símbolo (``"CU"``, ``"AU"``, ...)."""
        metal = metal.upper()
        if metal not in METALS:
            raise KeyError(f"Metal desconocido: {metal!r}")
        return getattr(self, f"grade_{metal.lower()}")

    @property
    def is_raee(self) -> bool:
        return self.category == Category.RAEE


@dataclass
class MetalPrices:
    """Precios del día (sección 4.2).

    ``price_cu`` en USD/tonelada; el resto en USD/onza troy. Editables.
    """

    price_cu: float
    price_au: float
    price_ag: float
    price_pt: float
    price_pd: float

    def price(self, metal: str) -> float:
        metal = metal.upper()
        if metal not in METALS:
            raise KeyError(f"Metal desconocido: {metal!r}")
        return getattr(self, f"price_{metal.lower()}")


@dataclass
class RecoveryRule:
    """Parámetros de Recovery Rate de un metal precioso (tabla 3.3).

    RR = clamp((g - deduction) / g, floor, cap).

    - ``cap``: tope superior (``None`` = sin tope).
    - ``floor_zero``: si ``True`` aplica ``MAX(0, ...)`` antes del tope.
    - ``paid``: si ``False`` el metal no se paga (RR = 0). Útil para PT, cuyos
      términos son desconocidos (sección 7, pregunta 5).
    """

    deduction: float
    cap: Optional[float] = None
    floor_zero: bool = False
    paid: bool = True


@dataclass
class ContractTerms:
    """Términos de la refinería (sección 4.3). Todos parametrizables."""

    # Refining charges (RC), descontados del precio.
    rc_cu: float = 0.0   # USD/tonelada
    rc_au: float = 0.0   # USD/onza
    rc_ag: float = 0.0
    rc_pt: float = 0.0
    rc_pd: float = 0.0

    # Cobre: deduce puntos porcentuales de la ley (RR = (g - cu_deduction) / g).
    cu_deduction: float = 0.03

    # Reglas de RR de metales preciosos (tabla 3.3).
    au_rule: RecoveryRule = field(
        default_factory=lambda: RecoveryRule(deduction=7.0, cap=0.96)
    )
    ag_rule: RecoveryRule = field(
        default_factory=lambda: RecoveryRule(deduction=100.0, cap=0.95, floor_zero=True)
    )
    pd_rule: RecoveryRule = field(
        default_factory=lambda: RecoveryRule(deduction=18.0, cap=None, floor_zero=True)
    )
    # PT: términos desconocidos. Por defecto no se paga (CONFIRMAR con Gilberto).
    pt_rule: RecoveryRule = field(
        default_factory=lambda: RecoveryRule(deduction=0.0, paid=False)
    )

    # Cargos de procesamiento (se restan).
    tc_rate: float = 600.0          # treatment charge, USD/tonelada seca (DMT)
    shred_rate: float = 100.0       # shredding charge, USD/tonelada húmeda (WMT)
    min_lot_charge: float = 0.0     # CONFIRMAR
    moisture_penalty: float = 0.0   # CONFIRMAR

    def rc(self, metal: str) -> float:
        metal = metal.upper()
        if metal not in METALS:
            raise KeyError(f"Metal desconocido: {metal!r}")
        return getattr(self, f"rc_{metal.lower()}")

    def rule(self, metal: str) -> RecoveryRule:
        metal = metal.upper()
        if metal not in PRECIOUS_METALS:
            raise KeyError(f"Sin RecoveryRule para {metal!r}")
        return getattr(self, f"{metal.lower()}_rule")


def default_prices() -> MetalPrices:
    """Precios de referencia observados (planilla 2025-01-23, sección 10).

    Cargar como defaults **editables**; no asumir vigentes. Pt sin dato → 0.
    """
    return MetalPrices(
        price_cu=11_803.79,
        price_au=4_500.0,
        price_ag=64.34,
        price_pt=0.0,
        price_pd=1_569.0,
    )


def default_terms() -> ContractTerms:
    """Términos de referencia observados (planilla 2025-01-23, sección 10)."""
    return ContractTerms(
        rc_cu=300.0,
        rc_au=5.0,
        rc_ag=0.5,
        rc_pt=0.0,
        rc_pd=14.0,
        tc_rate=600.0,
        shred_rate=100.0,
        min_lot_charge=0.0,
        moisture_penalty=0.0,
    )
