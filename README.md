# Cne Nails AI Agent

Agente conversacional para la gestión de citas de Cne By Nails.

## Objetivo

Construir un agente capaz de:

* responder preguntas sobre servicios, precios y políticas;
* consultar disponibilidad;
* agendar citas;
* cancelar y reprogramar citas;
* mantener el contexto de la conversación;
* utilizar herramientas externas mediante MCP.

## Documentación

* Reglas del negocio: `knowledge/domain_specification.md`
* Arquitectura técnica: `docs/architecture.md`

## Estado

En desarrollo.

Actualmente el proyecto cuenta con:

* integración con Gemini mediante LangChain;
* `ChatPromptTemplate`;
* `SystemMessage` y contexto autorizado del negocio;
* historial mediante `MessagesPlaceholder`;
* few-shot prompting;
* chain conversacional construida con LCEL;
* `StrOutputParser`;
* tests unitarios del prompt;
* tests de integración con Gemini.

## Comandos rápidos

### Activar entorno virtual

```powershell
.\.venv\Scripts\Activate.ps1
```

### Verificar Python activo

```powershell
python -c "import sys; print(sys.executable)"
```

### Ejecutar tests locales

```powershell
python -m pytest
```

Los tests que requieren servicios externos, como Gemini, permanecen desactivados por defecto.

### Ejecutar todos los tests, incluyendo Gemini

```powershell
$env:RUN_INTEGRATION_TESTS = "1"
python -m pytest -v
```

Para volver a desactivar los tests de integración en la sesión actual:

```powershell
Remove-Item Env:RUN_INTEGRATION_TESTS
```

## Ejecutar aplicación

El proyecto todavía no tiene un punto de entrada de aplicación definitivo.

Este comando se añadirá cuando se implemente la capa encargada de iniciar y ejecutar el agente conversacional.
