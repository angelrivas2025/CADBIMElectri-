# Plan del proyecto: Herramienta eléctrica + BIM asistida por IA

> Nombre provisional: **VoltaCAD** (cambiar cuando quieras).
> Estado: borrador v0.1 — para discutir y ajustar antes de escribir código.

---

## 1. Visión

Una herramienta propia, barata y abierta para hacer **proyectos eléctricos residenciales** (planta, circuitos, unifilar/multifilar, cuadros de carga, lista de materiales, memoria) con **BIM (IFC)**, donde la **IA es la interfaz principal**: el usuario conversa por chat ("proyecto eléctrico para casa de 3 dormitorios, 90 m²") y la IA propone y edita el proyecto. El **motor de cálculo determinista** valida todo; la IA nunca es la fuente de verdad de los números.

### Principios
1. **La IA propone, el motor valida.** Ningún cálculo normativo sale de un LLM.
2. **El proyecto es un archivo de datos (JSON) versionable en Git.** Todo lo demás (dibujos, PDF, IFC) se genera desde ahí.
3. **Formatos abiertos:** JSON propio, IFC, SVG, PDF, DXF, y export a QElectroTech (.qet).
4. **Flujo residencial primero.** Industrial/tableros tipo EPLAN queda para después.
5. **Todo cambio de la IA es reversible** (historial, undo, diff visual).

---

## 2. Alcance

### MVP (v0.1) — "Casa residencial de punta a punta"
- Importar plano de planta (imagen/PDF) o dibujar ambientes simples.
- Colocar puntos: tomacorrientes, interruptores, luminarias, tablero.
- Agrupar en circuitos.
- Cálculo: cargas, secciones de cable, protecciones (disyuntor/DR), caída de tensión, cuadro de cargas.
- Diagrama **unifilar** del tablero generado automáticamente.
- **Lista de materiales** y export **PDF** (planta + unifilar + cuadro de cargas).
- **Chat con IA** que crea y edita el proyecto mediante herramientas (tool use).
- Guardado en JSON + Git.

### v0.2
- Diagrama **multifilar** y export a **QElectroTech (.qet)**.
- Export/import **IFC** básico (ambientes, puntos eléctricos, tablero).
- Biblioteca de símbolos propia (IEC / ABNT).

### v0.3+
- Visor 3D del modelo IFC.
- IA que lee planos PDF y propone distribución.
- Revisión automática de normas con informe de no conformidades.
- Colaboración multiusuario (opcional), plantillas de proyecto.

### Fuera de alcance (por ahora)
- Reemplazar Revit completo (modelado arquitectónico).
- Diseño de tableros industriales 3D / PLC (EPLAN Pro Panel).
- Media/alta tensión.

---

## 3. Referencias y alternativas (investigado)

| Herramienta | Uso en este proyecto |
|---|---|
| **Woca** (web, Brasil) | Referencia funcional del flujo residencial. Copiar *funciones*, nunca código, símbolos ni textos. |
| **QElectroTech** (libre, GPL) | No es la base del editor. Se usa como **formato de salida** para esquemas (.qet es XML) y para reutilizar ideas de biblioteca. Ojo con GPL si se reutiliza código. |
| **FreeCAD BIM / Bonsai (BlenderBIM)** | Referencia y visores IFC libres. |
| **IfcOpenShell** (LGPL) | Librería para leer/escribir IFC desde Python. |
| EPLAN, ZWCAD Electrical, GstarCAD Electrical, Glodon, YJK | Comerciales. No se encontró un equivalente chino libre a EPLAN. |

---

## 4. Arquitectura

```
┌────────────────────────── Frontend (web) ──────────────────────────┐
│  Editor gráfico (planta / unifilar)  │  Panel de chat IA  │  Visor  │
└───────────────▲──────────────────────────────▲─────────────────────┘
                │ API (REST/WebSocket)         │
┌───────────────┴──────────────────────────────┴─────────────────────┐
│                        Backend (Python / FastAPI)                  │
│  ┌─────────────┐ ┌───────────────┐ ┌──────────────┐ ┌───────────┐ │
│  │ Modelo de   │ │ Motor de      │ │ Orquestador  │ │ Exporters │ │
│  │ proyecto    │ │ cálculo +     │ │ de IA (tools)│ │ PDF/SVG/  │ │
│  │ (JSON+schema)│ │ normas       │ │              │ │ IFC/QET   │ │
│  └─────────────┘ └───────────────┘ └──────────────┘ └───────────┘ │
└──────────────────────────────┬─────────────────────────────────────┘
                               │
                      Repositorio Git (proyectos)
```

