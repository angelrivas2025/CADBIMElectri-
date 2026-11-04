# ADR 0005: Contrato de herramientas del asistente IA

Fecha: 2026-11-04
Estado: aceptado; herramientas y chat implementados, falta prueba con un
proveedor real

## Contexto

El producto propone que la IA sea la interfaz: el usuario conversa y la IA edita
el proyecto. El riesgo es doble: que el modelo invente números eléctricos o que
deje el proyecto en un estado inválido. La regla del proyecto ya es «la IA
propone, el motor de cálculo valida»; falta definir cómo se aplica una propuesta.

## Decisión

1. **La IA no edita JSON a mano ni calcula.** Emite **llamadas a herramientas**
   con argumentos estructurados. Cada herramienta declara un JSON Schema cerrado
   (`additionalProperties: false`); una llamada que no lo cumple se rechaza
   antes de tocar el proyecto.
2. **Un agente en memoria aplica las llamadas.** `ai.Agente` guarda una copia
   antes de cada llamada, ejecuta la herramienta y luego exige que el proyecto
   cumpla el esquema y las referencias (`core.model.loader`). Si algo falla,
   revierte la llamada completa.
3. **Los planes son atómicos.** `Agente.aplicar_plan([...])` restaura el proyecto
   y el historial si cualquier llamada del plan falla, de modo que un plan a
   medio aplicar nunca se guarda.
4. **Deshacer es explícito.** `Agente.deshacer(n)` restaura las copias de las
   últimas `n` llamadas y recorta el historial en el mismo orden. Cada edición
   (las herramientas de solo lectura no cuentan) se registra además en
   `project.history` con autor `ia` y la llamada aplicada.
5. **Los números vienen del motor.** `run_validation` llama a
   `core.calc.validate` y devuelve conformidad, avisos, corrientes, secciones y
   caídas; el modelo solo los comunica. `export` reutiliza los exportadores.
6. **Contrato estable.** `python -m ai herramientas --json` publica el catálogo
   (nombre, descripción y parámetros) que se entrega al modelo. Un plan es
   `[{"tool": "...", "arguments": {...}}, ...]`; `python -m ai aplicar` lo
   aplica y valida, y `python -m ai validar` corre el motor sobre un proyecto.
7. **Chat con proveedor compatible OpenAI.** `python -m ai chat` lee
   `CADBIM_LLM_KEY` (y opcionalmente `CADBIM_LLM_URL` y `CADBIM_LLM_MODEL`),
   envía el prompt de sistema (`ai/prompts/sistema.md`) y el catálogo, aplica las
   llamadas con el mismo agente y devuelve los resultados al modelo. La clave
   nunca se persiste. Un límite de turnos evita bucles de herramientas.

## Herramientas v0

| Herramienta | Efecto |
| --- | --- |
| `get_project_summary` | Resumen de solo lectura (conteos, circuitos, red) |
| `add_level` / `add_room` / `update_room` | Estructura y geometría de ambientes |
| `add_panel` / `create_circuit` | Tableros y circuitos declarados |
| `place_point` / `assign_to_circuit` | Puntos eléctricos y su circuito |
| `set_project` / `set_supply` | Tensión, sistema, ubicación y datos de suministro |
| `run_validation` | Ejecuta el motor y devuelve el resultado |
| `export` | SVG, PDF, CSV, IFC o todos en una carpeta |

No se incluyen todavía `auto_place_points`, `size_circuit` ni `undo` como
herramienta: las dos primeras requieren reglas normativas explícitas y la
tercera es una operación de sesión (`Agente.deshacer`). El formato `qet` no está
disponible hasta la fase 6.

## Consecuencias

- El núcleo de la fase 4 (contratos, aplicación segura, historial, CLI y chat)
  queda verificable con un proveedor simulado, sin depender de una clave de API.
- Falta probar el chat contra un servicio real y escribir evals de conversación;
  el contrato de herramientas ya es el que recibe el modelo.
- Los efectos externos del plan (archivos exportados) no se revierten al
  deshacer: el rollback cubre el proyecto y el historial.
- Las reglas de negocio siguen en `core/`; las herramientas solo validan forma
  y referencias, no reemplazan la validación normativa.
