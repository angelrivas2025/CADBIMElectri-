# CADBIMElectri

Herramienta abierta para proyectos eléctricos residenciales (planta, circuitos,
unifilar/multifilar, BIM/IFC) con motor de cálculo NBR 5410 y asistente de IA por chat.

> Estado: fases 1–4 completas (motor, exportadores, red 2.5D y asistente IA) y
> editor web de la fase 5 en versión MVP. La ocupación de conductos queda como
> «no verificable» hasta incorporar las tablas de diámetros con procedencia. Aún
> no es apta para proyectos reales.

## Principios

- La IA propone, el motor de cálculo valida.
- El proyecto es un archivo JSON versionable en Git.
- Formatos abiertos: JSON, IFC, SVG, PDF, DXF y export a QElectroTech (.qet).
- Ningún dato faltante se estima en silencio: si la tabla o el proyecto no alcanzan,
  el motor se detiene y lo dice.

## Qué calcula hoy

| Módulo | Archivo | Contenido |
| --- | --- | --- |
| Carga por circuito | `core/calc/load_schedule.py` | VA por circuito, por fase y desbalance |
| Corrientes | `core/calc/currents.py` | 1φ, 2φ y 3φ con tensión de fase o de línea |
| Previsión de cargas | `core/calc/load_forecast.py` | Mínimos de iluminación y TUG por ambiente |
| Agrupación | `core/calc/grouping.py` | División en circuitos y propuesta equilibrada |
| Protecciones | `core/calc/protections.py` | Disyuntor, DR 30 mA y DPS |
| Demanda | `core/calc/demand.py` | Demanda con factores declarados |
| Dimensionamiento | `core/calc/sizing.py` | Sección por ampacidad, caída y mínimo normativo |
| Red y ruteo | `core/net/` | Grafo 2.5D, camino mínimo, longitud y agrupamiento por circuito, ocupación por tramo |
| Materiales | `core/calc/bom.py` | Lista de cables, protecciones y tableros |
| Validación integral | `core/calc/validate.py` | Errores y avisos de todo el proyecto |
| Salidas | `exporters/` | Unifilar SVG, modelo IFC4, cuadro de cargas CSV, materiales CSV e informe PDF |
| Editor web | `api/` | Plano SVG por nivel, puntos por clic, validación, chat, deshacer y exportación |

Tablas normativas (36 a 44) como datos versionados en
`core/norms/nbr5410/data/`, con su procedencia y método de contraste en
[SOURCE.md](core/norms/nbr5410/data/SOURCE.md).

## Uso

```python
from core.model.loader import load_project
from core.calc.validate import validar_proyecto

proyecto = load_project("examples/casa-conforme.json")
informe = validar_proyecto(proyecto)
print(informe["ok"], informe["errores"])
```

La red es opcional. Si el proyecto declara `network`, el validador rutea cada
circuito por los tramos declarados, dimensiona con esa longitud y con el
agrupamiento real, y calcula el alimentador por la ruta `supply → tablero`. Sin
`network` nada cambia. El detalle queda en `informe["red"]`; la ocupación de
conductos figura como «no verificable» mientras falten las tablas de diámetros
con procedencia.

```bash
python -m pytest
```

## Salidas

```bash
python -m exporters examples/casa-conforme.json --salida salida
```

Genera `unifilar.svg` (diagrama vectorial), `modelo.ifc` (BIM IFC4),
`cuadro_cargas.csv`, `materiales.csv` e `informe.pdf` con portada, cuadro de
cargas, unifilar, lista de materiales y observaciones. PDF e IFC requieren
dependencias opcionales:

```bash
pip install ".[export]"   # PDF + IFC
pip install ".[bim]"      # solo IFC
```

El modelo IFC4 incluye jerarquía espacial (sitio, edificio, nivel), ambientes
extruidos, tablero, puntos eléctricos (luminarias, tomas, interruptores) y los
circuitos como `IfcDistributionCircuit`, con las propiedades de cálculo en
property sets `Pset_CADBIMElectri_*`. Cuando el proyecto declara `network`, cada
nodo se exporta como `IfcJunctionBox` (o el tablero correspondiente) y cada tramo
como `IfcCableCarrierSegment`, con puertos `IfcDistributionPort` y conectividad
`IfcRelConnectsPorts`; los tramos quedan asignados a sus circuitos. El archivo se
verifica con `ifcopenshell.validate` sin errores de reglas EXPRESS. Si falta
IfcOpenShell, la CLI omite el IFC y lo informa.

El mismo diagrama alimenta SVG y PDF, así que ambos formatos muestran la misma
geometría. Ningún dato faltante se completa por estimación: si falta una longitud
o una tabla, el informe lo declara como observación.

## Editor web