### Decisiones de stack (aceptadas en ADR 0001 — 2026-11-03)
- **Núcleo/backend: Python.** Razón: IfcOpenShell, cálculo, generación de PDF/SVG y SDKs de IA son maduros.
- **Frontend: web (TypeScript + React + SVG/Konva).** Razón: editor gráfico pesado funciona mejor en web que en móvil nativo. *Alternativa:* Flutter Web si prefieres reutilizar tu stack (más trabajo en el editor de dibujo).
- **IA: API de Claude con tool use**, detrás de una interfaz propia para poder cambiar de modelo.
- **Persistencia inicial:** archivos en disco/Git. Firebase o similar solo si luego hace falta multiusuario.
- **Distribución:** primero local/web, luego empaquetar (Docker o desktop con Tauri).

> **Decisión #1 — aceptada:** Python + web. Flutter descartado. Ver [ADR 0001](docs/decisiones/0001-stack.md).

---

## 5. Modelo de datos (esquema `project.json`)

Entidades principales (versionadas con `schemaVersion`):

- `project`: metadatos, norma aplicable, tensión, sistema (monofásico/bifásico/trifásico), ubicación.
- `levels[]`: pisos/niveles con cota.
- `rooms[]`: ambientes (polígono, área, tipo → determina puntos mínimos por norma).
- `points[]`: elementos eléctricos (tipo, posición, potencia, altura, ambiente, circuito).
- `circuits[]`: id, tipo (iluminación, TUG, TUE...), carga, cable, protección, ruta.
- `panels[]`: tableros, barras, disyuntores, DR/DPS.
- `routes[]`: canalizaciones (eletrodutos) y tramos.
- `calc`: resultados cacheados + advertencias.
- `history[]`: cambios (quién: usuario/IA, qué, cuándo).

Regla: **toda la geometría y la lógica salen de este JSON**; cualquier vista es derivada.

---

## 6. Motor de cálculo y normas

### Norma inicial
- **ABNT NBR 5410** (baja tensión, Brasil) como primera implementación, porque el uso inicial es residencial en Brasil.
- Diseñado con **"paquetes de norma" intercambiables** (otros países después: IEC 60364, NEC, etc.).

### Módulos
1. **Previsión de cargas** (puntos mínimos de iluminación y tomas por ambiente, potencias por tipo).
2. **Agrupación en circuitos** (límites de carga/puntos por circuito, circuitos dedicados).
3. **Dimensionamiento de conductores:** corriente de proyecto, método de instalación, factores de agrupamiento/temperatura, sección mínima por tipo de circuito, capacidad de corriente.
4. **Caída de tensión** por circuito y total.
5. **Protecciones:** disyuntor, DR (30 mA donde aplica), DPS; coordinación básica con el conductor.
6. **Demanda y alimentación del tablero** (factores de demanda, acometida).
7. **Cuadro de cargas y balanceo de fases.**
8. **Lista de materiales** (cables, eletrodutos, cajas, dispositivos).
9. **Salidas:** cuadro de cargas, unifilar SVG, informe PDF, CSV y modelo IFC4 (`exporters/`).

### Calidad
- Cada fórmula con **pruebas unitarias** contra ejemplos resueltos de la norma/libros.
- Cada resultado guarda **referencia al artículo de la norma** aplicado.
- Revisión por un profesional habilitado antes de usar en proyectos reales.

> Las tablas y valores de la norma se cargan desde fuentes verificadas y se guardan como CSV versionados con procedencia en `core/norms/nbr5410/data/` (ver `SOURCE.md`).

---

## 7. IA vía chat

### Patrón
El usuario escribe en el chat → el LLM llama **herramientas** sobre el modelo del proyecto → el backend las ejecuta → corre el motor de cálculo → devuelve resultado y advertencias → el LLM explica y propone el siguiente paso.

