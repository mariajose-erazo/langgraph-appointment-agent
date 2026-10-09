# CNE By Nails — Software Architecture

## 1. Introducción y objetivos

### 1.1. Propósito

Este documento define la arquitectura de **CNE By Nails AI Agent**, un agente conversacional orientado a la atención al cliente y gestión de citas para un establecimiento de manicure y pedicure.

Establece los componentes del sistema, sus responsabilidades, interacciones y decisiones técnicas, sirviendo como referencia para su desarrollo y evolución.

Distingue entre la arquitectura actual y la arquitectura objetivo.

### 1.2. Problema del negocio

La gestión de citas requiere interpretar solicitudes, coordinar profesionales, verificar horarios y evitar conflictos de agenda.

El sistema busca automatizar estos procesos mediante conversaciones en lenguaje natural, manteniendo el cumplimiento de ...................................las reglas del negocio.

### 1.3. Objetivo general

Desarrollar un agente conversacional capaz de interpretar solicitudes, mantener el contexto y gestionar citas mediante la integración de modelos de lenguaje, orquestación de flujos y lógica determinista.

**Objetivos específicos:**

- Interpretar consultas, solicitudes y correcciones en lenguaje natural.
- Mantener el contexto entre turnos de conversación.
- Transformar solicitudes en datos estructurados y validados.
- Aplicar reglas del negocio y consultar disponibilidad real.
- Gestionar reservas y cancelaciones mediante integraciones autorizadas.
- Responder preguntas utilizando información confiable del negocio.

### 1.4. Alcance del MVP

**Incluye:**

- Atención conversacional y consultas informativas.
- Gestión de citas para servicios de manicure y pedicure.
- Selección de profesional, fecha y hora.
- Validación de horarios, duración, descansos y disponibilidad.
- Creación y cancelación de reservas.
- Propuesta de alternativas ante indisponibilidad.

**Excluye:**

- Procesamiento de pagos y facturación.
- Inventario y programas de fidelización.
- Gestión de personal y nómina.
- Penalizaciones por inasistencia.
- Servicios fuera del alcance definido para el MVP.

Las reglas operativas específicas se documentan en `domain-spec.md`.

### 1.5. Requisitos de calidad

- **Confiabilidad:** ninguna reserva se confirma sin validación y registro exitoso.
- **Consistencia:** prevención de conflictos y reservas duplicadas.
- **Mantenibilidad:** componentes modulares con responsabilidades definidas.
- **Testabilidad:** reglas del negocio verificables independientemente del LLM.
- **Extensibilidad:** incorporación de servicios, profesionales e integraciones con cambios localizados.
- **Seguridad:** protección de datos y control de operaciones autorizadas.
- **Observabilidad:** trazabilidad de operaciones, resultados y errores.

### 1.6. Principios y restricciones

- El LLM interpreta solicitudes, pero no decide ni ejecuta operaciones de negocio sin validación.
- Python implementa las reglas deterministas.
- La información operacional se consulta en fuentes confiables.
- El dominio permanece independiente del proveedor de LLM y de las integraciones externas.
- La implementación es incremental y respaldada por pruebas.

### 1.7. Estado del proyecto

**Implementado:** componentes conversacionales con Gemini, LangChain y LangGraph; modelos y fusión de solicitudes de citas; reglas de agendamiento y pruebas asociadas.

**En desarrollo:** interpretación estructurada de mensajes e integración con el estado de las solicitudes.

**Pendiente:** persistencia operacional, consulta de disponibilidad real y ejecución de reservas mediante integraciones externas.
l

## 4. Stack tecnológico

La arquitectura centralizará los servicios de inteligencia artificial en **Microsoft Foundry**, conservando Gemini como modelo de lenguaje actualmente implementado.

Se utilizará Azure Cosmos DB for NoSQL como servicio unificado de persistencia operacional y almacenamiento vectorial para RAG, manteniendo ambas responsabilidades separadas lógicamente.

