# Optimizador de Mezclas RAEE — Servicios Megabytes, C.A.

Simulador (y, a futuro, optimizador) de mezclas de chatarra electrónica (RAEE)
para venta a refinería. Calcula el **valor neto en USD** que pagaría la
refinería por un lote, replicando exactamente la planilla histórica.

El brief completo del proyecto está en [`CLAUDE.md`](./CLAUDE.md).

## Estado

**Fase 1 (Simulador) y Fase 2 (Optimizador): implementadas. Interfaz pulida en
Python (Streamlit), 100% sin frontend JS.**

- ✅ Núcleo de valorización (`src/domain/valuation.py`), puro y testeado.
- ✅ Modelo de datos con términos del contrato **parametrizables**.
- ✅ Test de aceptación del **Apéndice A** reproducido exactamente.
- ✅ Carga del **inventario real** y del **histórico de 53 lotes** desde los `.xlsx`.
- ✅ **Estimación de leyes** (sección 6) por mínimos cuadrados desde el
  histórico: **25/40** pilas con stock cubiertas (15 pendientes de laboratorio),
  validada reconstruyendo los lotes (error mediano Au ~5%, Cu ~2%).
- ✅ **Optimizador (Fase 2)** MILP que reparte el inventario en lotes para
  maximizar el pago de la refinería.
- ✅ **Motor de explicación** (`src/analysis/explain.py`): cada optimización
  dice *por qué* es la mejor decisión, en términos del contrato.
- ✅ **Estudio del histórico** (`src/analysis/historical.py`): compara cada lote
  real contra la mezcla óptima y cuantifica cuánto se hubiera ganado de más.
- ✅ **Interfaz de 5 páginas** (Panel · Simulador · Optimizador · Histórico ·
  Caso de negocio) con diseño propio, modo privado y deploy dockerizado.

### Confidencialidad

Las pilas se muestran **por número** (la leyenda de Gilberto: `#1`, `#2`, `#14`…)
y el nombre real solo aparece si se activa el **modo privado** en la barra
lateral (apagado por defecto). Así una demo no filtra materiales ni fórmulas.

### Honestidad del caso de negocio

El estudio del histórico es deliberadamente **honesto**: re-optimizar cada lote
que Gilberto ya envió solo agrega **+0,1%** — sus mezclas ya eran casi óptimas, y
el modelo lo confirma (fidelidad a nivel dinero: **±3%** vs. el pago real). El
valor del optimizador aparece **hacia adelante**, sobre el stock acumulado
(**+1,5%**, ~$9k por ciclo vs. una sola mezcla), más el **metal sub-umbral**
(Ag/Pd que históricamente pagó $0, ~$12,6k) que el sistema detecta para no perderlo.

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
  analysis/
    explain.py       # por qué una partición es la mejor decisión
    historical.py    # estudio del histórico (real vs. óptimo, % extra)
    build_analysis.py# precomputa data/history_analysis.json para la UI
  app/
    simulator.py     # entrada Streamlit (navegación de 5 páginas)
    ui.py            # sistema de diseño (CSS, KPIs, etiquetas confidenciales)
    sidebar.py       # precios, términos del contrato y modo privado
    data_access.py   # carga cacheada (histórico, inventario, óptimo)
    views/           # panel · simulador · optimizador · historico · negocio
    report.py        # reporte de análisis de extremo a extremo (CLI)
data/
  inventory.xlsx · refining_history.xlsx · estimated_grades.csv
  history_analysis.json   # artefacto precomputado del estudio del histórico
tests/
  test_valuation.py · test_recipes.py · test_data_pipeline.py
  test_optimizer.py · test_analysis.py
```

## Uso

Requiere Python ≥ 3.10.

```bash
# Instalar dependencias (incluye test y, opcionalmente, optimización)
pip install -e ".[dev]"

# Correr los tests (incluye el test de aceptación del Apéndice A)
pytest

# Lanzar la app (Panel · Simulador · Optimizador · Histórico · Caso de negocio)
streamlit run src/app/simulator.py

# Reporte de análisis de extremo a extremo por consola
python -m app.report          # (con PYTHONPATH=src, o tras `pip install -e .`)

# Regenerar el artefacto del histórico (tras cambiar leyes/precios/términos)
python -m analysis.build_analysis

# Regenerar la tabla de leyes estimadas (data/estimated_grades.csv)
python -m data.build_grade_table
```

En el **Simulador**, cargá un valor en la columna **blend_kg** de las pilas que
querés mezclar y mirá el resultado en vivo. El **Optimizador** arma las mezclas
solo y explica por qué. El **Histórico** compara cada lote real con su óptimo, y
el **Caso de negocio** proyecta el valor para fijarle precio al sistema.

## Deploy en un VPS (Docker)

```bash
docker compose up -d --build        # queda en http://<tu-vps>:8501
# o sin compose:
docker build -t raee-optimizer . && docker run -d -p 8501:8501 raee-optimizer
```

Poné un reverse proxy (nginx/Caddy) delante para HTTPS. El artefacto del
histórico (`data/history_analysis.json`) viaja en la imagen; para regenerarlo:
`docker compose exec raee-optimizer python -m analysis.build_analysis`.

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
