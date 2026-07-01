# Revisión exhaustiva del modelo — Aurix · Optimizador de Mezclas RAEE

> Auditoría técnica y estratégica del sistema completo, realizada sobre el código
> real (tres pasadas independientes: seguridad, matemática del modelo y
> arquitectura) más la lectura de quien lo construyó. Fecha: 2026-07-01, rama
> `claude/new-session-5k4aar`, 86 tests en verde.

---

## 1. Debilidades del modelo y cómo fortalecerlo

Ordenadas por impacto en las decisiones que ve el cliente.

### 1.1 La promesa "se afina solo" todavía no es real ⚠️ (la más importante)
**Hoy:** incorporar una liquidación nueva de la refinería exige editar el
`refining_history.xlsx` a mano, correr `python -m analysis.build_analysis` y
redeployar. El sistema **no aprende solo**; lo prometimos como diferencial.
**Fortalecer:** un flujo "Cargar liquidación" en la app (formulario o xlsx) que
valide el lote, lo agregue al histórico, re-estime leyes y regenere el análisis
en segundo plano. **Es la mejora nº 1 del roadmap** — convierte la promesa
comercial en una función real.

### 1.2 Bloques colineales: el riesgo se calcula como si fueran independientes
Las pilas que solo viajaron juntas (p. ej. {029–033}) comparten la incertidumbre
de su ley. `blend_threshold_risk` propaga σ asumiendo independencia
(`σ_blend² = Σ f²σ²`). Para mezclas que combinan pilas **del mismo bloque**, eso
**subestima** la σ real de la mezcla (las σ correlacionadas se suman en lineal,
no en cuadratura) → la P_cobro reportada queda **optimista**: la mezcla parece
más segura de lo que es. *(Nota: una de las auditorías concluyó lo contrario;
verificado algebraicamente, el sesgo es optimista para mezclas intra-bloque.)*
**Fortalecer:** tratar cada bloque colineal como una "súper-pila" en la
propagación (una sola σ para el grupo) y avisar en la UI cuando una mezcla
depende de un bloque.

### 1.3 El solver puede devolver soluciones subóptimas en silencio
CBC corre con `time_limit_s=10` y el `status` no se muestra al usuario: si el
tiempo se agota, la partición reportada puede estar por debajo del óptimo sin
aviso. El Big-M (`10·stock·max_grade`) es grande y puede degradar la precisión
numérica.
**Fortalecer:** (a) mostrar el status del solver y el gap cuando no es óptimo;
(b) time limit adaptativo al tamaño del problema; (c) acotar el Big-M por metal
(usar la ley máxima *de ese metal*, no la global).

### 1.4 Los CV por defecto (5–30%) son supuestos, no mediciones
Cuando una pila tiene una sola observación, su σ sale de `CV_DEFAULT`
(Au 15%, Ag/Pd 30%) — números razonables pero no calibrados.
**Fortalecer:** calibrarlos con las pilas que viajaron solas varias veces
(dispersión real entre lotes puros) y recalibrarlos con cada liquidación nueva.

### 1.5 El contrafáctico del bono es proyección del propio modelo
`valor_base` ("sin optimizar") lo proyecta el mismo modelo que se está
evaluando. Si las leyes estimadas tienen sesgo, la "mejora" lo hereda. Ya lo
mitigamos (base = solo metal rescatado, lectura honesta, reconciliación), pero
la reconciliación es manual.
**Fortalecer:** al cargar cada liquidación real, computar automáticamente
`(real − proyectado)/real` y mostrar el sesgo acumulado del modelo; liquidar el
bono **reconciliado** (recomendado y así acordado en la lectura honesta).

### 1.6 Parámetros de negocio con defaults razonables pero no justificados
- **Margen del 20%** sobre el umbral en "completar contenedor": fijo; debería
  escalar con la σ de la mezcla (mucho ruido → más holgura, poco → menos).
- **Umbral del 10%** del bono: se justificó sobre ruido en USD, pero la mejora
  del envío se mide en % de aprovechamiento — unidades distintas. Funciona como
  convención comercial; conviene dejarlo escrito así en el acuerdo.
