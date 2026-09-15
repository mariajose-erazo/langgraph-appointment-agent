# Cne By Nails — Domain Specification

## 1. Objetivo

Este documento define el dominio y las reglas de negocio de la primera versión del sistema de gestión de citas de Cne By Nails.

Su objetivo es establecer qué debe hacer el sistema y qué reglas debe respetar antes de comenzar su implementación.

Esta especificación corresponde al MVP del proyecto y podrá evolucionar en versiones posteriores.

---

# 2. Alcance del MVP

La primera versión estará enfocada exclusivamente en servicios relacionados con manicure y pedicure.

Incluye:

* Uñas acrílicas.
* PolyGel.
* Press On.
* Base Rubber.
* Kapping / Dipping.
* Esmaltado semipermanente.
* Esmaltado tradicional.
* Gel Evolution.
* Hidratación con parafina para manos y pies.
* Retoques.
* Reparación de uñas.
* Retiros.

## Fuera del alcance

El MVP no manejará:

* Cejas.
* Depilación.
* Pagos.
* Anticipos.
* Procesamiento de pagos.
* Penalizaciones económicas.
* No asistencia del cliente.
* Citas los domingos.
* Citas en días festivos.
* Facturación.
* Inventario.
* Programas de fidelización.

---

# 3. Profesionales

El establecimiento contará inicialmente con tres profesionales:

* Laura.
* Valentina.
* María José.

Las tres profesionales podrán realizar todos los servicios incluidos dentro del alcance del MVP.

No existirán inicialmente restricciones de servicios por profesional.

Toda cita deberá estar asociada a una profesional.

---

# 4. Horario de atención

El establecimiento funciona de lunes a sábado.

| Día       | Horario       |
| --------- | ------------- |
| Lunes     | 08:00 - 18:00 |
| Martes    | 08:00 - 18:00 |
| Miércoles | 08:00 - 18:00 |
| Jueves    | 08:00 - 18:00 |
| Viernes   | 08:00 - 18:00 |
| Sábado    | 08:00 - 18:00 |
| Domingo   | Cerrado       |
| Festivos  | Cerrado       |

Una cita debe realizarse completamente dentro del horario de atención.

Por lo tanto, no basta con que una cita comience antes de las 18:00. El servicio debe poder finalizar dentro del horario permitido.

---

# 5. Almuerzo de las profesionales

Cada profesional tendrá diariamente un periodo de almuerzo de:

**60 minutos.**

El horario de almuerzo puede ser diferente para cada profesional y dependerá de la disponibilidad de la agenda.

Para el MVP, el almuerzo será tratado como un bloqueo de agenda.

Durante ese bloqueo no podrán asignarse citas a la profesional.

Ejemplo:

* Laura: 12:00 - 13:00.
* Valentina: 13:00 - 14:00.
* María José: 12:30 - 13:30.

Estos horarios son ejemplos y no representan horarios fijos del negocio.

La forma exacta de asignar automáticamente los horarios de almuerzo se definirá posteriormente.

---

# 6. Tiempo entre citas

Después de cada cita deberán reservarse:

**10 minutos de buffer.**

Este tiempo permite preparar el puesto de trabajo antes de atender a la siguiente persona.

Ejemplo:

Servicio:

09:00 - 10:00.

Buffer:

10:00 - 10:10.

Siguiente cita posible:

10:10.

El buffer forma parte del cálculo de disponibilidad, pero no de la duración real del servicio prestado al cliente.

---

# 7. Retiros

El sistema distinguirá entre dos situaciones diferentes.

## 7.1 Retiro como servicio independiente

El cliente puede reservar únicamente un retiro.

Este servicio tiene su propia duración y precio.

Ejemplo:

Retiro de semipermanente:

* Precio: $10.000.
* Duración: 30 minutos.

## 7.2 Retiro previo a otro servicio

Cuando el cliente necesite un retiro antes de realizar un nuevo servicio, se agregarán:

**15 minutos adicionales.**

Ejemplo:

Semipermanente manos:

60 minutos.

Retiro previo:

15 minutos.

Duración total del trabajo:

75 minutos.

Buffer:

10 minutos.

Tiempo total bloqueado:

85 minutos.

---

# 8. Servicios y precios

## 8.1 Acrílicas y PolyGel

| Servicio                                   |       Precio |
| ------------------------------------------ | -----------: |
| Acrílicas hasta número 3                   |     $130.000 |
| PolyGel hasta número 3                     |     $130.000 |
| Cada número adicional después del número 3 |     +$10.000 |
| Recubrimiento acrílico en uñas naturales   | $85.000 base |
| Recubrimiento PolyGel en uñas naturales    | $85.000 base |
| Retoque acrílicas                          |      $80.000 |
| Retoque PolyGel                            |      $80.000 |
| Una uña acrílica                           |      $15.000 |
| Una uña PolyGel                            |      $15.000 |
| Retiro de acrílicos                        |      $15.000 |

