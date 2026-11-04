# Tablas de la NBR 5410

Esta carpeta contiene la capacidad de conducción (tablas 36 a 39) y los factores de
corrección (tablas 40 a 44) como datos versionados.

Los CSV de esta carpeta (`ampacidad_*.csv`) **no se editan a mano**: se generan con
`build_tables.py` a partir del consolidado verificado en `source/`. La procedencia y el
método de contraste están en [SOURCE.md](SOURCE.md).

## Contenido

| Archivo | Tabla NBR | Contenido |
| --- | --- | --- |
| `ampacidad_cobre_pvc.csv` | 36 y 38 | Cobre, PVC 70 °C, métodos A1–D y E–G |
| `ampacidad_cobre_xlpe.csv` | 37 y 39 | Cobre, XLPE/EPR 90 °C, métodos A1–D y E–G |
| `ampacidad_aluminio_pvc.csv` | 36 y 38 | Aluminio, PVC 70 °C, métodos A1–D y E–G |
| `ampacidad_aluminio_xlpe.csv` | 37 y 39 | Aluminio, XLPE/EPR 90 °C, métodos A1–D y E–G |
| `factores_temperatura.csv` | 40 | Temperatura ambiente (aire) y del suelo, por aislación |
| `factores_resistividad.csv` | 41 | Resistividad térmica del suelo, en ducto y enterrado directo |
| `factores_agrupamiento.csv` | 42 | Circuitos agrupados en una camada, por disposición |
| `factores_multicamada.csv` | 43 | Varias camadas de circuitos |
| `factores_enterrado.csv` | 44 | Circuitos enterrados según separación |

Formato largo, una fila por valor:

```
seccion_mm2,metodo,n_conductores,corriente_a,tabla_nbr,material,aislacion
2.5,A1,3,24,36,Cu,PVC
```

`metodo` conserva la variante cuando la norma la distingue: `F_JUSTAPOSTO`,
`F_TRIFOLIO`, `G_HORIZONTAL` y `G_VERTICAL`. El motor no elige variante por su
cuenta: `capacidad()` y `seleccionar_seccion()` la exigen para F y G.

`corriente_a` es el valor tabulado (sin factores de corrección). La corrección por
temperatura, agrupamiento, resistividad del terreno y profundidad se aplica encima,
con `capacidad(..., factor=...)` y el módulo `corrections.py`.

Los `factores_*.csv` se generan con `build_factors.py` desde el mismo consolidado y
se leen con `corrections.py`. Ninguno interpola: si el valor pedido cae entre dos
filas se usa la más desfavorable; fuera de tabla se lanza `FactorIndefinido`.

## Regenerar

```bash
python core/norms/nbr5410/data/build_tables.py
python core/norms/nbr5410/data/build_factors.py
python -m pytest core/tests/test_ampacity.py core/tests/test_corrections.py
```

`validar_tabla()` revisa errores típicos de transcripción (valores que no crecen con la
sección, 3 conductores mayor que 2, secciones no comerciales). Atrapó justamente el
defecto de desplazamiento de filas del catálogo Nexans durante la verificación.
`validar_factores()` hace lo propio con las tablas 40 a 44: los factores deben empeorar
al agravarse la temperatura, la resistividad, el agrupamiento o la separación.

## Advertencia

La NBR 5410 es una norma protegida por ABNT. Aquí se reproducen **valores numéricos**
con su referencia, no el texto de la norma. Antes de usar el motor en un proyecto real,
un profesional habilitado debe verificar los valores contra su copia oficial.