- **Humedad 1% uniforme**: sin medición por pila; con Cu cerca del umbral (3%),
  un 2% de humedad extra puede cambiar si cobra o no.
**Fortalecer:** margen adaptativo a σ; pactar el 10% como convención contractual
explícita; medir humedad por categoría de material.

### 1.7 P_cobro asume normalidad
Φ(z) sobre distribuciones que están truncadas en 0 y no se testean. Efecto
menor (2–5 puntos de P_cobro) y en general conservador. **Fortalecer:** usar la
normal truncada cuando σ es grande relativa a la ley; es un cambio chico en
`risk.py`.

> Corrección a la auditoría: `k_safe` y `z_min` **sí son configurables** desde
> Ajustes › Riesgo (una pasada los reportó como hardcodeados). Lo que falta es
> justificar el default 1.0 en el acuerdo con el cliente.

---

## 2. Valor agregado para Megabytes

Lo que el sistema le da a Gilberto que hoy no tiene, con los números reales del
proyecto:

1. **No perder metal en $0.** El problema central del negocio. El sistema
   detecta metal bajo umbral *antes* de enviar (ej. real: Pd a 12 g/t en el
   sobrante = $10,248 brutos en juego) y dice exactamente cómo rescatarlo.
2. **Qué comprar y cuánto.** "Completar contenedor" convierte el problema en una
   orden de compra concreta: ~1.814 kg de la pila 025 → el sobrante pasa de
   cobrar 65% a 78% de su metal.
3. **El contenedor óptimo, explicado.** Partición en lotes que la refinería tasa
   por separado (92% aprovechado con el stock actual), con el porqué en lenguaje
   de negocio y el plano físico de pallets numerado para el galpón.
4. **Radiografía del inventario.** Leyes estimadas de 25/40 pilas sin pagar
   laboratorio, con confianza explícita por pila y metal (medida / estimada /
   sin determinar) — el usuario sabe de qué número fiarse.
5. **Validación del criterio propio.** El histórico demuestra que sus mezclas
   eran buenas (el modelo reproduce los pagos reales con ~3% de desvío). Eso
   construye confianza para delegar en el sistema lo que sigue.
6. **Un tablero honesto.** Todo en % de aprovechamiento (estable) y no en USD
   (volátil); los montos aparecen como referencia, nunca como promesa.
7. **Privacidad operativa:** las pilas se muestran solo por código; las fórmulas
   de clasificación de material no se filtran ni en pantalla ni en errores.

---

## 3. Cómo convertirlo en un activo de miles de dólares

El precio acordado ($6.000 + $200/mes) se sostiene — y crece — sobre tres
argumentos:

### 3.1 ROI medible por envío
Un contenedor es ~$600k de metal. Cada punto de aprovechamiento que el sistema
protege son **miles de dólares por envío** (~4 envíos/año). El caso del sobrante
(65→78%) o el Pd rescatado ($3,212/envío) pagan la mensualidad muchas veces.
**Acción:** que el panel del bono acumule también el "valor protegido" anual
proyectado — es el número que justifica la renovación.

