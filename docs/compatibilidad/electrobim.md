# Protocolo de paridad funcional con electroBIM

Documento de ingeniería. No es asesoría legal. La política aplicable está en el
[ADR 0003](../decisiones/0003-compatibilidad-clean-room.md).

## Fuente y alcance

La referencia es el folleto público **«ElectroBIM: mais inteligência e integração
para projetos elétricos em BIM»** (Electro Graphics / Hiper Energy, serie 2026).
Describe un plugin de Revit 2020–2026 para gestionar redes eléctricas en BIM.

La página de **gStarBIM** enlazada en la conversación corresponde a otro producto
(BIM de arquitectura) y no aporta funciones eléctricas; su prueba de 30 días no
implica que electroBIM ofrezca las mismas condiciones. Cualquier evaluación debe
confirmarse con el proveedor antes de usarla.

Alcance: igualar **servicios y comportamiento**, no interfaz, textos ni código.
Quedan fuera el ruteo 3D completo y la integración como plugin de Revit; nuestro
puente BIM es IFC.

## Matriz de paridad

| Servicio | electroBIM (según folleto) | CADBIMElectri hoy | Objetivo |
| --- | --- | --- | --- |
| Red en árbol | Acometida → cuadros → prumadas → cargas | Un tablero y circuitos planos | Fase 3.5 |
| Subcuadros y prumadas | Sí | No | Fase 3.5 |
| Asociación red ↔ objetos del modelo | Sí, por símbolos | Parcial (puntos y circuitos) | Fase 6 |
| Ruteo automático de cables | Por conductos, camino más corto | No; longitud declarada | Fase 3.5 (2.5D) |
| Longitudes de cable | Calculadas del ruteo | Declaradas por circuito | Fase 3.5 |
| Agrupamiento por proximidad | Actualizado al rutear | Declarado en el proyecto | Fase 3.5 |
| Ocupación de conductos | Verificación y vista previa | No | Fase 3.5 |
| Cálculo y dimensionamiento | Delega en Ampère o red reducida | Propio, NBR 5410 | Ya disponible |
| Optimización por caída de tensión | Sí | Sí, por circuito | Ya disponible |
| Tablas por cuadro | Sí, personalizables | Parcial (global) | Fase 3.5 |
| Tabla general de cables | Sí, por tipo de red | Parcial (BOM) | Fase 3.5 |
| Redes auxiliares | Datos, EVAC/incendio, TV/SAT | No | Post-MVP |
| Sincronización con cálculo externo | Ampère | No aplica (motor propio) | — |
| BIM | Revit propietario | IFC4 abierto | Fase 6 |

## Protocolo de caja negra

### Requisitos previos

1. Acceso legítimo al producto (licencia o evaluación) y lectura del EULA.
2. Si el EULA prohíbe instalar el producto en un entorno de análisis, no se
   instala: se trabaja solo con documentación y con archivos de ejemplo que el
   usuario ya posea.
3. Proyecto propio, sin datos de clientes. Nada de archivos del proveedor se
   redistribuye.
4. Dos roles separados: quien escribe especificación y tests **no implementa**;
   quien implementa trabaja solo desde la especificación.

### Registro de casos

Cada caso se documenta con esta plantilla:

```
ID:            C01
Objetivo:      red en árbol con subcuadro y prumada
Procedencia:   folleto electroBIM, sección «Gestão da Rede Elétrica»
Precondición:  proyecto de prueba propio con un tablero y dos cargas
Entradas:      potencias, longitudes y conductos declarados
Acciones:      crear cuadro, prumada y cargas; guardar
Salidas:       árbol, longitudes, tabla de cuadro, archivos exportados
Tolerancia:    longitudes ±0,1 m; secciones y corrientes exactas
Evidencia:     CSV/IFC/PDF generados por la herramienta
Fecha/versión: 2026-11-04 / versión observada
```

### Catálogo mínimo de casos

| ID | Caso | Qué se observa |
| --- | --- | --- |
| C01 | Red con acometida, tablero, prumada y subcuadro | Estructura del árbol y propagación de potencia |
| C02 | Dos circuitos que comparten un tramo de conducto | Camino elegido y longitud por cable |
| C03 | Varios circuitos en el mismo tramo | Factor de agrupamiento aplicado |
| C04 | Conducto al límite de ocupación | Cómo reporta el exceso y qué sección propone |
| C05 | Circuito largo con caída límite | Sección elegida y verificación |
| C06 | Tabla de un cuadro con columnas personalizadas | Contenido y orden de columnas |
| C07 | Duplicar, renombrar y eliminar un elemento | Efectos sobre dependencias |
| C08 | Red auxiliar de datos o incendio | Reglas de ruteo y ocupación propias |
| C09 | Exportación BIM y lista de cables | Entidades, propiedades y cantidades |
| C10 | Cambio de potencia en una carga | Propagación y actualización de tablas |

### Evidencia y límites

- Se admiten capturas y archivos **generados por la herramienta** si el EULA lo
  permite; nunca volcados de memoria, recursos extraídos ni código.
- No se registran claves, rutas internas ni mensajes que revelen implementación.
- El resultado se contrasta con NBR 5410 y con cálculos propios; la norma manda
  sobre el comportamiento observado.

### De la observación al test

1. Convertir cada caso en un test de aceptación con entrada y salida esperada.
2. Implementar de forma independiente (nuestro motor ya es propio).
3. Comparar contra la evidencia con las tolerancias declaradas.
4. Si hay discrepancia, prevalece la norma; se documenta la diferencia.
5. Validar el IFC resultante con IfcOpenShell y en un visor abierto
   (Bonsai/FreeCAD).

## Criterio de cierre

- Matriz de paridad con estado por servicio: pendiente, en curso o verificado.
- Casos C01–C10 documentados y, cuando sea posible, automatizados.
- IFC válido y legible en un visor independiente.
- Revisión por un profesional habilitado antes de usar en proyectos reales.
- Sin código, recursos ni tablas copiadas de productos propietarios.
