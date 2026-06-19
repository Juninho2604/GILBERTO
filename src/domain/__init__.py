"""Dominio puro del Optimizador de Mezclas RAEE.

Contiene el modelo de datos y la lógica de valorización (sección 3 del brief),
sin ninguna dependencia de UI. Es el núcleo testeado del sistema.
"""

from .models import (
    Category,
    ContractTerms,
    InventoryItem,
    MetalPrices,
    METALS,
    PRECIOUS_METALS,
    TROY_OUNCE_G,
    default_prices,
    default_terms,
)
from .valuation import (
    BlendComponent,
    LotValuation,
    MetalResult,
    recovery_rate_cu,
    recovery_rate_precious,
    value_blend,
    value_lot,
)

__all__ = [
    "Category",
    "ContractTerms",
    "InventoryItem",
    "MetalPrices",
    "METALS",
    "PRECIOUS_METALS",
    "TROY_OUNCE_G",
    "default_prices",
    "default_terms",
    "BlendComponent",
    "LotValuation",
    "MetalResult",
    "recovery_rate_cu",
    "recovery_rate_precious",
    "value_blend",
    "value_lot",
]
