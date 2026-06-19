# Servicios Megabytes, C.A. — Optimizador de Mezclas RAEE

> **Especificación del proyecto.** Documento para usar como brief en Claude Code: describe el dominio, la fórmula de valorización, el modelo de datos, el alcance por fases y los datos de referencia. Prosa en español; nombres de campos/clases en inglés.

---

## Cómo usar este documento

1. Colocá este archivo en la raíz del repo (podés renombrarlo `CLAUDE.md` para que Claude Code lo cargue solo).
2. Pedile a Claude Code que arranque por la **Fase 1 (Simulador / MVP)** de la sección 5.
3. Usá el **ejemplo numérico del Apéndice A** como test de aceptación: la implementación de la fórmula debe reproducir esos números antes de seguir.

---

## Estado actual — el bloqueante a resolver primero

⚠️ **Las leyes por pila no existen todavía, y son el insumo de TODO el cálculo.** El inventario solo tiene pesos, no leyes. Sin leyes no hay simulación ni optimización posible: es el cabo suelto que no hay que perder de vista.

**Acción recomendada inmediata:** antes de construir —o en paralelo— generar una **tabla inicial de leyes estimadas** a partir de los 53 lotes históricos (método de la sección 6) y usarla para **sembrar el simulador con números reales, en vez de placeholders**. Esa tabla debe validarse contra los ensayos reales de los lotes antes de confiar en ella. Cubre ~25 de los 40 ítems con stock; los 15 restantes quedan pendientes de laboratorio o carga manual.

---

## 1. Contexto y objetivo

Servicios Megabytes es un negocio de reciclaje de chatarra electrónica (**RAEE** = Residuos de Aparatos Eléctricos y Electrónicos). El negocio acumula material en **pilas** clasificadas (placas madre, boards, procesadores, etc.) y lo vende a una **refinería** (referida como **JX**) que paga según el contenido de metales preciosos y cobre recuperables.

Antes de enviar, se arma una **mezcla**: se combinan varias pilas en proporciones definidas para formar un lote. La calidad y el valor del lote dependen de esa combinación.

**Objetivo del software:** que el usuario cargue su inventario de pilas y el sistema le permita **simular y luego optimizar** las mezclas, calculando el valor neto en USD que pagaría la refinería.

### Por qué mezclar tiene valor (la intuición económica)
La refinería aplica **deducciones fijas por tonelada** (ej.: descuenta 7 g/t de oro, 100 g/t de plata antes de pagar) más **cargos por peso** (tratamiento, trituración). Por eso una pila de baja ley, sola, puede valer casi nada: la deducción y los cargos se comen su valor. Pero **mezclada con una pila rica**, el lote combinado supera los umbrales y se "rescata" ese metal que se perdería. El límite: si se agrega demasiado peso muerto, los cargos por tonelada superan el metal aportado. Ahí vive la optimización.

---

## 2. Glosario del dominio

| Término | Significado |
|---|---|
| **RAEE** | Chatarra electrónica. Única categoría que entra en las mezclas para JX. |
| **Pila / item** | Una clase de material clasificado en inventario (ej. "Boards Tipo 1"). |
| **Lote / blend** | Un envío a la refinería, compuesto por una mezcla de pilas. |
| **Ley / grade** | Concentración de un metal en la pila. Cu en fracción (0.21 = 21%); Au/Ag/Pt/Pd en **g/t** (gramos por tonelada). |
| **WMT** | Wet Metric weight — peso húmedo (kg). |
| **DMT** | Dry Metric weight — peso seco = WMT × (1 − moisture). |
| **RR** | Recovery Rate — fracción del metal que la refinería reconoce como recuperable. |
| **RC** | Refining Charge — cargo de refinación por unidad de metal, descontado del precio. |
| **T/C** | Treatment Charge — cargo de tratamiento por tonelada seca. |

### Metales considerados
`CU` (cobre), `AU` (oro), `AG` (plata), `PT` (platino), `PD` (paladio).

### Categorías de inventario
- **630 — Inventory RAEE** → entra en las mezclas. **Es el alcance del simulador.**
- **650 — Inventario No Ferroso** (aluminio, cobre, bronce…) → se vende aparte.
- **651 — Inventario Ferroso** (hierro) → se vende aparte.

> Las recetas históricas **solo referencian códigos de la categoría 630**. El no-ferroso y el ferroso quedan fuera del modelo de mezcla.

---

## 3. Cómo se valoriza un lote — LA FÓRMULA (el corazón del sistema)

Replicada exactamente de la planilla histórica de la refinería. **Es la pieza más importante: implementarla con precisión es prioridad.**

### 3.1 Pesos del lote
```
DMT = WMT × (1 − moisture)
```

