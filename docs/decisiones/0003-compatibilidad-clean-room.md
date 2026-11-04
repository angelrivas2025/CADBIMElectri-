# ADR 0003: Compatibilidad e ingeniería inversa limpia

Estado: **aceptada** (2026-11-04)

## Contexto

El proyecto toma como referencia funcional herramientas comerciales de proyectos
eléctricos en BIM, en particular **electroBIM** (Electro Graphics / Hiper Energy)
y el software de cálculo **Ampère**. Igualar servicios es un objetivo legítimo:
la funcionalidad y las ideas no están protegidas por derecho de autor, pero el
código, los recursos y la documentación técnica de esos productos sí lo están.

Existe la tentación de descompilar el plugin o de reutilizar sus tablas y
recursos. Eso introduciría riesgo legal, posible contaminación de licencia y
dependencia de binarios ajenos. Brasil no tiene una excepción amplia de
descompilación como la Unión Europea, y el EULA del producto puede prohibirla.

## Decisión

**Política de clean room: paridad funcional por especificación y pruebas de caja
negra, sin acceder al código propietario.**

1. **Prohibido** descompilar, desensamblar, depurar o extraer recursos de
   binarios ajenos; saltar licencias o activaciones; usar código filtrado o de
   procedencia desconocida.
2. **Fuentes admitidas:** documentación pública, normas técnicas licenciadas,
   comportamiento observable bajo acceso legítimo, archivos generados por el
   propio usuario (IFC, CSV, PDF, XML) y proyectos open source con su licencia
   respetada.
3. **Especificación primero:** cada requisito de paridad se escribe como caso de
   uso con entradas, salidas y tolerancias antes de implementar. El
   implementador trabaja desde la especificación, no desde el binario.
4. **Registro de procedencia:** cada requisito indica de dónde salió (manual,
   norma, observación de caja negra). Sin procedencia, no entra al alcance.
5. **Compatibilidad por formatos abiertos:** IFC, CSV y JSON. Un formato
   propietario solo se soporta con documentación del proveedor o autorización
   expresa; nunca por ingeniería inversa del binario.
6. **Marcas:** los nombres de terceros se usan solo como referencia factual en
   documentación. No se usan en el producto ni se declara compatibilidad sin
   pruebas que la respalden.
7. **Normas:** los valores se cargan desde fuente oficial licenciada y se citan
   por tabla/artículo; no se copian del software de referencia (ya establecido
   en el ADR 0002).
8. **Revisión legal:** este ADR es política de ingeniería, no asesoría jurídica.
   Cualquier análisis de binarios ajenos requiere consulta previa con un abogado
   especializado en propiedad intelectual.

## Consecuencias

- La paridad avanza por **especificación + tests**, más lenta que copiar código
  pero sin riesgo de indemnización ni de contaminar Apache-2.0.
- electroBIM y Ampère quedan como **referencias de comportamiento**, no como
  dependencias.
- QElectroTech (GPL) sigue siendo solo referencia de formato: el `.qet` se genera
  desde cero y no se copia código.
- La documentación de paridad es pública y auditable; el protocolo está en
  [docs/compatibilidad/electrobim.md](../compatibilidad/electrobim.md).
- Si en el futuro se necesita importar un formato propietario, la vía es pedir
  la especificación al proveedor o usar sus exportaciones, no analizar el
  binario.