### Regla de precio por largo

Acrílicas y PolyGel tienen un precio base de $130.000 hasta el número 3.

Después del número 3 se agregan $10.000 por cada número adicional.

Ejemplos:

| Largo    |   Precio |
| -------- | -------: |
| Número 3 | $130.000 |
| Número 4 | $140.000 |
| Número 5 | $150.000 |
| Número 6 | $160.000 |

## Precio "desde"

La carta original indica que algunos servicios tienen precio "desde $85.000".

Para poder trabajar con el MVP, $85.000 será considerado el precio base.

Si posteriormente existen variables que modifiquen este precio, deberán incorporarse como nuevas reglas de negocio.

El sistema no deberá inventar recargos que no estén definidos.

---

# 8.2 Press On

| Servicio         |   Precio |
| ---------------- | -------: |
| Press On         | $100.000 |
| Retoque Press On |  $80.000 |
| Una uña Press On |  $10.000 |

---

# 8.3 Base Rubber

| Servicio    |  Precio |
| ----------- | ------: |
| Base Rubber | $70.000 |

---

# 8.4 Kapping / Dipping

| Servicio                        |  Precio |
| ------------------------------- | ------: |
| Recubrimiento Kapping / Dipping | $80.000 |
| Retoque Kapping / Dipping       | $80.000 |

---

# 8.5 Semipermanente

| Servicio                    |  Precio |
| --------------------------- | ------: |
| Manos semipermanente        | $50.000 |
| Pies semipermanente         | $50.000 |
| Manos semipermanente hombre | $40.000 |
| Pies semipermanente hombre  | $40.000 |
| Retiro manos y pies         | $15.000 |
| Retiro semipermanente       | $10.000 |

---

# 8.6 Tradicional y Gel Evolution

| Servicio            |  Precio |
| ------------------- | ------: |
| Manos Gel Evolution | $30.000 |
| Pies Gel Evolution  | $30.000 |
| Manos tradicionales | $25.000 |
| Pies tradicionales  | $25.000 |

No se realizan decoraciones sobre esmaltado tradicional.

---

# 8.7 Spa de manos y pies

| Servicio                       |  Precio |
| ------------------------------ | ------: |
| Hidratación con parafina pies  | $25.000 |
| Hidratación con parafina manos | $20.000 |

---

# 9. Decoraciones

Las decoraciones pueden generar un valor adicional.

Ejemplos:

* Glitter.
* Piedras.
* Stickers.
* Diseños especiales.
* Otras decoraciones.

El valor depende de la complejidad del diseño.

En el MVP el precio de las decoraciones no se calculará automáticamente.

Cuando el cliente solicite una decoración cuyo precio no pueda determinarse mediante una regla conocida, el sistema deberá indicar que el precio debe ser confirmado por el establecimiento.

El agente nunca deberá inventar el precio de una decoración.

No se realizan decoraciones sobre esmaltado tradicional.

---

# 10. Duraciones simuladas

Las siguientes duraciones son valores simulados para el desarrollo del MVP.

No representan necesariamente los tiempos reales del establecimiento y podrán modificarse posteriormente.

| Servicio                            | Duración |
| ----------------------------------- | -------: |
| Acrílicas                           |  150 min |
| PolyGel                             |  150 min |
| Recubrimiento acrílico              |   90 min |
| Recubrimiento PolyGel               |   90 min |
| Retoque acrílicas                   |  120 min |
| Retoque PolyGel                     |  120 min |
| Reparación de una uña acrílica      |   30 min |
| Reparación de una uña PolyGel       |   30 min |
| Retiro de acrílico independiente    |   30 min |
| Press On                            |   90 min |
| Retoque Press On                    |   75 min |
| Reparación de una Press On          |   20 min |
| Base Rubber                         |   75 min |
| Kapping / Dipping                   |   90 min |
| Retoque Kapping / Dipping           |   90 min |
| Semipermanente manos                |   60 min |
| Semipermanente pies                 |   60 min |
| Semipermanente manos hombre         |   60 min |
| Semipermanente pies hombre          |   60 min |
| Retiro manos y pies independiente   |   45 min |
| Retiro semipermanente independiente |   30 min |
| Gel Evolution manos                 |   45 min |
| Gel Evolution pies                  |   45 min |
| Tradicional manos                   |   45 min |
| Tradicional pies                    |   45 min |
| Parafina manos                      |   30 min |
| Parafina pies                       |   30 min |

---

# 11. Disponibilidad

Una profesional se considera disponible cuando puede realizar completamente el servicio solicitado dentro del intervalo requerido.

Para calcular disponibilidad deben considerarse:

* Horario de apertura.
* Horario de cierre.
* Duración del servicio.
* Retiro adicional, si aplica.
* Buffer posterior de 10 minutos.
* Citas existentes.
* Bloqueo de almuerzo.
* Estado de las citas existentes.