### 3.2 Por cada metal
Para cada metal se calcula: contenido → recuperado → monto.

**Cobre (CU)** — grade en fracción, precio en USD/tonelada:
```
content_kg      = grade_cu × DMT
RR_cu           = (grade_cu − 0.03) / grade_cu          # deduce 3 puntos porcentuales
recovered_kg    = content_kg × RR_cu
unit_price      = price_cu − RC_cu
amount_usd      = recovered_kg × unit_price / 1000      # kg → tonelada
```

**Metales preciosos (AU, AG, PT, PD)** — grade en g/t, precio en USD/onza troy:
```
content_g       = (DMT / 1000) × grade
recovered_g     = content_g × RR                        # RR según tabla de abajo
unit_price      = price − RC
amount_usd      = recovered_g × unit_price / 31.1034768 # gramos → onza troy
```

### 3.3 Tabla de Recovery Rate (RR) por metal — **términos del contrato, CONFIRMAR**
| Metal | Fórmula de RR | Deducción | Tope |
|---|---|---|---|
| CU | `(g − 0.03) / g` | 3 puntos % | — |
| AU | `MIN(0.96, (g − 7) / g)` | 7 g/t | 96% |
| AG | `MIN(0.95, MAX(0, (g − 100) / g))` | 100 g/t | 95% |
| PD | `MAX(0, (g − 18) / g)` | 18 g/t | sin tope observado |
| PT | desconocida | — | — |

> ⚠️ **Bug detectado en la planilla original:** la fórmula de Cu incluía ramas `IF(grade>=20 …)` y `IF(grade>=23 …)` que **nunca se activan**, porque comparan la ley en fracción (0.21) contra 20/23. En la práctica siempre aplica `(g − 0.03)/g`. Implementar el comportamiento real (deducir 3 puntos %) y **confirmar con Gilberto** si las ramas de 20%/23% eran intencionales.

### 3.4 Cargos de procesamiento (se restan)
```
treatment_charge = (DMT / 1000) × tc_rate              # 600/tonelada seca observado
shredding_charge = (WMT / 1000) × shred_rate           # 100/tonelada húmeda observado
min_lot_charge   = ...                                  # 0 observado — CONFIRMAR
moisture_penalty = ...                                  # 0 observado — CONFIRMAR
```

### 3.5 Resultado del lote
```
metal_total   = Σ amount_usd (todos los metales)
charges_total = treatment_charge + shredding_charge + min_lot_charge + moisture_penalty
net_value_usd = metal_total − charges_total
result_per_kg = net_value_usd / WMT
```

### 3.6 Cómo se valoriza una MEZCLA
Una mezcla es un conjunto de pilas con un peso aportado cada una. La ley de cada metal del lote combinado es el **promedio ponderado por peso seco**:
```
DMT_blend       = Σ dry_weight_i                        # dry_weight_i = weight_i × (1 − moisture_i)
WMT_blend       = Σ weight_i
grade_blend(m)  = Σ (grade_i(m) × dry_weight_i) / DMT_blend
```
Luego se aplica la fórmula de 3.1–3.5 al lote combinado (con `WMT_blend`, `DMT_blend` y las `grade_blend`).

> **Nota para el optimizador:** como las deducciones son por tonelada, el valor recuperado es **lineal por tramos** en los pesos de las pilas (lineal mientras la ley de la mezcla esté por encima del umbral y por debajo del tope). Esto habilita **programación lineal (LP)** o **MILP** con manejo de los quiebres. No es necesario en la Fase 1.

---

## 4. Modelo de datos

### 4.1 `InventoryItem` (pila)
| Campo | Tipo | Notas |
|---|---|---|
| `code` | str | Código de inventario (ej. "001", "998"). |
| `name` | str | Nombre (ej. "Boards Tipo 1"). |
| `category` | enum | `RAEE` \| `NON_FERROUS` \| `FERROUS`. Solo `RAEE` entra en mezclas. |
| `quantity_kg` | float | Stock disponible en kg (WMT). |
| `moisture` | float | Fracción de humedad. **Falta en los datos actuales** (asumir default, ej. 0.01, editable). |
| `grade_cu` | float | Ley de cobre (fracción). **FALTA — ver sección 6.** |
| `grade_au` | float | Ley de oro (g/t). **FALTA.** |
| `grade_ag` | float | Ley de plata (g/t). **FALTA.** |
| `grade_pt` | float | Ley de platino (g/t). **FALTA.** |
| `grade_pd` | float | Ley de paladio (g/t). **FALTA.** |

> Las leyes deben ser **editables en la UI**: hoy no existen en el inventario y se cargarán por estimación (sección 6) o por análisis de laboratorio.

