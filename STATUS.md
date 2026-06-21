# STATUS — Optimizador de Mezclas RAEE (Servicios Megabytes, C.A.)

> Documento de **handoff**: estado completo del proyecto para retomarlo en cualquier
> chat de Claude. Última actualización: rama `claude/new-session-5k4aar`.

---

## 1. Resumen ejecutivo

Software que ayuda a **Servicios Megabytes** (reciclaje de chatarra electrónica /
RAEE) a decidir **qué mezcla de materiales mandar en cada contenedor** a la
refinería (**JX**) para que le **paguen el mayor porcentaje posible** del metal.

**Estado:** funcional y desplegado en producción (con login + HTTPS). Núcleo de
cálculo validado contra datos reales. **48 tests en verde**, ~5.000 líneas.

- **Repo / rama de trabajo:** `Juninho2604/GILBERTO` → `claude/new-session-5k4aar`
- **App en vivo:** `https://147-93-6-70.sslip.io` (login con contraseña)
- **Stack:** Python · Streamlit · PuLP (MILP) · Plotly (3D) · Docker

---

## 2. El negocio (dominio)

- Se acumulan **pilas** de chatarra electrónica clasificada (placas, boards,
  procesadores…), cada una con un **código** (001, 009, 998…).
- Se arma un **contenedor** (estándar 40' ≈ **23 toneladas**) y se manda a la
  refinería **~1 vez cada 3 meses**.
- La refinería **mide y paga por lote**: dentro de un contenedor puede haber
  **varios lotes** que valoriza por separado.
- La refinería aplica **deducciones fijas por tonelada** (descuenta 7 g/t de oro,
  100 g/t de plata, etc.) antes de pagar. Por eso una pila pobre **sola** no paga
  casi nada, pero **mezclada con una rica** supera el umbral y se cobra.
- **Ahí vive la optimización:** combinar para superar umbrales sin meter tanto
  peso muerto que los cargos por tonelada se coman la ganancia.

### Metales y categorías
- Metales: **CU** (cobre), **AU** (oro), **AG** (plata), **PT** (platino), **PD** (paladio).
- Solo entra la categoría **630 — Inventory RAEE**. El no-ferroso (650) y ferroso
  (651) se venden aparte, fuera del modelo.

---

## 3. La fórmula de valorización (el corazón)

Replicada exacta de la planilla de la refinería. Módulo puro en
`src/domain/valuation.py`, validado contra el **Apéndice A** (primer lote
histórico) al dólar.

```
DMT = WMT × (1 − humedad)                         # peso seco

# Cobre (ley en fracción, precio USD/t):
content_kg   = grade_cu × DMT
RR_cu        = (grade_cu − 0.03) / grade_cu        # deduce 3 puntos %
amount_usd   = content_kg × RR_cu × (price_cu − RC_cu) / 1000

# Preciosos (ley en g/t, precio USD/oz troy):
content_g    = (DMT/1000) × grade
amount_usd   = content_g × RR × (price − RC) / 31.1034768
```

**Tabla de Recovery Rate (RR):**
| Metal | RR | Deducción | Tope |
|---|---|---|---|
| CU | (g−0.03)/g | 3 puntos % | — |
| AU | MIN(0.96, (g−7)/g) | 7 g/t | **96%** |
| AG | MIN(0.95, MAX(0,(g−100)/g)) | 100 g/t | 95% |
| PD | MAX(0, (g−18)/g) | 18 g/t | s/tope |
| PT | desconocida (no se paga por defecto) | — | — |

**Cargos (se restan):** Treatment 600/tonelada seca · Shredding 100/tonelada húmeda.

**Mezcla:** la ley del lote combinado es el promedio ponderado por peso seco de
las pilas; luego se aplica la fórmula al lote.

> ⚠️ Bug heredado de la planilla: la fórmula de Cu tenía ramas `IF(grade>=20/23)`
> que nunca se activan. Se implementó el comportamiento real (deducir 3 puntos %).
> **Confirmar con Gilberto** si esas ramas eran intencionales.

### El % de aprovechamiento (métrica principal de la UI)
En `LotValuation` se calculan, además del $:
- `metal_utilization_pct` = **% del metal presente que la refinería paga** (lo que
  supera los mínimos). **Es el dato que importa, no el $.**
- `net_utilization_pct` = idem, ya descontados los cargos.
- `unused_pct` = % del metal que se pierde por caer bajo el umbral.

---

## 4. El modelo de optimización (lo más importante de entender)

**Unidad de optimización = UN contenedor (23 t), partido en sus lotes óptimos.**
NO se optimiza "todo el inventario de una vez" (esa era una premisa equivocada que
se corrigió). Implementado como **MILP** en `src/optimize/optimizer.py`.

- `optimize_partition(..., container_kg=23000)`: reparte el material en lotes con
  el **total acotado a la capacidad del contenedor**; deja el resto en depósito
  para el próximo envío.
- `best_partition(...)`: barre la cantidad de lotes (1..N) y elige la de mayor
  valor (corta cuando la ganancia se aplana).
- El optimizador **concentra el oro** para tocar el tope (96%) en un lote y
  **separa el relleno**, maximizando el % pagado sin diluir.
- Las deducciones por tonelada hacen el problema **lineal por tramos** → se modela
  exacto con binarias por umbral/tope.

**Objetivo:** maximizar el valor (= más dinero para Gilberto), lo que ya empuja
cada metal a su % máximo donde conviene. Decisión tomada con el usuario: NO
maximizar el % "a la fuerza" (haría ganar menos en algunos casos).

**Resultado típico (inventario actual):** 23 t en **2 lotes**, **~92% aprovechado**
(Lote 1 rico con Au 175 g/t = 96% de oro; Lote 2 mixto ~91%).

---

## 5. El problema de las leyes (assays) — la principal limitación

**El inventario tiene peso pero NO tiene ley medida por pila.** No hay laboratorio:
la **única fuente** es lo que la refinería pagó por los **53 lotes históricos**.

- Las leyes se **estiman por regresión** (mínimos cuadrados) desde esos 53 lotes:
  cada lote es el promedio ponderado de sus pilas → se despeja la ley de cada pila.
  Código: `src/data/estimate_grades.py`.
- **Cobertura:** de **40 ítems RAEE con stock**, **25 tienen ley estimada**, 15 no
  (no aparecen en recetas históricas).
- **Validación:** el modelo reproduce el dinero real con ~3% de desvío; error
  mediano de ley: Cu 2%, Au 5%, Ag 8% (media 19% — colas feas), Pd 10%.

> ⚠️ **Hueco conocido y pendiente:** la confianza NO distingue cuántas recetas
> sostienen cada estimación. Pilas que aparecen en 1 sola receta (ej. "Slot
> Processors") dan leyes-fantasma (Pd 1882 g/t, Au 0) con la misma etiqueta
> `ESTIMATED` que una bien sostenida. **El dato `n_recipes` ya se guarda; falta
> usarlo para degradar/marcar la confianza.** (Ver lote 791 como caso testigo:
> el modelo lo valoriza +12% por sobreestimar la plata).

Las leyes **se afinan solas** a medida que se mandan más lotes y se ve lo que
paga la refinería (no hace falta laboratorio).

---

## 6. Arquitectura del código

```
src/
├── domain/
│   ├── models.py          # InventoryItem, MetalPrices, ContractTerms, RecoveryRule
│   └── valuation.py       # LA FÓRMULA (§3) + % aprovechado. Puro, testeado.
├── optimize/
│   └── optimizer.py       # MILP: optimize_partition(container_kg), best_partition
├── data/
│   ├── load_history.py    # parsea los 53 lotes de la refinería
│   ├── load_inventory.py  # parsea el inventario RAEE
│   ├── estimate_grades.py # regresión de leyes desde el histórico
│   └── recipes.py         # parseo de recetas ("6 + 8*33%", etc.)
├── analysis/
│   ├── historical.py      # estudio real vs óptimo + % aprovechado agregado
│   ├── explain.py         # explica por qué una partición es mejor
│   └── build_analysis.py  # precomputa data/history_analysis.json
└── app/
    ├── simulator.py       # ENTRYPOINT (streamlit run). Login + navegación.
    ├── auth.py            # login básico por contraseña (APP_PASSWORD)
    ├── ui.py              # CSS/tema premium + componentes (kpi, pile_label…)
    ├── sidebar.py         # precios/términos editables
    ├── data_access.py     # caché de datos para la UI
    ├── logistics.py       # capacidades de contenedor
    ├── viz3d.py           # visualización 3D del contenedor (plotly)
    └── views/
        ├── panel.py       # dashboard ejecutivo (% aprovechado)
        ├── inventario.py  # editar stock y leyes (solo códigos)
        ├── simulador.py   # arma una mezcla a mano, resultado en vivo
        ├── optimizador.py # arma el mejor CONTENEDOR + 3D
        └── historico.py   # 53 lotes reales vs óptimo
tests/                     # 48 tests (pytest). Apéndice A = test de aceptación.
deploy/                    # Dockerfile, setup.sh, Caddyfile, README
data/                      # inventory.xlsx, refining_history.xlsx, history_analysis.json
```

---

## 7. La interfaz (5 módulos)

Navegación propia por "pills". Estética: tema oscuro premium (tipografía Inter,
glassmorphism, glow, gradientes).

| Módulo | Qué hace |
|---|---|
| **Panel** | Resumen: % aprovechado del próximo contenedor, envíos pendientes, precisión del modelo. |
| **Inventario** | Editar stock y leyes en vivo (solo por **código**). |
| **Simulador** | Armar una mezcla a mano y ver el % y el resultado al instante. |
| **Optimizador** | Arma el **mejor contenedor de 23 t**, lo parte en lotes, lo muestra en **3D** y avisa si algo queda en $0. |
| **Histórico** | Los 53 lotes reales vs. la mezcla óptima, con % aprovechado por lote. |

**Decisiones de UI tomadas con el usuario:**
- **El % manda, el $ va al fondo** (a Gilberto no le interesa el monto total; sí
  cuánto material se aprovecha).
- **Privacidad:** las pilas se muestran **solo por código**, nunca el nombre del
  material (info que protegen Gilberto y su socio). `pile_label()` ignora el nombre.
- **3D del contenedor** (`viz3d.py`): caja de vidrio + un bloque por lote (tamaño =
  peso, color = % aprovechado, ámbar→verde), interactivo.

---

## 8. Deploy y seguridad

**El VPS real es compartido:** corre **nginx** con ~8 sitios de producción
(brothersclubbarbers.com, kpsula.app, etc.) + Let's Encrypt. Por eso la app va
**detrás del nginx existente**, NO con su propio Caddy.

**Arquitectura desplegada:**
- App en Docker, atada a **127.0.0.1:8501** (no pública).
- **nginx** la publica con HTTPS en `https://147-93-6-70.sslip.io` (cert Let's
  Encrypt vía `certbot --nginx`, renovación automática). Config en
  `/etc/nginx/sites-available/raee.conf` (proxy + headers de WebSocket).
- Dominio: **sslip.io** (mapea la IP sin registrar nada). Mejorable a un dominio
  propio para la demo a Gilberto.

**Capas de seguridad:**
1. 🔒 **Login** por contraseña (`app/auth.py`, env var `APP_PASSWORD`).
2. 🔐 **HTTPS** (todo cifrado).
3. 🚪 Puerto 8501 **cerrado al público** (solo localhost detrás de nginx).
4. 🙈 Inventario **solo por código**.

**Modos del `deploy/setup.sh`:**
- `EXTERNAL_PROXY=1 bash deploy/setup.sh` → **el que usa este VPS**: app en
  127.0.0.1, sin Caddy (la sirve el nginx propio).
- `DOMAIN=... bash deploy/setup.sh` → levanta Caddy con HTTPS (para un VPS limpio
  sin nginx).
- Sin nada → app pública en :8501 (solo dev).

**Redeploy seguro en este server:**
```bash
cd ~/raee-optimizer
git fetch origin claude/new-session-5k4aar && git reset --hard origin/claude/new-session-5k4aar
EXTERNAL_PROXY=1 bash deploy/setup.sh
```

> ⚠️ El `.env` (contraseña, dominio, flags) está **fuera de git** (.gitignore).

---

## 9. Datos de referencia (editables en la UI, fecha 2025-01-23)

- **Precios:** Cu 11.803,79 USD/t · Au 4.500 USD/oz · Ag 64,34 · Pd 1.569 · Pt s/d.
- **Refining charges:** Cu 300/t · Au 5/oz · Ag 0,5/oz · Pd 14/oz.
- **Cargos:** Treatment 600/Dt · Shredding 100/t · Min lot 0 · Moisture penalty 0.
- **Inventario:** 40 ítems RAEE con stock (~37 t con ley estimada). Mayores
  volúmenes: Bajo Grado Marrón (13.330 kg), Boards T3/T2/T1, Centrales Telefónicas.

---

## 10. Limitaciones conocidas y preguntas abiertas

**Limitaciones:**
1. **Leyes estimadas, no medidas** — y la confianza no penaliza las pilas con
   pocas recetas (ver §5). Es el riesgo de credibilidad más grande.
2. **15 de 40 pilas sin ley** (no aparecen en recetas históricas).
3. **sslip.io** es un dominio compartido (poco profesional para la demo final).

**Preguntas abiertas para Gilberto:**
1. ¿La refinería exige mínimos/máximos de ley? ¿Penaliza contaminantes? ¿Rechaza
   por tamaño de lote?
2. ¿Las deducciones/topes/cargos son fijos o se negocian por envío?
3. El bug de Cu (ramas 20%/23%): ¿eran intencionales?
4. ¿El platino se paga? ¿Con qué términos?
5. ¿Cómo se mapea un contenedor a los "lotes" que tasa la refinería (los 53
   históricos son lotes chicos, no contenedores de 23 t)?
6. ¿La humedad se mide por pila o es un estimado global?

---

## 11. Próximos pasos sugeridos (por prioridad)

1. **Confianza por `n_recipes`** — degradar/marcar las leyes flojas en la UI y que
   el optimizador no sobre-confíe. (Dato ya disponible, falta usarlo.)
2. **Flujo de carga de lotes nuevos** — que cada liquidación nueva de la refinería
   reafine las leyes sin editar el xlsx a mano.
3. **Dominio propio** para la demo a Gilberto (~$1-10/año) en vez de sslip.io.
4. **Modelar contenedor↔lotes históricos** (pregunta abierta #5).
5. Llevar el nivel visual del Optimizador al Panel e Histórico.

---

## 12. Comandos útiles

```bash
# Tests
PYTHONPATH=src python -m pytest -q

# Correr local
streamlit run src/app/simulator.py            # http://localhost:8501

# Regenerar el estudio del histórico (tras cambiar leyes/precios)
PYTHONPATH=src python -m analysis.build_analysis

# Logs en el VPS
docker logs raee-optimizer --tail 50
sudo nginx -T | grep -A20 'server_name 147-93-6-70'
```

---

## 13. Cronología (commits clave de esta sesión)

1. Optimizador con tope de lote y guía de contenedor.
2. Optimizador elige solo el nº de lotes (modo automático).
3. App reorientada al **% aprovechado** (el $ al fondo).
4. **Contenedor = varios lotes + visualización 3D + UI premium**.
5. **Login** por contraseña.
6. **HTTPS** (Caddy/DuckDNS y luego modo **proxy externo** para nginx).

> El núcleo (fórmula + optimizador) está sólido y testeado. El mayor margen de
> mejora está en la **calidad/confianza de las leyes**, no en el motor.