### Herramientas (tools) iniciales
- `get_project_summary()`
- `add_room(name, polygon, type)` / `update_room(...)`
- `place_point(type, room, position, power, height)`
- `auto_place_points(room)` — propone puntos mínimos según norma
- `create_circuit(points, type)` / `assign_to_circuit(...)`
- `size_circuit(circuit)` — llama al motor, no calcula el LLM
- `generate_single_line(panel)` / `generate_bom()`
- `run_validation()` — lista no conformidades
- `export(format)` — pdf, ifc, qet
- `undo(n)`

### Reglas de seguridad de la IA
1. Los números siempre vienen del motor; la IA solo los comunica.
2. Cada edición de la IA queda en `history` con diff y se puede deshacer.
3. Salida estructurada validada por JSON Schema antes de aplicar.
4. Cambios grandes → **modo propuesta**: se muestra el diff y el usuario aprueba.
5. La IA indica cuando falta información (en lugar de inventarla).

### Evaluación
- Banco de **casos de prueba** (prompt → proyecto esperado) para medir errores entre versiones del modelo/prompt.
- Métricas: % de proyectos que pasan validación sin correcciones, errores por tipo.

---

## 8. BIM / IFC

- **Objetivo realista:** exportar e importar un subconjunto de IFC (ambientes, tablero, puntos, circuitos como sistemas), no modelar arquitectura.
- **Exportación IFC4 (completada en v0.2):** `exporters/ifc.py` con IfcOpenShell genera la jerarquía sitio/edificio/nivel, ambientes por extrusión, tablero, puntos eléctricos (`IfcOutlet`, `IfcLightFixture`, `IfcSwitchingDevice`), circuitos como `IfcDistributionCircuit` y propiedades de cálculo en `Pset_CADBIMElectri_*`. Verificado con `ifcopenshell.validate` sin errores.
- Lectura de un IFC arquitectónico existente para extraer ambientes y geometría base.
- Uso de **IfcOpenShell**; probar interoperabilidad con FreeCAD/Bonsai y con Revit mediante IFC.
- Ver 3D: visor web (p. ej. librería IFC para web) en v0.3.

---

## 9. Interfaz gráfica

- **Editor de planta:** lienzo 2D con zoom/pan, capas, snap, símbolos, medición, escala.
- **Vista de diagrama:** unifilar/multifilar generado automáticamente con ajustes manuales.
- **Panel de chat:** historial, adjuntos (plano), botones de acciones sugeridas, vista previa de cambios.
- **Panel de propiedades** y **tabla de circuitos** editable (las ediciones manuales pasan por las mismas validaciones).
- **Biblioteca de símbolos** SVG propios (IEC/ABNT), creados desde cero.
- Diseño responsivo; edición pesada pensada para tablet/escritorio, consulta y chat cómodos en teléfono.

---

## 10. Estructura del repositorio

```
voltacad/
├── README.md
├── plan.md                 # este documento
├── docs/
│   ├── decisiones/         # ADRs (una decisión por archivo)
│   └── normas/             # notas de normas (sin copiar contenido protegido)
├── core/                   # modelo + motor de cálculo (Python)
│   ├── model/
│   ├── calc/
│   ├── norms/nbr5410/
│   └── tests/
├── ai/                     # orquestador, tools, prompts, evaluaciones
│   ├── tools/
│   ├── prompts/
│   └── evals/
├── exporters/              # pdf, svg, ifc, qet, dxf
├── api/                    # FastAPI
├── web/                    # frontend
├── symbols/                # biblioteca de símbolos SVG
├── examples/               # proyectos de ejemplo (.json)
└── .github/workflows/      # CI
```

### Flujo de trabajo con GitHub
- Rama `main` protegida; trabajo en ramas `feat/...`, PRs pequeños.
- **Issues** y **Project board** a partir de la sección 11.
- **CI:** tests del motor, lint, validación de JSON Schema, evals de IA (manuales al inicio).
- Commits convencionales (`feat:`, `fix:`, `docs:`).
- Claves de API **nunca** en el repo (variables de entorno / secretos de GitHub).

---

## 11. Hoja de ruta

