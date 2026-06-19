# Optimizador de Mezclas RAEE — Servicios Megabytes, C.A.

Simulador (y, a futuro, optimizador) de mezclas de chatarra electrónica (RAEE)
para venta a refinería. Calcula el **valor neto en USD** que pagaría la
refinería por un lote, replicando exactamente la planilla histórica.

El brief completo del proyecto está en [`CLAUDE.md`](./CLAUDE.md).

## Estado

**Fase 1 (Simulador) y Fase 2 (Optimizador): implementadas.**

- ✅ Núcleo de valorización (`src/domain/valuation.py`), puro y testeado.
- ✅ Modelo de datos con términos del contrato **parametrizables**.
- ✅ Test de aceptación del **Apéndice A** reproducido exactamente.
- ✅ Carga del **inventario real** y del **histórico de 53 lotes** desde los `.xlsx`.
- ✅ **Estimación de leyes** (sección 6) por mínimos cuadrados desde el
  histórico: **25/40** pilas con stock cubiertas (15 pendientes de laboratorio),
  validada reconstruyendo los lotes (error mediano Au ~5%, Cu ~2%).
- ✅ **Optimizador (Fase 2)** MILP que reparte el inventario en lotes para
  maximizar el pago de la refinería.
- ✅ Simulador + Optimizador en una app Streamlit con dos pestañas.

**El objetivo del optimizador** (definido por el usuario): encontrar las mezclas
óptimas para que la refinería pague lo máximo, aprovechando cada material. El
hallazgo clave: como el oro domina y su deducción es **por tonelada**, conviene
**no diluir** las pilas ricas en oro con relleno pobre. Repartir el inventario
en **2 lotes** (uno rico a ~175 g/t de Au, otro de relleno) paga ~$615k vs.
~$606k de una sola mezcla (**+1,5%**), y supera también a enviar todo por
separado ($612k).

> ⚠️ Las leyes son **estimadas** y están a validar con ensayos reales. Varias
> preguntas abiertas (sección 7) afectan el óptimo: tamaño mínimo de lote, si el
> platino se paga, y si los términos del contrato son fijos o negociados.

## Estructura

```
src/
  domain/
    models.py        # InventoryItem, MetalPrices, ContractTerms, RecoveryRule
    valuation.py     # LA FÓRMULA (sección 3): value_lot / value_blend
  data/
    load_inventory.py   # parsea inventory.xlsx
    load_history.py     # parsea refining_history.xlsx (53 lotes)
    recipes.py          # parser de recetas históricas
    estimate_grades.py  # estimación de leyes por regresión (sección 6)
    build_grade_table.py# genera data/estimated_grades.csv
    bootstrap.py / seed.py
  optimize/
    optimizer.py     # Fase 2: optimize_blend / optimize_partition (MILP, PuLP)
  app/
    simulator.py     # UI Streamlit (Simulador + Optimizador)
    report.py        # reporte de análisis de extremo a extremo (CLI)
data/
  inventory.xlsx · refining_history.xlsx · estimated_grades.csv
tests/
  test_valuation.py · test_recipes.py · test_data_pipeline.py · test_optimizer.py
```

## Uso

Requiere Python ≥ 3.10.

```bash
# Instalar dependencias (incluye test y, opcionalmente, optimización)
pip install -e ".[dev]"

# Correr los tests (incluye el test de aceptación del Apéndice A)
pytest

# Lanzar el simulador + optimizador
streamlit run src/app/simulator.py

# Reporte de análisis de extremo a extremo por consola
python -m app.report          # (con PYTHONPATH=src, o tras `pip install -e .`)

# Regenerar la tabla de leyes estimadas (data/estimated_grades.csv)
python -m data.build_grade_table
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

1. **Validar las leyes estimadas** contra ensayos de laboratorio (las 25
   estimadas) y **medir las 15 pendientes** que no aparecen en recetas.
2. Confirmar con Gilberto las preguntas abiertas (sección 7) que cambian el
   óptimo: **tamaño mínimo/objetivo de lote**, si el **platino se paga**, y si
   los términos del contrato son fijos o negociados por envío.
3. Afinar el optimizador con las reglas reales de JX (mínimos/máximos de ley,
   penalización de contaminantes, rechazo por tamaño) cuando se conozcan.
4. Mejorar la separación de pilas que hoy quedan en grupos ambiguos
   (`12 + 998`, `37 + 38`, etc.) pidiendo los kg de cada componente.