### 4.2 `MetalPrices` (precios del día)
`price_cu` (USD/t), `price_au`, `price_ag`, `price_pt`, `price_pd` (USD/onza troy). Editables; en el futuro, posible carga automática.

### 4.3 `ContractTerms` (términos de la refinería)
Cargos de refinación `rc_cu`, `rc_au`, `rc_ag`, `rc_pt`, `rc_pd`; parámetros de RR (deducciones y topes de la tabla 3.3); `tc_rate`, `shred_rate`, `min_lot_charge`, `moisture_penalty`. **Todos parametrizables**, no hardcodeados.

### 4.4 `Blend` y `BlendComponent`
```
Blend:
  components: list[BlendComponent]
  → calcula: WMT_blend, DMT_blend, grade_blend por metal,
             amount por metal, charges, net_value_usd, result_per_kg

BlendComponent:
  item: InventoryItem
  weight_kg: float          # cuánto de esa pila entra (≤ quantity_kg)
```

---

## 5. Alcance del producto — por fases

### Fase 1 — Simulador (MVP) ✅ construir primero
El usuario elige pilas y pesos (o porcentajes); el sistema muestra **al instante**:
- Ley resultante de la mezcla por metal.
- Monto por metal, cargos, **valor neto USD** y **USD/kg**.
- Avisos si se rompe alguna regla del contrato (cuando se definan).

Características: tabla de inventario editable (incluidas leyes), tabla de precios editable, panel de resultado en vivo. **El usuario itera a mano y mantiene el control.** Replica la planilla pero viva, y valida la fórmula contra números reales.

### Fase 2 — Optimizador
El usuario carga inventario + términos + objetivo, y el sistema **calcula solo** la mejor mezcla (LP/MILP). Requiere:
- Las **leyes** cargadas y confiables.
- Las **reglas/objetivo** definidos (ver sección 7): ¿maximizar USD total? ¿USD/kg sujeto a tamaño mínimo de lote? ¿qué restricciones impone JX?

> No empezar la Fase 2 hasta tener leyes y reglas. El simulador hace aflorar ambas.

---

## 6. El problema de las leyes (assays) y cómo resolverlo

**El inventario tiene peso pero NO tiene ley.** Es el insumo que falta para todo el cálculo. Dos caminos:

1. **Ideal:** Gilberto provee los ensayos de laboratorio por pila.
2. **Estimación desde el histórico:** cada uno de los **53 lotes** enviados tiene su análisis real, y ese análisis es el **promedio ponderado de las pilas que lo formaron**. Con recetas conocidas, se puede resolver el sistema inverso (regresión por mínimos cuadrados) para despejar la ley de cada pila.

**Cobertura estimada:** de los **40 ítems RAEE con stock**, **25 aparecen en recetas** (estimables) y **15 no** (necesitan valor de laboratorio o manual). Las pilas de mayor volumen (Bajo Grado Marrón, Boards T1/T2/T3, Centrales) están cubiertas.

**Caveats de la estimación:**
- Recetas con porcentajes que suman 100% (ej. `1*(28%) + 2*(58%) + 14*(14%)`) son limpias.
- Recetas tipo `6 + 8*33%` son ambiguas: no se conoce cuántos kg fue el componente "6". Usar solo el subconjunto resoluble o pedir el dato.
- Es un método **prometedor pero a validar** contra los ensayos reales de los lotes antes de confiar en él.

**Acción recomendada:** generar esta **tabla de leyes estimadas como primer entregable de datos** y sembrar con ella el simulador (paso 5 del plan), para arrancar con números reales en lugar de placeholders. Marcar cada ley con su origen (`estimada` vs. `laboratorio`) y un nivel de confianza, para que el usuario sepa de cuáles fiarse y cuáles refinar con análisis.

---

## 7. Preguntas abiertas para confirmar con Gilberto

1. **Reglas de validez de la mezcla:** ¿JX exige mínimos/máximos de alguna ley? ¿Penaliza contaminantes (plomo, hierro)? ¿Rechaza lotes por tamaño?
2. **Objetivo del optimizador:** ¿maximizar valor total del envío? ¿USD/kg? ¿decidir qué pilas enviar ahora vs. retener? ¿hay un tamaño de lote objetivo/obligatorio?
3. **Términos del contrato:** ¿las deducciones (7 g/t Au, 100 g/t Ag, 18 g/t Pd, 3% Cu), topes y cargos (600/Dt, 100/t) son fijos o negociados por envío?
4. **El bug de Cu:** ¿las ramas 20%/23% eran intencionales?
5. **Platino (PT):** ¿se paga? ¿con qué términos?
6. **Assays:** ¿tiene leyes por pila o por lote histórico? ¿Cómo y cada cuánto se miden?
7. **Humedad:** ¿se mide por pila o es un estimado global?
8. **Omar:** ¿quién es y este es el mismo comprador/proceso de Gilberto?

