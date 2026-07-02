# Propuesta y Presupuesto de Desarrollo de Software

**Optimizador de Mezclas para Recuperación de Metales (RAEE)**

| | |
|---|---|
| **Para:** | Gilberto Rujana — Servicios Megabytes, C.A. |
| **De:** | Omar Moya — OMIA Agency |
| **Contacto:** | Omarmoya@omiaagency.com · 0424-2414306 |
| **Fecha:** | 1 de julio de 2026 |
| **Validez de la oferta:** | 30 días |

---

## 1. Objetivo

Esta propuesta cubre la entrega de una aplicación a medida para Servicios
Megabytes, C.A. que recomienda la mezcla óptima de materiales electrónicos
(RAEE) a enviar a la refinería, para maximizar el porcentaje de metal que esta
paga por cada contenedor. El modelo replica la fórmula de liquidación de la
refinería y fue validado contra los 53 envíos históricos reales: reproduce lo
que la refinería pagó con un desvío de ±3%.

## 2. Alcance y entregables

El modelo entregable a Servicios Megabytes, C.A. — **desarrollado, probado
(115 pruebas automáticas) y listo para operar** — incluye:

**Optimización del envío**
- Simulador de mezclas que replica la fórmula de liquidación de la refinería
  (Cu, Au, Ag, Pt, Pd) con sus cargos y deducciones, validado contra los 53
  envíos históricos.
- Optimizador del contenedor de 23 toneladas, repartido en los lotes óptimos
  que la refinería tasa por separado.
- **Plano de carga por pallets**: cada pallet numerado en orden de carga y
  clasificado (muy rico / poco rico / relleno), con alerta si alguno quedaría
  bajo el umbral de pago. Visualización 3D del contenedor y sus lotes.
- **Completar contenedor**: cuando el material en depósito dejaría algún metal
  sin cobrar, el sistema indica **qué pila comprar y cuántos kilos** para
  rescatarlo.
- **Plan de rotación**: simula los envíos sucesivos hasta agotar el stock y
  señala las pilas que nunca salen (mercancía que envejece y necesita
  refuerzo, ensayo o venta aparte).

**Inteligencia que mejora sola**
- Sistema de confianza por pila y por metal (medida / estimada / no
  determinada), con margen de error y **probabilidad de cobro** por lote, para
  no recomendar mezclas que la refinería podría no pagar al analizarlas.
- **Carga de liquidaciones desde la propia aplicación**: cada liquidación
  nueva de la refinería re-estima las leyes y recalibra el modelo
  automáticamente — sin técnicos ni redespliegues.
- **Evolución del modelo** en el panel: con cada liquidación cargada, el
  sistema muestra cómo mejora su precisión ("el error pasó de ±X% a ±Y%").
- Carga de inventario por Excel (mismo formato actual) y edición en línea.

**Seguridad y operación**
- Aplicación web con acceso por contraseña (con bloqueo ante intentos
  repetidos) y conexión cifrada (HTTPS). El inventario se muestra **solo por
  código**: los nombres de los materiales no aparecen en pantalla.
- Copias de seguridad diarias automáticas del estado (inventario, registros)
  y registro de actividad para diagnóstico.
- Instalación y puesta en marcha en servidor administrado por OMIA Agency.

## 3. Tecnología y arquitectura

El software se desarrolla con tecnologías estándar de la industria, robustas y
de amplio soporte: **Python** (lógica de cálculo y optimización), **Streamlit**
(interfaz web), **PuLP** (optimización matemática MILP), **NumPy/pandas**
(cálculo numérico y estimación de leyes desde el histórico), **Plotly**
(visualización 3D), **Docker** (despliegue confiable y reproducible) y
**servidor VPS con HTTPS**.

## 4. No incluye

- Análisis de laboratorio de las pilas (opcional y externo; mejora la
  precisión pero no es necesario para operar).
- Integraciones con otros sistemas no mencionados en esta propuesta.
- Capacitación más allá de la inducción inicial incluida.
- Funcionalidades nuevas fuera del alcance de la sección 2 (se cotizan aparte).

## 5. Inversión

| Concepto | Detalle | Monto (USD) |
|---|---|---|
| **Setup + servidor + software** | Instalación y puesta en marcha en el servidor, gestionado por OMIA Agency, y el modelo completo de la sección 2. Pago en 2 cuotas (ver Forma de pago). | **USD 5.000** |
| **Primer mes (garantía)** | Ajustes y correcciones sobre lo entregado. | Sin costo |
| **Soporte mensual (desde el 2.º mes)** | Alojamiento y administración del servidor (copias de seguridad diarias, actualizaciones, monitoreo) + 4 horas de soporte a demanda al mes. Hora adicional: USD 30. | **USD 250 / mes** |
| **Bono de éxito (condicionado)** | 15% del valor del **metal rescatado en cada envío** ejecutado con el modelo (metal que habría pagado $0 y se cobró gracias a la mezcla), cuando la mejora del envío supera el 10%. Lo calcula y registra el propio modelo y se liquida **reconciliado con la liquidación real** de la refinería (ver sección 11). | Variable, por envío |

