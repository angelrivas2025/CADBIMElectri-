# CADBIMElectri

Herramienta abierta para proyectos eléctricos residenciales (planta, circuitos,
unifilar/multifilar, BIM/IFC) con motor de cálculo NBR 5410 y asistente de IA por chat.

> Estado: fase 1–3 (modelo de datos, motor de cálculo y salidas). Aún no es apta
> para proyectos reales.

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
| Materiales | `core/calc/bom.py` | Lista de cables, protecciones y tableros |
| Validación integral | `core/calc/validate.py` | Errores y avisos de todo el proyecto |
| Salidas | `exporters/` | Unifilar SVG, cuadro de cargas CSV e informe PDF |

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

```bash
python -m pytest
```

## Salidas

```bash
python -m exporters examples/casa-conforme.json --salida salida
```

Genera `unifilar.svg` (diagrama vectorial), `cuadro_cargas.csv` y `informe.pdf`
con portada, cuadro de cargas, unifilar, lista de materiales y observaciones.
El PDF requiere la dependencia opcional:

```bash
pip install ".[export]"
```

El mismo diagrama alimenta SVG y PDF, así que ambos formatos muestran la misma
geometría. Ningún dato faltante se completa por estimación: si falta una longitud
o una tabla, el informe lo declara como observación.

## Documentación

- [plan.md](plan.md): plan completo y hoja de ruta.
- [core/model/project.schema.json](core/model/project.schema.json): esquema del proyecto.
- [exporters/](exporters): exportadores SVG, PDF y CSV; CLI `python -m exporters`.
- [examples/casa-conforme.json](examples/casa-conforme.json): proyecto de ejemplo que pasa la validación integral (previsión, protecciones, dimensionamiento y BOM).
- [examples/casa-simple.json](examples/casa-simple.json): borrador de fase 1, deliberadamente incompleto; sirve para ver cómo el validador detecta mínimos no cumplidos.
- [docs/decisiones](docs/decisiones): ADR 0001 (stack) y ADR 0002 (licencia).

## Licencia

Apache License 2.0. Ver [LICENSE](LICENSE).

## Aviso

Esta herramienta asiste el diseño; no reemplaza al responsable técnico habilitado.
Todo proyecto debe ser revisado por un profesional antes de su ejecución. Los
valores de las tablas se contrastaron con documentación técnica de fabricantes,
pero deben verificarse contra la norma oficial antes de usarse en obra.
