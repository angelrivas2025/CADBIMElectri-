# ADR 0004: Modelo de red y ruteo 2.5D

Estado: **aceptada** (2026-11-04)

## Contexto

Hoy el proyecto declara una longitud por circuito (`circuits[].length_m`) y el
motor la usa para la caída de tensión. Esa longitud no se verifica: no hay
trazado, no se sabe cuántos circuitos comparten una canalización y no se puede
comprobar la ocupación de los conductos.

La referencia funcional (electroBIM) modela la instalación como un árbol
acometida → cuadros → prumadas → cargas y rutea los cables por los conductos
dibujados en el modelo, calculando longitudes, agrupamiento y ocupación. Para
igualar ese servicio sin depender de Revit ni de un binario ajeno, hace falta un
modelo de red propio, explícito y versionable en el JSON.

## Decisión

### 1. La red es un grafo explícito y opcional

Se agrega `network` al proyecto, con `nodes` y `segments`. Sustituye al
placeholder `routes`, que estaba vacío y sin uso. Si `network` no está presente,
el comportamiento actual no cambia (longitud declarada, sin verificación de
trazado).

```json
"network": {
  "nodes": [
    {"id": "SUP", "type": "supply", "level": "N0", "position": [0.0, 0.0], "height": 1.2},
    {"id": "QD1", "type": "panel", "ref": "QD1", "level": "N0", "position": [1.2, 3.0], "height": 1.5},
    {"id": "CX1", "type": "junction", "level": "N0", "position": [4.0, 3.0], "height": 2.4},
    {"id": "CARGA-C2", "type": "load", "ref": "C2", "level": "N0", "position": [6.5, 4.2], "height": 0.3}
  ],
  "segments": [
    {"id": "T01", "from": "SUP", "to": "QD1", "kind": "conduit", "trade_size": "32"},
    {"id": "T02", "from": "QD1", "to": "CX1", "kind": "conduit", "trade_size": "25"},
    {"id": "T03", "from": "CX1", "to": "CARGA-C2", "kind": "conduit", "trade_size": "20"}
  ]
}
```

Reglas del modelo:

- Nodos: `supply` (punto de entrega), `panel` (tablero, `ref` al panel),
  `junction` (caja o punto de paso) y `load` (carga terminal, `ref` al circuito).
- Un `supply` por proyecto en esta fase; varios tableros y cargas.
- Cada circuito con red tiene **exactamente un nodo `load`**. La carga representa
  el terminal del circuito (el punto más desfavorable para la caída); el ruteo
  punto por punto queda fuera de alcance.
- Segmentos: `kind` ∈ `conduit` (eletroduto), `tray` (eletrocalha) o `riser`
  (prumada). `trade_size` es la designación comercial (`20`, `25`, `32`, `40`…)
  y debe existir en la tabla versionada; no se aceptan diámetros libres.
- Un segmento que une nodos de niveles distintos debe ser `riser`. Los demás
  segmentos unen nodos del mismo nivel.
- Posiciones en metros: `position: [x, y]` y `height: z`. Los `waypoints`
  opcionales son `[x, y, z]` y permiten modelar quiebres; sin waypoints, el
  tramo es recto entre extremos.

### 2. Alcance 2.5D: rutear sobre conductos declarados

El motor **no diseña la trayectoria de los conductos**: calcula el recorrido de
los cables por la red de segmentos ya declarada. Es el mismo principio que la
referencia (allí también se rutea sobre conductos dibujados). La generación
automática de trazados y el ruteo 3D con colisiones quedan fuera de esta fase.

### 3. Algoritmo determinista

- Grafo no dirigido, peso = longitud 3D del segmento (horizontal + diferencia de
  altura; con waypoints, suma de tramos).
- Ruta de cada circuito: camino mínimo entre el nodo del tablero y su nodo
  `load` (Dijkstra).
- Desempate por `id` de segmento para que el resultado sea reproducible.
- Sin camino, grafo desconectado o referencias rotas: **error**, nunca se cae a
  la longitud declarada en silencio.

### 4. Longitud y agrupamiento por circuito

- `length_m` para dimensionar = longitud de la ruta del circuito.
- `n_circuitos_agrupados` = máximo número de circuitos distintos que comparten
  un segmento a lo largo de su ruta (criterio conservador).