```bash
pip install ".[api,export]"   # o ".[dev]" dentro del repo
python -m api --proyecto examples/casa-conforme.json
# abrir http://127.0.0.1:8000
```

El editor es una sesión local de un solo usuario. Dibuja el plano por nivel,
permite colocar puntos con un clic (el formulario llama a `place_point`), muestra
errores, avisos, circuitos y alimentador del motor, conversa con el asistente,
deshace cambios y exporta SVG, PDF, CSV, materiales e IFC con vista previa del
unifilar. **Guardar** descarga el proyecto JSON y **Abrir** lo recarga después de
validarlo; la sesión no escribe el archivo original.

Para usarlo desde el teléfono en la misma red:

```bash
python -m api --proyecto casa.json --host 0.0.0.0 --port 8000
# abrir http://IP-DE-LA-COMPUTADORA:8000
```

La API no tiene autenticación: expóngala solo en una red de confianza. El chat
necesita `CADBIM_LLM_KEY` en el entorno del servidor; sin clave, el resto del
editor funciona y el chat responde 503. Ver
[ADR 0006](docs/decisiones/0006-editor-web.md).

La prueba E2E abre el editor real en Edge o Chrome (escritorio y móvil),
coloca un punto, deshace, exporta, descarga y vuelve a abrir el proyecto, y
guarda capturas en `salida/e2e/`:

```bash
pip install ".[dev,e2e]"
python -m pytest e2e -q
```

Si no hay Edge ni Chrome, `python -m playwright install chromium` habilita el
navegador de Playwright. La suite no forma parte de `pytest` por defecto porque
necesita un navegador y arranca un servidor propio en un puerto libre.

## Asistente

La IA no edita el JSON a mano ni calcula: emite llamadas a herramientas con
argumentos validados por JSON Schema. Cada llamada se aplica sobre una copia y el
proyecto resultante debe cumplir esquema y referencias; si algo falla, se
revierte, y un plan completo es atómico. Los números salen siempre del motor.

```bash
python -m ai herramientas            # contrato que se entrega al modelo
python -m ai aplicar plan.json --nuevo "Casa simple" --salida casa.json
python -m ai validar casa.json
```

Un plan es `[{"tool": "add_room", "arguments": {...}}, ...]`. Para conversar,
exporte `CADBIM_LLM_KEY` (opcionales `CADBIM_LLM_URL` y `CADBIM_LLM_MODEL`; la API
debe ser compatible con OpenAI):

```bash
python -m ai chat --proyecto casa.json --salida casa.json
```

El modelo recibe el catálogo de herramientas y cada llamada pasa por la misma
validación y rollback; la clave nunca se guarda en el proyecto. La integración
HTTP está probada con un proveedor simulado; falta la prueba con un servicio real
([ADR 0005](docs/decisiones/0005-herramientas-ia.md)).

## Documentación

- [plan.md](plan.md): plan completo y hoja de ruta.
- [core/model/project.schema.json](core/model/project.schema.json): esquema del proyecto.
- [ai/](ai): herramientas del asistente (contratos JSON Schema, agente con historial y CLI `python -m ai`).
- [api/](api): editor local (FastAPI + uvicorn) y frontend sin build en `api/web` (plano SVG, validación, chat y exportación).
- [exporters/](exporters): exportadores SVG, IFC, PDF y CSV; CLI `python -m exporters`.
- [examples/casa-conforme.json](examples/casa-conforme.json): proyecto de ejemplo que pasa la validación integral (previsión, protecciones, dimensionamiento y BOM).
- [examples/casa-red.json](examples/casa-red.json): variante con red 2.5D (esquema 0.2); rutea los circuitos, aplica agrupamiento real y calcula el alimentador por la ruta.
- [examples/casa-simple.json](examples/casa-simple.json): borrador de fase 1, deliberadamente incompleto; sirve para ver cómo el validador detecta mínimos no cumplidos.
- [docs/decisiones](docs/decisiones): ADR 0001 (stack), ADR 0002 (licencia), ADR 0003 (compatibilidad y clean room), ADR 0004 (red y ruteo 2.5D), ADR 0005 (herramientas IA) y ADR 0006 (editor web local).
- [docs/compatibilidad/electrobim.md](docs/compatibilidad/electrobim.md): matriz de paridad y protocolo de pruebas de caja negra.

## Licencia

Apache License 2.0. Ver [LICENSE](LICENSE).

## Aviso

Esta herramienta asiste el diseño; no reemplaza al responsable técnico habilitado.
Todo proyecto debe ser revisado por un profesional antes de su ejecución. Los
valores de las tablas se contrastaron con documentación técnica de fabricantes,
pero deben verificarse contra la norma oficial antes de usarse en obra.
