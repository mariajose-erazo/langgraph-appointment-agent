# Arquitectura — Cne Nails AI Agent

## 1. Objetivo de la arquitectura

Este documento describe la arquitectura técnica planeada antes de comenzar
la implementación del agente.

## 2. Principios

- Separar las reglas del negocio de la inteligencia artificial.
- No permitir que el LLM decida reglas deterministas de agenda.
- Separar datos operacionales de conocimiento semántico.
- Confirmar antes de ejecutar acciones que modifiquen datos.
- Mantener los componentes reemplazables.

## 3. Componentes previstos

### LLM
Gemini inicialmente.

### LangChain
Integraciones con LLM, prompts, structured output y RAG.

### LangGraph
Orquestación del agente, estado de conversación y decisiones.

### ChromaDB
Base vectorial para conocimiento del negocio.

### SQLite
Base operacional para citas, profesionales, horarios y bloqueos.

### FastMCP
Exposición de herramientas del sistema mediante MCP.

## 4. Separación de información

### SQLite

- citas;
- profesionales;
- horarios;
- bloqueos;
- estados de citas.

### ChromaDB

- servicios;
- precios;
- políticas;
- preguntas frecuentes.

### Estado de LangGraph

- intención actual;
- servicio seleccionado;
- profesional;
- fecha;
- hora;
- confirmación pendiente;
- contexto de conversación.

## 5. Flujo general

Usuario
→ LangGraph
→ decisión
→ RAG o herramienta
→ resultado
→ respuesta al usuario

## 6. Decisiones pendientes

Se documentarán durante el desarrollo.