### 3.2 El activo real son los datos, no el código
La tabla de leyes estimadas + confianza, derivada de *sus* 53 liquidaciones, no
existe en ningún otro lado y **mejora con cada envío** (cuando cerremos el loop
de ingesta, §1.1). Eso crea switching cost legítimo: irse del sistema es perder
la memoria calibrada del negocio.
**Acción:** cerrar el loop de ingesta cuanto antes; cada liquidación cargada
aumenta el valor del activo de forma automática y visible ("el modelo mejoró su
error de X% a Y% con tu último envío").

### 3.3 Replicabilidad a otros recicladores
El dominio (valorización, umbrales, MILP, estimación por regresión) es genérico
para cualquier reciclador que venda a refinería con deducciones por tonelada. Lo
específico de Megabytes (términos JX, formato xlsx, textos) está localizado y es
extraíble a configuración por cliente (§5). Cada cliente nuevo replica la
licencia con costo marginal bajo.
**Acción comercial:** cerrar con Megabytes como caso de referencia (con su
permiso, resultados en %, sin datos), y empaquetar "Aurix para recicladores".

---

## 4. Vulnerabilidades de código y desarrollo

De la auditoría de seguridad (17 hallazgos), filtrados y priorizados con mi
verificación. Contexto que baja el riesgo global: la app corre **detrás de
HTTPS**, en `127.0.0.1` detrás del nginx del VPS, con login, un solo tenant y
usuarios de confianza.

### Arreglar ya (antes de la entrega)
1. **Sin límite de intentos en login/PIN** (`auth.py`). Un PIN de 4 dígitos se
   fuerza en minutos. *Fix:* lockout de 5 min tras 5 intentos fallidos (10
   líneas).
2. **El ledger del bono vive en memoria** (`views/bono.py`): un reinicio del
   contenedor borra los envíos registrados. Es registro contractual → debe
   persistir. *Fix:* JSON/SQLite en `data/` con timestamp (medio día).
3. **Fallback silencioso a datos de ejemplo**: si falta `inventory.xlsx`, la app
   sigue con datos sembrados sin avisar — el usuario optimizaría inventario
   falso. *Fix:* banner rojo "datos de ejemplo" o error explícito.
4. **`sed` sin escape en `setup.sh`**: una contraseña con `&` o `|` corrompe el
   `.env`. *Fix:* escapar el valor (ya nos mordió una variante de esto).

### Arreglar pronto (primer mes)
5. **Escritura concurrente de `inventory_state.json`** sin lock: dos sesiones
   editando a la vez pierden cambios. *Fix:* `portalocker` o migrar a SQLite.
6. **XLSX corrupto/hostil sin manejo**: un zip renombrado crashea la vista de
   inventario. *Fix:* try/except + límite de tamaño (5 MB).
7. **Contenedor Docker corre como root.** *Fix:* `USER app` en el Dockerfile.
8. **Escapado HTML**: casi todo el HTML inyectado es de código propio (riesgo
   real bajo), pero los códigos de pila vienen del xlsx del usuario y algún día
   llegarán a un `st.markdown`. *Fix:* `html.escape()` en los componentes de
   `ui.py` que interpolan datos.
9. **Dependencias sin techo de versión** (`pulp>=2.7` permitirá PuLP 4.0 con
   breaking changes ya anunciados en los warnings). *Fix:* `pulp>=2.7,<3.0`,
   `streamlit` acotado, y un `requirements.lock`.

### Menores / higiene
10. Documentación del token de GitHub en URL (queda en bash history) → usar
    credential helper.
11. Sin logging estructurado ni backups del estado (`data/`) → logging +
    backup diario (cron + tar a almacenamiento externo).
12. `APP_PASSWORD` vacío no bloquea el arranque en producción → fallar el
    deploy si falta.

> Corrección a la auditoría: el supuesto "bypass de autenticación al recargar"
> no es tal — `st.session_state` muere con la sesión del navegador y la
> recarga vuelve a pedir contraseña. El punto válido detrás de ese hallazgo es
> el nº 2 (persistencia del ledger).

---

## 5. Opciones para escalar el proyecto

En orden de esfuerzo creciente. Lo importante: **el núcleo (dominio, optimizador,
datos) es Python puro sin Streamlit — migra sin cambios.** Las ~2.000 líneas de
UI son lo único acoplado.

| Etapa | Qué | Esfuerzo | Cuándo conviene |
|---|---|---|---|
| **E1 — Producción sólida** | SQLite para inventario+ledger, logging, backup diario, lockout de login, validación de xlsx | ~2 semanas | Ya (es parte de entregar bien la v1) |
| **E2 — El loop de datos** | Carga de liquidaciones desde la app, re-estimación y rebuild automáticos, reconciliación del bono | 2–3 semanas | Inmediatamente después: es la promesa "se afina solo" |
| **E3 — Multi-cliente** | Config por tenant (nombre, términos, formato xlsx, metales), Postgres con `tenant_id`, aislamiento de datos | 8–12 semanas | Cuando aparezca el 2º reciclador interesado |
| **E4 — Plataforma** | FastAPI + React, workers (Celery) para el MILP, roles y auditoría, API pública de inventario/lotes | 4–6 semanas más | Con 3+ clientes o si Megabytes pide multiusuario |

Anti-recomendación explícita: **no** saltar a E3/E4 ahora. Streamlit + un tenant
es la arquitectura correcta para el tamaño actual del negocio; sobre-ingeniería
hoy es plata y tiempo que no ve el cliente.

---

## 6. Mejoras continuas programadas (calendario propuesto)

**v1.1 — próximas 2 semanas (endurecimiento):**
lockout de login · ledger persistente · aviso de datos de ejemplo · fix de sed ·
validación de xlsx · `USER app` en Docker · pins de dependencias · logging +
backup diario.

**v1.2 — mes 1 (el loop de datos):**
pantalla "Cargar liquidación" → re-estima leyes → regenera análisis en
background · reconciliación automática del bono (real vs. proyectado, sesgo
acumulado) · status/gap del solver visible.

**v1.3 — mes 2–3 (afinar el motor):**
σ por bloque colineal (súper-pila) · CV calibrados desde lotes puros · margen
adaptativo en completar contenedor · humedad por categoría · normal truncada en
P_cobro · rotación de inventario (qué retener vs. enviar, edad de las pilas).

**Cadencia trimestral (alineada al ciclo de envíos, ~1 contenedor/3 meses):**
tras cada liquidación: recalibrar, medir precisión del modelo vs. real,
reportar al cliente "el modelo mejoró de X a Y" — ese reporte ES el argumento de
renovación de la mensualidad.

---

## 7. Mi opinión y consideraciones

**Lo que está genuinamente bien.** El núcleo es sólido y es la parte difícil:
la fórmula de la refinería reproducida al dólar y validada contra 53
liquidaciones reales (~3% de desvío), un MILP que modela exactamente la
economía del problema (umbrales y topes, que es donde vive todo el valor), y una
capa de honestidad — confianza por pila, P_cobro, lectura honesta del bono — que
es rara en software vendido a PyMEs y es tu mejor protección comercial. La
decisión de medir todo en % de aprovechamiento fue correcta: es defendible ante
cualquier variación de precios.

**El riesgo real no es el código, son los datos.** 14 de las pilas estimadas
vienen de "reparto equitativo" (confianza mínima) y 15 no tienen ley. El sistema
lo declara con etiquetas — bien — pero el valor de las recomendaciones está
acotado por esa calidad. La palanca más barata para subir la calidad de TODO el
sistema no es más código: es **cada liquidación nueva cargada** y, para las
pilas grandes sin ley, un ensayo de laboratorio puntual. Por eso E2 (el loop de
ingesta) es, en mi opinión, la única prioridad innegociable del roadmap.

**Cuidado con la sobreventa.** El histórico muestra que las mezclas de Gilberto
ya eran casi óptimas (+0.08% de re-mezcla). El valor del sistema no es "mejorar
lo que Gilberto hacía" — es (a) proteger contra el error caro que aún no pasó,
(b) decidir compras con números, (c) conservar el conocimiento fuera de la
cabeza de una persona, y (d) mejorar con cada envío. Vendé eso; los números
inflados se caen en la primera liquidación y este sistema está diseñado
justamente para no inflarse.

**El bono quedó bien parado.** Base = solo metal rescatado, por envío, hacia
adelante, reconciliado contra el dato real. Es chico por envío ($482 en la
proyección actual) pero es **indiscutible** — y un bono indiscutible cobrado
vale más que uno grande discutido. Dejá el 10% y el 15% escritos como convención
en el acuerdo, con la reconciliación como regla.

**Sobre la arquitectura:** Streamlit fue la elección correcta y sigue siéndolo.
El día que esto necesite React será porque el negocio creció — buen problema.
Lo único que trataría como deuda real hoy es la lista "arreglar ya" del §4 y la
observabilidad mínima (si Gilberto llama diciendo "me da error", hoy no hay
ningún log que mirar).

**En síntesis:** el modelo está listo para entregarse como v1 con la lista
corta del §4 aplicada. Su valor como activo crece con una sola cosa por encima
de todas: cerrar el ciclo con las liquidaciones reales. Ahí deja de ser una
buena herramienta de cálculo y pasa a ser lo que prometimos — un sistema que
vale más cada trimestre que se usa.