---

## 8. Stack técnico recomendado

- **Lógica de dominio:** Python. La valorización (sección 3) en un módulo puro y testeado, independiente de la UI.
- **UI del MVP:** **Streamlit** — permite tener el simulador funcionando rápido sin frontend dedicado. Migrable después a algo más pulido (FastAPI + React) si hace falta.
- **Optimización (Fase 2):** `PuLP` u `OR-Tools` para LP/MILP.
- **Datos:** carga desde los `.xlsx` existentes con `openpyxl`/`pandas`.
- **Tests:** `pytest`, con el Apéndice A como caso de aceptación.

---

## 9. Estructura de repo sugerida y plan de construcción

```
/
├── CLAUDE.md                 # este documento
├── pyproject.toml
├── src/
│   ├── domain/
│   │   ├── models.py         # InventoryItem, MetalPrices, ContractTerms, Blend
│   │   └── valuation.py      # fórmula sección 3 (núcleo, sin dependencias de UI)
│   ├── data/
│   │   ├── load_inventory.py # parsea el xlsx de inventario
│   │   └── estimate_grades.py# sección 6 (regresión desde lotes históricos)
│   └── app/
│       └── simulator.py      # UI Streamlit (Fase 1)
├── data/
│   ├── inventory.xlsx
│   └── refining_history.xlsx
└── tests/
    └── test_valuation.py     # Apéndice A
```

**Plan por pasos:**
1. `domain/valuation.py` + `tests/` → que pase el Apéndice A.
2. `domain/models.py` → estructuras de datos de la sección 4.
3. `data/load_inventory.py` → cargar pilas RAEE con stock.
4. `app/simulator.py` → simulador con inventario y precios editables, resultado en vivo.
5. `data/estimate_grades.py` → estimación de leyes; validar contra lotes reales.
6. (Tras confirmar reglas) Fase 2: optimizador.

---

## 10. Datos de referencia observados en el archivo

> Tomados de la planilla con fecha **2025-01-23**. Cargar como valores por defecto **editables**; no asumir vigentes.

**Precios:** Cu 11.803,79 USD/t · Au 4.500 USD/oz · Ag 64,34 USD/oz · Pd 1.569 USD/oz · Pt s/d.
**Refining charges (RC):** Cu 300/t · Au 5/oz · Ag 0,5/oz · Pd 14/oz.
**Cargos:** Treatment 600/tonelada seca · Shredding 100/tonelada húmeda · Min lot charge 0 · Moisture penalty 0.

**Inventario actual:** 40 ítems RAEE con stock. Mayores volúmenes: Bajo Grado Marrón (13.330 kg), Boards Tipo 3 (4.206 kg), Boards Tipo 2 (3.479 kg), Boards Tipo 1 (2.924 kg), Centrales Telefónicas (2.923 kg), Bajo Grado Verde (2.809 kg).

---

## Apéndice A — Ejemplo numérico verificado (test de aceptación)

Primer lote histórico. La implementación debe reproducir estos valores.

**Entrada:**
- WMT = 5184 kg · moisture = 0.009 → **DMT = 5137.344 kg**
- Precios: Cu 11803.79 · Au 4500 · Ag 64.34 · Pd 1569
- RC: Cu 300 · Au 5 · Ag 0.5 · Pd 14 · Cargos: T/C 600/Dt · Shred 100/t
- Leyes: Cu 0.2113 · Au 84.4 g/t · Ag 646 g/t · Pd 4.3 g/t

**Salida esperada (≈):**
| Metal | content | RR | recovered | amount USD |
|---|---|---|---|---|
| CU | 1085.52 kg | 0.8580 | 931.40 kg | 10.714,64 |
| AU | 433.59 g | 0.9171 | 397.63 g | 57.464,60 |
| AG | 3318.72 g | 0.8452 | 2804.99 g | 5.757,25 |
| PD | 22.09 g | 0.0000 | 0 g | 0,00 |

```
metal_total   ≈ 73.936,49
treatment     = 600 × 5137.344/1000 = 3.082,41
shredding     = 100 × 5184/1000     =   518,40
charges_total ≈ 3.600,81
net_value_usd ≈ 70.335,68
result_per_kg ≈ 13,57 USD/kg
```

> Nota: Pd da 0 porque su ley (4,3 g/t) está por debajo de la deducción de 18 g/t → `MAX(0, (4.3−18)/4.3) = 0`. Es el efecto que el sistema debe capturar: material sub-umbral no paga solo, pero sí mezclado con pilas ricas.