| Fase | Entregable | Criterio de "hecho" |
|---|---|---|
| **0. Fundamentos** | Repo, README, plan, licencia, CI vacío, ADRs iniciales (stack y licencia) | Repo creado y CI verde |
| **1. Modelo** | Esquema `project.json` + validación + 2 proyectos de ejemplo | Ejemplos validan contra el esquema |
| **2. Motor v0** | Previsión de cargas, circuitos, secciones, caída de tensión, protecciones (NBR 5410) | Tests contra ejemplos resueltos pasan |
| **3. Salidas v0** (completada) | Cuadro de cargas, unifilar SVG, IFC4, BOM, PDF | PDF completo e IFC válido de un proyecto de ejemplo |
| **3.5 Red y ruteo** (propuesta) | Grafo acometida→cuadro→prumada→carga, tramos 2.5D, longitudes, agrupamiento y ocupación ([ADR 0004](docs/decisiones/0004-red-y-ruteo.md)) | Casos C01–C05 del [protocolo de paridad](docs/compatibilidad/electrobim.md) y tablas por cuadro |
| **4. IA v0** | Chat + tools básicas por CLI/API | Crear una casa simple por chat sin errores de validación |
| **5. Frontend v0** | Editor de planta + chat + vista de unifilar | Flujo completo en el navegador |
| **6. Export QET + IFC** | `.qet` abre en QElectroTech; IFC con puertos y conectividad (export básico ya en fase 3) | Verificado a mano |
| **7. Pulido MVP** | Evals de IA, documentación, ejemplos, primera versión pública | Release v0.1 |

---

## 12. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Errores de cálculo con consecuencias reales | Motor determinista, tests, referencias a la norma, aviso de revisión por profesional habilitado |
| Alucinaciones de la IA | Tools + validación + modo propuesta + undo |
| Alcance enorme (BIM completo) | MVP residencial y subconjunto de IFC |
| Licencias (GPL de QElectroTech, normas ABNT protegidas) | No copiar código GPL salvo decisión consciente; generar `.qet` desde cero; tablas de norma desde fuente licenciada |
| Coste de la API de IA | Cache, prompts cortos, modelo pequeño para tareas simples |
| Editor gráfico complejo | Empezar con SVG simple y un solo tipo de vista |
| Responsabilidad técnica/legal | Descargo claro: la herramienta asiste, no reemplaza al responsable técnico |

---

## 13. Decisiones

**Resueltas:**
1. ~~Stack: Python + web vs. Flutter.~~ → Python + web ([ADR 0001](docs/decisiones/0001-stack.md)).
2. ~~Licencia del proyecto (MIT/Apache/AGPL).~~ → Apache-2.0 ([ADR 0002](docs/decisiones/0002-licencia.md)).
3. ~~Cómo se almacenarán las tablas normativas.~~ → CSV versionados con procedencia en `core/norms/nbr5410/data/` (ver `SOURCE.md`).
4. ~~Formato BIM de salida.~~ → IFC4 con IfcOpenShell; circuitos como `IfcDistributionCircuit` y propiedades en `Pset_CADBIMElectri_*`.
5. ~~Cómo igualar servicios de herramientas comerciales.~~ → Clean room, caja negra y formatos abiertos; sin descompilar binarios ajenos ([ADR 0003](docs/decisiones/0003-compatibilidad-clean-room.md), [protocolo](docs/compatibilidad/electrobim.md)).
6. ~~Cómo modelar la red y calcular longitudes.~~ → Grafo explícito y ruteo 2.5D sobre conductos declarados, con agrupamiento y ocupación ([ADR 0004](docs/decisiones/0004-red-y-ruteo.md)).

**Pendientes:**
7. País/norma inicial confirmada: NBR 5410 (Brasil)? ¿Soporte inicial para otra?
8. ¿Proyecto abierto al público o privado al inicio?
9. Nombre definitivo.

---

## 14. Primeros pasos (cuando llegues a la computadora)

1. Crear repo en GitHub (privado al inicio) y subir este `plan.md` y un `README.md`.
2. Abrir issues para Fase 0 y Fase 1.
3. Decidir las preguntas de la sección 13 (una ADR por decisión).
4. Definir 2 proyectos residenciales de ejemplo reales (planta + qué quieres que salga) para usarlos como casos de prueba de motor e IA.
