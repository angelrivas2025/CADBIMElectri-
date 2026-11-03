# Tablas de la NBR 5410

Esta carpeta contiene las tablas normativas **como datos**. Están **vacías a propósito**:
la NBR 5410 es una norma protegida por ABNT y un valor mal transcrito es un riesgo real.

## Cómo llenar `ampacidad_cobre_pvc.csv`
Fuente: Tabla 36 de la NBR 5410:2004 (cobre, aislación PVC 70 °C, métodos A1, A2, B1, B2, C y D),
desde tu copia de la norma o desde el catálogo/guía de un fabricante que la reproduzca.

Una fila por valor, columnas: `seccion_mm2,metodo,n_conductores,corriente_a`

Ejemplo de formato (valores inventados, NO usar): `2.5,B1,2,99`

Después de llenarla, ejecuta `pytest`: el validador revisa errores típicos de transcripción
(valores que no crecen con la sección, 3 conductores mayor que 2, etc.).
Un segundo profesional debería verificar cada valor contra la norma antes de usarla en un proyecto real.
