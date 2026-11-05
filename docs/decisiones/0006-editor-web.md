# ADR 0006: Editor web local y API de sesión

Fecha: 2026-11-04
Estado: aceptado; implementado el MVP local, sin autenticación ni multiusuario

## Contexto

El motor, los exportadores y el asistente ya funcionan por línea de comandos,
pero dibujar el plano y revisar el cumplimiento exigía editar JSON o abrir
archivos generados. Falta una interfaz visual que reutilice exactamente las
mismas reglas y que también sea usable desde el teléfono en la red local.

## Decisión

1. **Backend FastAPI + uvicorn, con una sola sesión en memoria.** `python -m api`
   carga un proyecto (o crea uno vacío con `--nuevo`), construye un `Agente` y
   lo protege con un `threading.Lock`. El servidor escucha en `127.0.0.1:8000`
   por defecto. Las dependencias viven en el extra `[api]`; los tests usan
   `httpx` y `fastapi.testclient`.
2. **La API repite las reglas del CLI, no las relaja.** Cada llamada a
   herramienta valida su JSON Schema, se aplica sobre una copia, exige esquema y
   referencias válidas y se revierte si falla. Los números de validación salen de
   `core.calc.validate`; el navegador nunca calcula secciones ni caídas.
3. **Endpoints mínimos.**

   | Método y ruta | Efecto |
   | --- | --- |
   | `GET /api/estado` | Proyecto, resumen, validación y si se puede deshacer |
   | `GET /api/proyecto` | Descarga el JSON actual como `proyecto.json` |
   | `POST /api/proyecto` | Abre un proyecto validado y reinicia el historial |
   | `GET /api/herramientas` | Catálogo que también recibe el modelo |
   | `POST /api/herramienta` | Aplica una llamada y devuelve el estado completo |
   | `POST /api/deshacer` | Revierte las últimas `n` ediciones |
   | `POST /api/validar` | Ejecuta el motor y devuelve el informe compacto |
   | `POST /api/chat` | Conversa con el proveedor; 503 si falta la clave |
   | `POST /api/exportar` | Genera SVG, PDF, CSV, materiales e IFC en `salida/` |

   `/estatico` sirve el frontend y `/salida` los archivos exportados.
4. **El frontend es HTML, CSS y JavaScript sin build.** Es un desvío deliberado
   del MVP respecto de [ADR 0001](0001-stack.md), que preveía TypeScript + React:
   el plano actual no justifica un bundler, y el navegador consume los mismos
   endpoints que el CLI. Se migrará cuando el editor necesite estado complejo o
   edición gráfica avanzada. Dibuja el plano como SVG
   a partir de los polígonos del proyecto, con filtro por nivel, etiquetas de
   área y símbolos por tipo de punto. Un clic dentro del ambiente elegido
   prepara un punto y el formulario lo confirma mediante `place_point`; el
   formulario nunca escribe el JSON por su cuenta.
5. **El panel de cumplimiento es el del motor.** Muestra errores, avisos,
   circuitos dimensionados, alimentador y unifilar. La exportación devuelve
   enlaces a los archivos y advierte si el proyecto todavía tiene errores.
6. **Guardar es explícito.** La sesión vive en memoria: el botón Guardar descarga
   el JSON y Abrir lo vuelve a cargar después de validarlo. No hay autosave ni
   escritura silenciosa sobre el archivo original.
7. **El chat es opcional.** Si `CADBIM_LLM_KEY` no está definida, el editor, la
   validación y la exportación funcionan igual; `/api/chat` responde 503 con una
   explicación. La clave solo se lee del entorno y nunca se envía al navegador.
8. **Seguridad acotada a una red de confianza.** No hay autenticación: la API
   puede modificar el proyecto y gastar tokens del proveedor. Se usa en
   `127.0.0.1`; para el teléfono se expone con `--host 0.0.0.0` solo en una red
   local de confianza, y la CLI lo advierte. El agente de la API además limita la
   herramienta `export` (también cuando la invoca el chat) a la carpeta de salida
   servida, para que una ruta arbitraria no escriba fuera de ella.

## Consecuencias

- El flujo completo (plano, puntos, validación, chat, deshacer, exportación y
  guardar/abrir) queda disponible en el navegador y reutiliza el motor.
- Sigue siendo un MVP de un solo usuario: no hay autenticación, sesiones
  múltiples, autosave ni edición colaborativa. La API se prueba con
  `fastapi.testclient` y el flujo real del editor con Playwright en
  `e2e/test_editor.py` (escritorio y móvil): colocar y deshacer un punto,
  validar, exportar y servir los archivos, descargar y reabrir el proyecto, y
  comprobar que no hay errores de página ni desbordes en pantalla pequeña. La
  suite vive fuera de `testpaths` porque requiere un navegador instalado.
- Los archivos exportados no se revierten con Deshacer: son artefactos de salida,
  no parte del proyecto.