- Si el circuito declara `length_m` y hay red, manda la red; una diferencia
  mayor al 5 % genera aviso con ambos valores.
- El agrupamiento calculado reemplaza el valor global de opciones para ese
  circuito; el factor se aplica con la tabla de la norma.

### 5. Ocupación de conductos

- Área ocupada = suma de las secciones exteriores de todos los conductores de
  todos los circuitos que pasan por el segmento.
- Diámetros exteriores de cable, diámetros interiores de conducto y límite de
  ocupación se cargan desde tablas versionadas con procedencia en
  `core/norms/nbr5410/data/` (política del ADR 0002). No se hardcodean valores.
- Si falta la tabla o el `trade_size`, la etapa **no puede verificar**: se
  reporta como error de datos, no como cumple. Cuando el segmento excede el
  límite se informa el tramo, los circuitos y la siguiente medida comercial.

### 6. Integración con el motor

- `core/net/`: `graph.py` (construcción y validación), `routing.py` (Dijkstra),
  `occupancy.py` (ocupación), `report.py` (resultados por circuito y tramo) y
  `analizar_red(project)` como entrada.
- `core/calc/validate.py`: etapa `red` cuando hay `network`; entrega longitudes
  y agrupamiento a `dimensionar_proyecto`.
- Alimentador: la ruta `SUP → tablero` reemplaza `supply.feeder_length_m` cuando
  hay red; una diferencia con el valor declarado genera aviso.
- `core/calc/sizing.py`: acepta valores por circuito; sin red, comportamiento
  actual.
- `core/calc/bom.py`: longitudes de cable desde el ruteo cuando hay red.
- Exportadores: tablas por cuadro y por tramo en una etapa posterior; el
  informe del validador ya expone los avisos.
- IFC: nodos y segmentos se mapean a elementos y puertos en la fase 6.

### 7. Dominio y reutilización para hidráulica

`core/net` trabaja sobre nodos y segmentos abstractos. La semántica
(`supply`/`panel`/`load`) es eléctrica en esta fase; hidráulica extenderá el
enum y las reglas de dimensionamiento sin tocar el ruteo. Esa separación evita
reescribir el motor cuando se agregue água/esgoto.

### 8. Versionado

- `network` es opcional; `routes` se elimina del esquema y de los ejemplos
  (estaba vacío).
- `schemaVersion` pasa a `0.2` cuando se implemente el campo.

## Alternativas descartadas

- **Mantener solo `length_m` declarada:** simple, pero no verifica trazado,
  agrupamiento ni ocupación; es el problema que motiva la fase.
- **Generar automáticamente la trayectoria de los conductos:** mucho más
  complejo y fuera del comportamiento de referencia; queda para una fase
  posterior.
- **Ruteo 3D con colisiones:** aporta poco al MVP residencial; 2.5D cubre
  longitudes y ocupación.
- **Ruteo por punto en vez de por circuito:** más preciso, pero exige conductos
  hasta cada punto y complica el modelo; se difiere.
- **Persistir resultados en `calc`:** el proyecto debe seguir siendo la fuente
  de verdad; los resultados se calculan al validar y no se escriben de vuelta.

## Consecuencias

- El esquema crece y hay que mantener coherencia entre puntos, circuitos y red;
  el cargador validará referencias y niveles.
- Los ejemplos actuales se simplifican al quitar `routes`; se agrega un ejemplo
  nuevo con red (`examples/casa-red.json`) sin alterar los existentes.
- Aparecen tests de grafo, ruteo, agrupamiento y ocupación; los casos C01–C05
  del [protocolo de paridad](../compatibilidad/electrobim.md) pasan a ser
  aceptación.
- Es la base compartida para hidráulica: el mismo grafo y ruteo servirán para
  água, esgoto y pluviais.
- Sin red, nada cambia: los proyectos actuales siguen validando igual.

## Criterio de cierre

- Esquema y cargador validan nodos, segmentos, referencias y niveles.
- `core/net` determinista, con tests unitarios y casos C01–C05.
- Un ejemplo con red que incluya un tramo compartido por dos circuitos.
- `validate` informa longitud y agrupamiento por circuito y ocupación por tramo.
- El dimensionamiento usa los valores de red y el BOM refleja las longitudes.
- Suite completa en verde y documentación actualizada.