| Tecnología | Responsabilidad | Estado |
|---|---|---|
| **Python 3.11** | Lógica del negocio, modelos de datos y validaciones. | Implementado |
| **Gemini** | Interpretación del lenguaje natural y generación de respuestas. | Implementado |
| **LangChain / LCEL** | Composición de prompts y cadenas de procesamiento. | Implementado |
| **LangGraph** | Orquestación y gestión del estado conversacional. | Implementado |
| **Microsoft Foundry** | Plataforma de servicios de IA y acceso a modelos de embeddings. | Propuesto |
| **Azure Cosmos DB for NoSQL** | Persistencia de citas, horarios y profesionales; almacenamiento e indexación vectorial para RAG. | Propuesto |
| **FastMCP** | Exposición de herramientas de consulta y gestión de citas mediante MCP. | Propuesto |
| **Foundry Observability** | Trazabilidad, monitoreo y evaluación del agente. | Propuesto |
| **Pytest** | Pruebas unitarias y de integración. | Implementado |

### 4.1. Criterios tecnológicos

- **Centralización:** nuevos servicios de IA integrados mediante Microsoft Foundry.
- **Desacoplamiento:** dominio independiente de los proveedores de IA e infraestructura.
- **Separación de responsabilidades:** datos operacionales y conocimiento vectorial gestionados mediante módulos y contenedores independientes.
- **Confiabilidad:** operaciones críticas validadas mediante Python y fuentes de información verificables.
- **Evolución incremental:** incorporación de tecnologías según las necesidades del MVP.

Las integraciones propuestas estarán sujetas a validación técnica, disponibilidad y costos antes de su implementación.

## Interpretación estructurada de turnos

La unidad `chains/turn_interpretation.py` transforma el mensaje actual de la
clienta en un `TurnInterpretation` validado por Pydantic mediante la salida
estructurada nativa de Gemini. El historial reciente se usa únicamente para
resolver referencias contextuales y la salida representa exclusivamente el
delta del turno actual.

Esta unidad no normaliza valores, no consulta catálogos ni disponibilidad, no
crea `AppointmentRequestPatch`, no modifica el estado conversacional y no
ejecuta reservas, cancelaciones o herramientas. La normalización determinista
y la integración con LangGraph permanecen como pasos separados.

## Estado acumulado de citas en LangGraph

El grafo procesa cada turno mediante inicialización de la solicitud,
interpretación estructurada y normalización determinista antes de generar la
respuesta conversacional. Conserva por `thread_id` la última interpretación,
el resultado de normalización y el `AppointmentRequest` acumulado.

Los catálogos y el reloj de referencia son entradas obligatorias del contexto
de ejecución. Un resultado bloqueante conserva la solicitud previa; un cambio
solo se publica en el estado después de completar exitosamente el merge. El
checkpointer actual es local y efímero y usa serialización de confianza para
preservar los dataclasses inmutables del dominio.

## Routing conversacional posterior a la normalizacion

Despues de `normalize_turn`, una funcion pura selecciona la rama mediante
conditional edges. Los problemas de configuracion se propagan como errores
tecnicos. Los resultados `INVALID` y `NEEDS_CLARIFICATION` se atienden con
nodos deterministas separados; un `SUCCESS` se divide entre respuesta
informativa y conversacional sin reducir la lista de intenciones a una sola.

Las aclaraciones e invalidaciones generan un `AIMessage` a partir de codigos y
datos estructurados. No invocan el LLM, no modifican `AppointmentRequest` y no
ejecutan herramientas. La respuesta exitosa recibe explicitamente la solicitud
acumulada, la interpretacion del turno, sus preguntas informativas y los
contextos autorizados. Este nodo puede describir preferencias recopiladas,
pero no confirma reservas, cancelaciones ni disponibilidad.

Cuando el turno inmediatamente anterior termino en `NEEDS_CLARIFICATION`, el
nodo de interpretacion conserva referencias locales a la interpretacion y al
resultado anteriores antes de invocar Gemini para el delta actual. Una funcion
pura puede reconciliar ambos resultados antes de sobrescribir el estado. En la
V1 esta reconciliacion se limita a completar deterministicamente una hora de
12 horas pendiente con una respuesta inequivoca de manana o tarde. Los cambios
del turno bloqueado se reintentan juntos, manteniendo la atomicidad; preguntas
laterales, contradicciones y respuestas no reconocidas no reconstruyen el
turno anterior.

## Readiness y consulta determinista de disponibilidad