Una profesional no puede tener dos citas activas superpuestas.

Una cita cancelada no bloquea disponibilidad.

---

# 12. Selección de profesional

El cliente podrá solicitar una profesional específica.

Si solicita una profesional, la disponibilidad deberá comprobarse exclusivamente para esa profesional.

Si el cliente no tiene preferencia, el sistema podrá ofrecer o asignar alguna de las profesionales disponibles.

En el MVP no se define todavía una estrategia automática de prioridad entre Laura, Valentina y María José.

Por lo tanto, si varias profesionales están disponibles, el sistema podrá presentar las opciones disponibles al cliente.

---

# 13. Creación de citas

Para crear una cita deberán conocerse como mínimo:

* Cliente.
* Servicio.
* Fecha.
* Hora.
* Profesional.

Antes de crearla deberán validarse:

1. Que el servicio exista y esté activo.
2. Que la profesional exista y esté activa.
3. Que el día sea laborable.
4. Que el servicio completo pueda realizarse dentro del horario de atención.
5. Que la profesional esté disponible.
6. Que no exista una superposición con otra cita.
7. Que no exista un bloqueo de almuerzo durante ese intervalo.

Una cita solamente podrá persistirse después de superar todas las validaciones.

---

# 14. Estados de una cita

Para el MVP una cita podrá tener uno de los siguientes estados:

### SCHEDULED

La cita está agendada y ocupa espacio en la agenda.

### CANCELLED

La cita fue cancelada y deja de ocupar espacio en la agenda.

### COMPLETED

La cita ya fue atendida.

No se manejarán por ahora estados relacionados con:

* Pago pendiente.
* Pago confirmado.
* No-show.
* Anticipos.

---

# 15. Cancelación

Una cita puede cancelarse únicamente cuando faltan al menos:

**24 horas para su inicio.**

Ejemplo:

Cita:

Sábado 15:00.

Solicitud de cancelación:

Viernes 16:00.

Tiempo restante:

23 horas.

Resultado:

Cancelación no permitida.

En el MVP la cancelación no tendrá consecuencias económicas.

Una cita ya cancelada no podrá cancelarse nuevamente.

Una cita completada no podrá cancelarse.

---

# 16. Reprogramación

Una cita podrá reprogramarse únicamente cuando falten al menos:

**8 horas para su inicio.**

Antes de confirmar la reprogramación deberá comprobarse nuevamente:

* Día laborable.
* Horario.
* Duración.
* Disponibilidad.
* Profesional.
* Conflictos con otras citas.
* Almuerzo.

Reprogramar una cita implica cambiar su fecha y/o hora manteniendo la cita existente.

Una cita cancelada o completada no podrá reprogramarse.

---

# 17. Información mínima de una cita

Toda cita deberá contener como mínimo:

* Identificador.
* Cliente.
* Servicio.
* Profesional.
* Fecha y hora de inicio.
* Fecha y hora de finalización.
* Estado.
* Indicación de si necesita retiro adicional.

El precio del servicio podrá calcularse a partir del servicio y sus reglas de precio.

---

# 18. Casos de uso del MVP

El núcleo del sistema deberá permitir:

* Consultar servicios.
* Consultar información de un servicio.
* Consultar precio.
* Consultar profesionales.
* Consultar horarios disponibles.
* Consultar disponibilidad para una fecha y hora.
* Crear una cita.
* Consultar una cita.
* Cancelar una cita.
* Reprogramar una cita.

Estos casos de uso deberán funcionar independientemente del canal de entrada.

Por ejemplo, en diferentes etapas el sistema podrá utilizar:

* Consola.
* Telegram.
* WhatsApp.
* Interfaz web.

Las reglas de negocio no deben depender del canal utilizado.

---

# 19. Principio de independencia tecnológica

Las reglas descritas en este documento pertenecen al negocio y no a una tecnología específica.

Por lo tanto, conceptos como:

* Gemini.
* Otro proveedor de LLM.
* MCP.
* Chroma.
* SQLite.
* Telegram.
* FastAPI.

no forman parte de las reglas del dominio.

Estas tecnologías podrán utilizarse para implementar el sistema, pero deberán poder reemplazarse sin cambiar las reglas descritas en esta especificación.

---

# 20. Decisiones pendientes para versiones posteriores

No bloquean el desarrollo del MVP, pero deberán definirse si el sistema evoluciona:

* Estrategia automática para asignar profesional cuando existen varias disponibles.
* Regla automática para decidir el horario de almuerzo.
* Precio detallado de decoraciones.
* Variables que modifican los servicios cuyo precio originalmente aparece como "desde".
* Anticipación máxima permitida para reservar.
* Reservas para el mismo día.
* Recordatorios automáticos.
* Citas recurrentes.
* Lista de espera.
