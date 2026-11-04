# ADR 0002: Licencia

Estado: **aceptada** (2026-11-03)

## Contexto

El proyecto se publica como herramienta abierta para proyectos eléctricos
residenciales. Podría terminar usándose comercialmente (estudios de ingeniería) y
puede integrar dependencias con otras licencias: IfcOpenShell (LGPL), jsonschema
(MIT) y, más adelante, exportación a QElectroTech (GPL).

## Decisión

**Apache License 2.0.** El texto completo está en [LICENSE](../../LICENSE).

Motivos:

- Es permisiva: permite uso comercial, modificación y redistribución sin obligar a
  publicar el código derivado.
- Incluye una **concesión explícita de patentes** y una cláusula de represalia
  limitada, algo que MIT no cubre.
- Es compatible con dependencias LGPL como IfcOpenShell y con las MIT del núcleo.
- Es la licencia que mejor equilibra apertura y adopción por terceros.

Descartadas: MIT (sin protección de patentes ni cláusula de marcas), AGPL-3.0
(obligaría a publicar también a quien ofrezca el servicio en red, lo que frena la
adopción en un estudio de ingeniería).

## Consecuencias

- No se copia código GPL de QElectroTech ni de ningún otro proyecto: el **.qet se
  genera desde cero** a partir de su formato XML. La licencia del proyecto no se
  contamina.
- La NBR 5410 es una norma protegida por ABNT: se reproducen **valores numéricos**
  con su referencia de tabla, no el texto de la norma.
- Cualquier contribución se entiende licenciada bajo Apache-2.0 (sección 5).
- El aviso de copyright y el texto de la licencia acompañan a cada distribución.