Las intenciones `CHECK_AVAILABILITY` y `BOOK_APPOINTMENT` atraviesan una capa
de readiness después de una normalización exitosa. Esta capa pura exige un
servicio con identidad canónica (o retiro independiente), fecha y hora exactas
y una profesional resuelta o la selección explícita `ANY`. Un periodo horario
no equivale a una hora exacta. La ausencia de retiro no bloquea la consulta y
se conserva como `UNSPECIFIED`; operacionalmente no agrega duración en V1.

Una solicitud incompleta termina en una pregunta determinista y no consulta la
agenda. Una solicitud lista se transforma en `ScheduleQuery`. El puerto
`AvailabilityProvider` solo devuelve un `ScheduleSnapshot`: profesionales,
citas, almuerzos y cierres autorizados. No interpreta lenguaje, no calcula
disponibilidad y no ofrece operaciones de creación o reserva.

El dominio suma las duraciones de las definiciones operacionales enlazadas por
`canonical_id`, agrega 15 minutos para retiro `ADDON` y un único buffer final
de 10 minutos. Evalúa intervalos semiabiertos y aplica el buffer tanto frente a
la cita anterior como frente a una cita posterior. Lunes a sábado operan de
08:00 a 18:00; domingos y cierres inyectados no operan. Los almuerzos son
bloqueos de 60 minutos. `SCHEDULED` y `COMPLETED` bloquean; `CANCELLED` no.

Para `ANY` se evalúan todas las profesionales autorizadas con las mismas reglas
y se devuelven todas las disponibles en orden estable por ID. Ese orden no es
un ranking y no asigna automáticamente una profesional. No se buscan horarios
alternativos en esta etapa.

`appointment_readiness` y `availability_result` son resultados derivados del
último turno. LangGraph los limpia al comenzar el turno siguiente y el
checkpointer los aísla por `thread_id`. Un resultado de disponibilidad nunca se
reutiliza como garantía para reservar. `BOOK_APPOINTMENT` realiza exactamente
la misma consulta de solo lectura que `CHECK_AVAILABILITY`; la reserva real
permanece fuera del alcance de esta etapa.

## Persistencia operacional con Azure Cosmos DB

La agenda persistente se integra mediante `CosmosAvailabilityProvider`, que
implementa el mismo puerto usado por el provider in-memory. LangGraph recibe el
provider por composición y no conoce la tecnología de persistencia. Cosmos
solo suministra hechos operacionales validados; duración, buffer, horario,
solapamientos y disponibilidad continúan siendo reglas Python.

La cuenta utiliza tres containers. `professionals` tiene partition key
`/business_id`; `schedule_entries` reúne citas y bloqueos individuales con
partition key `/schedule_key`, cuyo valor es `business_id#YYYY-MM-DD`; y
`business_closures` usa `/business_id`. Todas las lecturas de agenda indican
explícitamente la partición diaria y evitan consultas cross-partition en el
camino normal.

Las fechas de negocio se almacenan como `YYYY-MM-DD` de Bogotá. Los instantes
se almacenan en UTC con timezone explícita y el adapter valida que correspondan
a la fecha local declarada. Las citas persisten `service_ends_at` como hecho
histórico, pero no buffer, `occupied_until` ni resultados de disponibilidad.

Los bloqueos individuales pueden ser `lunch`, `absence`, `vacation` u `other`.
Todos bloquean; solo `lunch` exige exactamente 60 minutos y expone el motivo
específico de almuerzo. Los festivos y cierres globales son documentos
separados y nunca se infieren.

Para `ANY`, Cosmos filtra el subconjunto de profesionales conocidas que está
activo y autorizado para todos los servicios. Python evalúa la disponibilidad
de todas ellas, sin ranking ni selección automática. Para una profesional
específica, inexistencia, inactividad o falta de autorización son errores de
precondición y no una agenda vacía.

La configuración proviene exclusivamente de variables `CNE_COSMOS_*`. En V1
se admite autenticación por key y la fábrica acepta un credential inyectado
para permitir una futura adopción de `DefaultAzureCredential`. La aplicación
no crea infraestructura ni ejecuta seeds al arrancar; bootstrap y seed son
scripts manuales e independientes.

Una consulta de disponibilidad es una observación temporal, no un lock ni una
reserva. Una futura operación de booking deberá volver a validar frente a
concurrencia antes de persistir.
