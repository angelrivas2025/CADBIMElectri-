# ADR 0001: Stack tecnológico

Estado: **aceptada** (2026-11-03)

## Contexto

El proyecto necesita un motor de cálculo determinista, lectura/escritura de IFC,
generación de planos y documentos (SVG/PDF/DXF), y un editor gráfico donde el
usuario vea lo que la IA propone. El uso inicial es residencial en Brasil y el
equipo es pequeño: la prioridad es reducir riesgo técnico, no optimizar por
tecnología.

## Decisión

- **Núcleo y backend en Python 3.10+.** El cálculo, la validación contra la norma,
  el IFC (IfcOpenShell), la exportación y los SDK de IA son maduros en Python. El
  núcleo se mantiene **sin dependencias de red** y con tests deterministas.
- **API con FastAPI** cuando haga falta exponer el motor.
- **Frontend web con TypeScript + React + SVG/Konva.** El editor gráfico es la
  parte más pesada y funciona mejor en web que en móvil nativo.
- **Flutter Web descartado** como base: reutilizar experiencia previa no compensa
  el trabajo extra en el editor gráfico.

## Consecuencias

- Dos lenguajes (Python + TypeScript) y un contrato de API que versionar.
- El formato de proyecto JSON es la frontera estable entre el núcleo y el frontend:
  todo lo que la IA o el usuario edita pasa por el validador del núcleo.
- El núcleo puede probarse y usarse por CLI sin el frontend.
- Si más adelante se necesita escritorio, se envuelve el frontend web (Tauri o
  similar) sin reescribir el motor.
