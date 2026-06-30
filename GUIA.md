# Aurix · Optimizador de Mezclas RAEE — Recuento y Guía de Uso

> **Servicios Megabytes, C.A.** — Software que decide **qué mezcla mandar en cada
> contenedor** a la refinería (JX) para que paguen **el mayor porcentaje posible**
> del metal, sin dejar material sin cobrar.
>
> App en vivo: **https://147-93-6-70.sslip.io** · Acceso con contraseña.
> Última actualización: rama `claude/new-session-5k4aar`.

---

## Parte 1 — Qué construimos (recuento)

### 1.1 El problema, en una frase
La refinería **descuenta una cantidad fija por tonelada** antes de pagar (7 g/t de
oro, 100 g/t de plata, 18 g/t de paladio, 3 puntos de cobre). Una pila **pobre,
enviada sola, cae por debajo de ese umbral y paga $0** — material perdido. Pero
**mezclada con una rica** supera el umbral y se cobra. Si se diluye de más, los
cargos por tonelada (tratamiento, trituración) se comen la ganancia.

**Ahí vive el negocio: armar cada contenedor en la mezcla justa.** Eso es lo que
el sistema calcula, explica y visualiza.

### 1.2 Qué hace el sistema hoy
- **Reproduce la fórmula de la refinería al dólar.** Validada contra el primer
  lote histórico (Apéndice A): `net ≈ 70.335,68 USD`, `13,57 USD/kg`.
- **Estima las leyes que no existían.** El inventario tenía peso pero **no ley**.
  El sistema las despeja de **53 lotes históricos** por regresión, y marca de cada
  una **qué tan confiable es** (medida / estimada / sin determinar).
- **Optimiza el contenedor.** Lo parte en los **lotes** que la refinería tasa por
  separado, concentrando el oro y separando el relleno — el mayor % cobrado.
- **Muestra el plano físico de carga** en 3D: cada **pallet** numerado y
  clasificado (Muy Rico / Poco Rico / Relleno), con alerta roja si alguno
  pagaría $0.
- **Recomienda qué comprar** para completar el próximo contenedor cuando el
  sobrante quedaría bajo el umbral.
- **Mide el riesgo de cobro.** Para cada metal: probabilidad de superar el umbral
  (`P_cobro`), dada la incertidumbre de la ley.

### 1.3 La filosofía: el % manda, no el USD
El sistema muestra **% del material aprovechado**, no montos. El precio
internacional de los metales varía mucho; un valor en USD de hace un año no
aplica. El **% que paga la refinería es lo estable y comparable** — y es el número
que de verdad mide si la mezcla está bien armada.

