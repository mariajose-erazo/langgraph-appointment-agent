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