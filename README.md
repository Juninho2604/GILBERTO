# Optimizador de Mezclas RAEE — Servicios Megabytes, C.A.

Simulador (y, a futuro, optimizador) de mezclas de chatarra electrónica (RAEE)
para venta a refinería. Calcula el **valor neto en USD** que pagaría la
refinería por un lote, replicando exactamente la planilla histórica.

El brief completo del proyecto está en [`CLAUDE.md`](./CLAUDE.md).

## Estado

**Fase 1 — Simulador (MVP): implementada.**

- ✅ Núcleo de valorización (`src/domain/valuation.py`), puro y testeado.
- ✅ Modelo de datos (`src/domain/models.py`) con términos del contrato
  **parametrizables** (nada hardcodeado).
- ✅ Mezclas: leyes del lote por promedio ponderado por peso seco (sección 3.6).
- ✅ Test de aceptación del **Apéndice A** reproducido exactamente.
- ✅ Simulador en Streamlit con inventario, leyes, precios y términos editables
  y resultado en vivo.

**Pendiente (bloqueante de la Fase 2):** las **leyes por pila** no existen en el
inventario real. Hay que cargarlas por laboratorio o estimarlas desde los 53
lotes históricos (sección 6). El simulador ya permite editarlas y arranca con
una pila de demo (Apéndice A) más los mayores volúmenes con ley pendiente.

## Estructura

```
src/
  domain/
    models.py      # InventoryItem, MetalPrices, ContractTerms, RecoveryRule
    valuation.py   # LA FÓRMULA (sección 3): value_lot / value_blend
  data/
    seed.py        # datos de arranque (sección 10) mientras no haya xlsx
  app/
    simulator.py   # UI Streamlit (Fase 1)
tests/
  test_valuation.py  # Apéndice A + RR + mezclas
```

## Uso

Requiere Python ≥ 3.10.

```bash
# Instalar dependencias (incluye test y, opcionalmente, optimización)
pip install -e ".[dev]"

# Correr los tests (incluye el test de aceptación del Apéndice A)
pytest

# Lanzar el simulador
streamlit run src/app/simulator.py
```

En el simulador, cargá un valor en la columna **blend_kg** de las pilas que
querés mezclar. Para reproducir el Apéndice A, poné `5184` en la fila
*Lote Apéndice A (demo)* → debería dar **net ≈ $70.335,68** y **13,57 USD/kg**.

## Uso del núcleo desde código

```python
from domain.models import default_prices, default_terms
from domain.valuation import value_lot

result = value_lot(
    wmt=5184, moisture=0.009,
    grades={"CU": 0.2113, "AU": 84.4, "AG": 646.0, "PD": 4.3},
    prices=default_prices(), terms=default_terms(),
)
print(result.net_value_usd, result.result_per_kg)
```

## Próximos pasos

1. `data/load_inventory.py` — parsear `inventory.xlsx` real.
2. `data/estimate_grades.py` — estimar leyes desde lotes históricos (sección 6)
   y validarlas contra los ensayos reales.
3. Confirmar con Gilberto las preguntas abiertas (sección 7): reglas de validez,
   objetivo del optimizador, términos del contrato, bug de Cu, Pt, humedad.
4. **Fase 2** — optimizador LP/MILP (`PuLP`/`OR-Tools`).
