# Procedencia de las tablas de ampacidad

Los valores de `ampacidad_*.csv` provienen de las tablas 36 a 39 de la
**ABNT NBR 5410:2004**, tal como las reproducen documentos técnicos de fabricantes
brasileños de conductores. Aquí se guardan **solo los valores numéricos** con su
referencia de tabla; no se reproduce el texto de la norma.

## Fuentes primarias descargadas

| Fuente | Uso |
| --- | --- |
| Prysmian — *Guia técnico de instalações elétricas de baixa tensão* (`prysmian_bt.pdf`) | Transcripción base de las tablas 36 a 39 |
| Cobrecom — catálogo de cabos de baja tensión (`cobrecom_catalogo.pdf`) | Contraste independiente |
| Nexans — catálogo de baja tensión (`nexans_bt.pdf`) | Segundo contraste (descartado para transcripción, ver abajo) |

Extracción con `pdftotext -raw` para preservar el orden de fila; la extracción
`-layout` desalineaba las etiquetas de sección respecto de sus valores.

## Contraste entre fuentes

- **Cobrecom**: coincidencia del 100 % con Prysmian en las secciones comparadas.
- **Nexans**: dos defectos propios del catálogo, no de la norma:
  - páginas 44 y 46: las columnas A2–D están desplazadas una fila respecto de las
    etiquetas de sección;
  - 95 mm² XLPE: el valor 269 A aparece impreso como 29 A.
  Por eso Nexans no se usó para transcribir fila por fila; sirvió para confirmar el
  defecto y validar el criterio del validador.
- **A1 ≠ B2**: se comprobó que las columnas no son idénticas en las 24 secciones de
  cobre (y 16 de aluminio). Ejemplo PVC 25 mm², 3 conductores cargados: A1 = 73 A,
  B2 = 80 A, C = 96 A, D = 86 A.

## Consolidado

`source/tabelas_36_39_consolidadas.csv` (160 filas = 4 tablas × (24 secciones de cobre
+ 16 de aluminio)). Formato semicolon-separado con una fila por sección y una columna
por método y número de conductores cargados:

- tablas 36 (PVC) y 37 (XLPE) → A1, A2, B1, B2, C, D;
- tablas 38 (PVC) y 39 (XLPE) → E, F (justaposto y trifólio) y G (horizontal y vertical).

`build_tables.py` convierte ese consolidado al formato largo que consume
`ampacity.py` y conserva `tabla_nbr`, `material` y `aislacion` en cada fila.

## Celdas omitidas a propósito

En el bloque de aluminio de la tabla 38 (PVC, métodos E/F/G), la fila de 630 mm² de
las columnas F justaposto y G horizontal/vertical se perdió durante la extracción del
PDF: el texto extraído repite los valores de 500 mm². Se comprobó contra las filas
vecinas (400, 800 y 1000), que sí crecen de forma coherente, y contra el bloque de
cobre, así que el valor correcto no se puede recuperar de esta fuente.

Esas tres celdas quedan **vacías** en el consolidado. `capacidad()` y
`seleccionar_seccion()` lanzan `TablaIncompleta` en vez de devolver un valor dudoso.
Con el validador actual estos duplicados habrían pasado inadvertidos porque el valor
repetido no rompe la monotonía; se detectaron con una búsqueda de valores idénticos
entre secciones consecutivas ≥ 16 mm².

En la tabla 41 (resistividad del suelo), la fila de 3 K·m/W tenía invertidas las
columnas: el origen las lee como 0,96 en ducto y 0,90 enterrado directo, cuando la
tabla de Prysmian dice 0,90 en ducto y 0,96 enterrado directo. Corregido en el
consolidado. Un factor invertido no rompe la monotonía, así que tampoco lo habría
detectado el validador: se encontró contrastando fila por fila con el PDF.

## Factores de corrección (tablas 40 a 44)

`source/fatores_40_44_origem.csv` (100 filas) reúne los factores de temperatura del
aire y del suelo (40), resistividad térmica del suelo (41), agrupamiento en una camada
(42), multicamada (43) y circuitos enterrados (44). `build_factors.py` lo reparte en
los cinco `factores_*.csv`.

Las tablas 42 a 44 no distinguen aislación: sus factores dependen solo de la
disposición y del número de circuitos. En la tabla 41 las dos columnas del origen no
son PVC y XLPE sino *en ducto enterrado* y *directamente enterrado*; el generador las
etiqueta con `modo` para no repetir la confusión.

## Verificación

```bash
python core/norms/nbr5410/data/build_tables.py
python -m pytest core/tests/test_ampacity.py
```

El validador comprueba que la capacidad crezca con la sección, que 3 conductores no
superen a 2 y que las secciones sean comerciales. Fue lo que detectó el defecto de
Nexans. Un profesional habilitado debe contrastar los valores con la norma oficial
antes de usarlos en un proyecto real.