Montos en dólares estadounidenses (USD). El soporte mensual puede cancelarse
con 30 días de aviso; en ese caso la aplicación sigue operativa, y OMIA deja de
administrar servidor, copias de seguridad y actualizaciones.

## 6. Forma de pago

- **USD 2.500 al inicio**: cubre el setup, la implementación y el montaje
  (servidor y puesta en marcha).
- **USD 2.500 a los primeros resultados**: se abona con la primera liquidación
  de la refinería de un envío armado con el modelo.
- **Primer mes de soporte: sin costo** (mes de garantía).
- **Desde el segundo mes: USD 250 mensuales**, por adelantado.
- El **bono de éxito** es adicional, por envío, y se rige por la sección 11.

## 7. Plazo de entrega

- **Presentación del modelo completo**: en vivo, operando sobre el inventario y
  el histórico reales del cliente.
- Entrega del modelo: **inmediata al aprobar la propuesta** — el desarrollo
  está finalizado, probado y operativo.
- Segundo pago: con la primera liquidación de la refinería de un envío
  ejecutado con el modelo.

## 8. Garantía

El primer mes posterior a la entrega es sin costo. Durante ese mes se incluyen
los ajustes y correcciones sobre lo entregado que hagan falta para que el
sistema opere según la sección 2. Las funcionalidades nuevas fuera de ese
alcance se cotizan aparte.

## 9. Condiciones

- Las leyes de las pilas se estiman a partir del histórico de envíos y **se
  afinan automáticamente con cada nueva liquidación cargada**; no requieren
  laboratorio (los ensayos son opcionales y mejoran la precisión).
- Los precios de los metales y los términos de la refinería son configurables
  desde la aplicación y deben mantenerse actualizados para que el cálculo sea
  preciso.
- El servidor queda gestionado por OMIA Agency mientras el soporte mensual
  esté vigente.
- Esta oferta es válida por 30 días desde la fecha indicada.

## 10. Confidencialidad

OMIA Agency mantendrá bajo estricta confidencialidad toda la información de
Servicios Megabytes, C.A. a la que acceda durante el proyecto: inventarios,
recetas de mezcla, datos de liquidación de la refinería, precios, proveedores,
clientes y cualquier dato comercial u operativo. Esta información no será
divulgada ni utilizada para ningún fin ajeno a este proyecto, y la obligación
permanece vigente aún después de finalizada la relación.

## 11. Exclusividad, propiedad y bono de éxito

**Exclusividad.** El modelo desarrollado es de **uso exclusivo de Servicios
Megabytes, C.A.**: OMIA Agency no lo comercializará, licenciará ni reutilizará
para terceros ni para empresas del mismo rubro, ni total ni parcialmente. Esta
exclusividad es una ventaja competitiva del cliente: ningún otro reciclador
podrá acceder a esta herramienta.

**Propiedad y licencia.** Servicios Megabytes, C.A. recibe una **licencia de
uso exclusiva, perpetua e ilimitada** del software para su operación. La
titularidad del código y del método permanece en OMIA Agency, sujeta a la
obligación de exclusividad del párrafo anterior.

**Bono de éxito (en contraprestación por la exclusividad).** Aplica **por cada
envío** ejecutado con el modelo, hacia adelante:

1. **Disparador:** la mejora del envío supera el **10%** (piso de ruido del
   análisis de la refinería). La mide el propio modelo comparando el resultado
   del envío optimizado contra lo que ese mismo material habría rendido sin
   optimizar.
2. **Base:** el valor del **metal rescatado en ese envío** — el metal que, sin
   el modelo, habría quedado bajo el umbral de deducción y pagado $0, y que
   gracias a la mezcla se cobró. **No** es un porcentaje del contenedor ni de
   la facturación: solo del metal que el modelo salvó.
3. **Bono:** **15% de esa base**, por envío. El módulo "Bono" de la aplicación
   lo calcula, lo registra y lo **reconcilia contra la liquidación real** de la
   refinería antes de liquidarse — el monto final siempre queda atado al dato
   real, no a la proyección.

Los parámetros (umbral 10%, tasa 15%) son la convención acordada entre las
partes y quedan configurados en la aplicación.

## 12. Aceptación

En conformidad con los términos de esta propuesta:

<br><br>

| | |
|---|---|
| \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ | \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ |
| Gilberto Rujana | Omar Moya |
| Servicios Megabytes, C.A. | OMIA Agency |
| Fecha: \_\_\_\_\_\_\_\_\_\_\_\_ | Fecha: \_\_\_\_\_\_\_\_\_\_\_\_ |