### 1.4 Números del proyecto
| | |
|---|---|
| Inventario RAEE con stock | **40 pilas · ~40,3 t** |
| Pilas con ley estimada | **25 de 40** (15 pendientes de laboratorio) |
| Histórico para estimar | **53 lotes** (36 con receta resoluble) |
| Contenedor estándar | **23 t** (40') · ~1 envío cada 3 meses |
| Tests automáticos | **71 en verde** (10 archivos) |
| Stack | Python · Streamlit · PuLP (MILP) · Plotly (3D) · Docker |

### 1.5 Términos del contrato que usa el modelo
| Metal | Deducción (umbral) | Tope de recuperación |
|---|---|---|
| Oro (AU) | 7 g/t | 96 % |
| Plata (AG) | 100 g/t | 95 % |
| Paladio (PD) | 18 g/t | sin tope |
| Cobre (CU) | 3 % de la ley | — |
| Platino (PT) | no se paga (a confirmar) | — |

**Cargos:** tratamiento 600 USD/t seca · trituración 100 USD/t húmeda.
Todos los términos y precios son **editables** desde la app (no están fijos en el
código).

---

## Parte 2 — Guía de uso (módulo por módulo)

La navegación está **siempre arriba**, en pestañas. Seis módulos:
**Demo · Panel · Inventario · Simulador · Optimizador · Histórico.**

> En toda la app las pilas se muestran **solo por código** (001, 009, 998…), nunca
> por nombre del material — privacidad de las fórmulas.

### 2.1 Panel — el resumen ejecutivo
Lo primero que conviene mostrar. De un vistazo:
- **Precisión del modelo** (qué tan bien reproduce los pagos reales de la
  refinería) y el error por metal (Au ~5 %, Cu ~2 %).
- **Material aprovechado del próximo contenedor** con el stock actual.
- **Cobertura:** cuántas pilas tienen ley y cuántas faltan.

**Para qué sirve en la reunión:** demuestra que el modelo es fiel a la realidad
antes de pedir confianza en lo que recomienda.

### 2.2 Inventario — la fuente de verdad
Acá se carga y edita el stock. Es la base de todo lo demás.
- **Tabla editable:** cantidad (kg), humedad, leyes por metal, origen de la ley.
- **Insignia de confianza** por pila: *Medida · Estimada · Floja*.
- **Carga por Excel (.xlsx)** con fusión: actualiza cantidades por código,
  conserva las leyes conocidas y agrega pilas nuevas.
- **Guardar:** los cambios impactan **al instante** en Simulador, Optimizador y
  Panel.

**Cómo se cargan más lotes/pilas:** subís el `.xlsx` actualizado o editás la tabla
a mano y guardás. No hace falta tocar nada técnico.

### 2.3 Simulador — armar una mezcla a mano
Para cuando el usuario quiere **probar una combinación propia**.
- Escribís cuántos kg de cada pila entran en la mezcla.
- Ves **al instante**: ley resultante, % aprovechado, recuperación por metal y
  valor neto tras cargos.
- Avisa si pedís más kg de los que hay en stock.

**Para qué sirve:** entender la fórmula "jugando", y validar a mano lo que el
optimizador propone solo.

### 2.4 Optimizador — el corazón operativo ⭐
Acá el sistema **arma el mejor contenedor solo**. El flujo:

1. Elegís el contenedor (23 t por defecto) y tocás **"Armar el mejor contenedor"**.
2. El sistema decide en **cuántos lotes** conviene partirlo (prueba 1, 2, 3… y
   elige el que más paga en conjunto, **sin tamaño mínimo de lote**).
3. Muestra el **% del material aprovechado** del contenedor entero.
4. **Vista 3D de lotes:** cada bloque es un lote (tamaño = peso, color = % que
   paga).
5. **Plano de carga de pallets (nuevo):** cómo va distribuido físicamente, pallet
   por pallet, **numerado en orden de carga** y clasificado:
   - 🟢 **MUY RICO** — concentra el valor (más oro).
   - 🟩 **POCO RICO** — volumen con ley media.
   - 🟨 **RELLENO** — peso que viaja mezclado para **no caer bajo el umbral**.
   - 🟥 Borde rojo si un pallet quedaría bajo el umbral (pagaría $0).
6. **Alerta de $0:** lista cualquier metal que caiga bajo el umbral, con la pila
   que lo rescataría.
7. **Seguridad de cobro por lote:** ley ± margen vs. umbral y **probabilidad de
   cobro** por metal.
8. **Queda en depósito:** lo que no entró en este contenedor.
9. **Completar el próximo contenedor (nuevo):** ver 2.6.

**Para qué sirve:** es la herramienta del día a día — "Gilberto, así te conviene
armar el contenedor que mandás ahora".

### 2.5 Histórico — la prueba de que funciona
Cada uno de los lotes reales enviados, comparado contra cómo lo armaría el
sistema.
- Tabla lote por lote: receta, peso, % aprovechado, neto.
- **Re-mezcla óptima** de los lotes multipila (solo en el mundo estimado).
- **Transparencia:** desglose paso a paso del pago de la refinería (ley →
  deducciones → precio − cargos).
- Avisos de metales que pagaron $0 por caer bajo umbral.

**Para qué sirve:** muestra honestamente que **las mezclas de Gilberto ya eran muy
buenas** (la mejora histórica es chica) — el sistema **valida su criterio**. El
salto de valor está hacia adelante, con el inventario completo.

### 2.6 Demo — el recorrido de 2 minutos para la reunión
Pensada para mostrar sin preparar nada.
- **"Tomar un lote al azar"** o buscar uno puntual.
- Compara **cómo se envió vs. cómo lo optimiza el sistema**, en %.
- Recuperación por metal, explicación de por qué elige esa versión, **3D + plano
  de pallets**, y seguridad de cobro por lote.
- Cierra con el encuadre **"el pasado valida, el futuro es el inventario"**.

---

## Parte 3 — Las dos capacidades nuevas, en detalle

### 3.1 Plano de carga por pallets
Responde a *"¿cómo va distribuido físicamente el contenedor?"*. El contenedor se
arma con **pallets de ~1 t**, numerados en orden de carga, dispuestos en una
grilla de 2 columnas (como un 40' real). Cada pallet hereda la categoría de su
lote según la **concentración de oro**, y los que quedaran bajo el umbral se
marcan en rojo. Da un **plan de armado concreto**: "Pallets 1–3 Muy Ricos, 4–8
Poco Ricos, 9–24 Relleno (y todos sobre el umbral)".

### 3.2 Completar contenedor
Responde al problema central: *"que no quede material sin cobrar, y avisar antes
de que pase"*. Cuando el sobrante (lo que no entró en el contenedor) tiene algún
metal bajo el umbral:
- **Detecta** qué metal pagaría $0 (ej.: Pd a 12 g/t < umbral 18).
- **Recomienda qué pila comprar y cuántos kg** para levantar la mezcla sobre el
  umbral con margen de seguridad.
- **Solo recomienda contra leyes confiables** (descarta números sin determinar) y
  usa la ley conservadora (`grade − k·σ`): no te hace comprar apostando a una
  estimación ruidosa.
- **Mide el beneficio honestamente:** cuánto del metal del **propio sobrante**
  pasa a cobrarse (ej.: 65 % → 78 % aprovechado).

> Ejemplo real con tu sobrante (17,3 t): comprar **~1.814 kg de la pila 025**
> (oro 342 g/t, ley medida) sube el sobrante de **65 % a 78 %** cobrado, sin
> dejar nada en $0.

---

## Parte 4 — Cómo medimos la confianza (por qué fiarse del número)

No todas las leyes valen lo mismo. Cada (pila, metal) tiene un nivel:
- **Medida** — la pila viajó sola en algún lote: ley directa, máxima confianza.
- **Estimada** — despejada por regresión de las recetas históricas, con
  apalancamiento suficiente.
- **Sin determinar** — pilas que solo viajaron juntas (inseparables) o con datos
  pobres: el sistema **no las usa para recomendar comprar**.

Sobre eso, cada lote reporta una **probabilidad de cobro** por metal (`P_cobro`):
qué tan por encima del umbral está la ley considerando su margen de error. Un
metal con `P_cobro` alto cobra seguro; uno pegado al umbral se marca como frágil.

---

## Parte 5 — Guion sugerido para la reunión (10 min)

1. **Panel** → "El modelo reproduce los pagos reales de la refinería con error de
   ~5 % en oro. No es una teoría, es fiel a lo que ya pasó."
2. **Demo** → tomar un lote al azar → "Acá ven cómo el sistema reconoce un envío
   real y lo arma óptimo, en % del material cobrado." Mostrar el **3D y el plano
   de pallets**.
3. **Histórico** → "Sus mezclas ya eran muy buenas — el sistema lo confirma. El
   criterio con el que vienen trabajando es sólido."
4. **Optimizador** → armar el contenedor de 23 t → mostrar la división en lotes,
   el plano de pallets numerado, y **"Completar contenedor"**: "Acá está el valor
   hacia adelante: el sistema les dice qué mandar, cómo cargarlo y **qué comprar**
   para no perder material."
5. **Cierre** → "Se afina solo: cada liquidación nueva mejora las leyes y la
   confianza, sin laboratorio. Vale más cuanto más se usa."

---

## Parte 6 — Operación y acceso

- **Entrar:** abrir la URL e ingresar la contraseña.
- **Modo demo (solo Demo + Inventario, con PIN):** se activa/desactiva por
  configuración del servidor (variables `DEMO_MODE` / `DEMO_PIN`).
- **Privacidad:** las pilas se ven solo por código; el `.env` con la contraseña
  vive en el servidor, nunca en el repositorio.
- **Despliegue:** Docker detrás del nginx existente del VPS (HTTPS), reinicia solo
  tras un reboot.

---

## Parte 7 — Qué queda por delante (hoja de ruta)

- **Rotación de inventario:** qué mandar ahora vs. retener, para dar salida a la
  mercancía sin dejarla envejecer.
- **Cobertura de leyes:** llevar las 15 pilas pendientes a *medida* (laboratorio o
  más liquidaciones), y desagregar los bloques colineales.
- **Carga automática de precios** del día y de nuevas liquidaciones.

> El sistema ya cubre el ciclo central: **cargar inventario → optimizar el
> contenedor → ver el plano de carga → saber qué comprar.** Lo demás lo hace cada
> vez más fino.
