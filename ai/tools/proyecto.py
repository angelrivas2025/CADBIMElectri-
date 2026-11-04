"""Herramientas deterministas sobre el proyecto JSON.

Cada herramienta valida sus argumentos, comprueba referencias y muta el
proyecto. El cálculo y la conformidad los resuelve `core.calc`, nunca la IA.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ai.tools.registry import ErrorHerramienta, definir

TIPOS_PUNTO = ["luminaria", "interruptor", "tug", "tue", "tablero"]
TIPOS_AMBIENTE = [
    "sala", "dormitorio", "cocina", "bano", "servicio", "garaje", "externo", "otro",
]
TIPOS_CIRCUITO = ["iluminacion", "tug", "tue"]
FASES = ["A", "B", "C", "AB", "BC", "AC", "ABC"]

_SIN_ARGS = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}


def _nivel(project: dict[str, Any], nivel_id: str | None) -> str:
    niveles = project["levels"]
    if not niveles:
        raise ErrorHerramienta("el proyecto no tiene niveles; agregue uno primero")
    if nivel_id is None:
        return niveles[0]["id"]
    if not any(n["id"] == nivel_id for n in niveles):
        raise ErrorHerramienta(f"nivel inexistente '{nivel_id}'")
    return nivel_id


def _unico(items: list[dict[str, Any]], nuevo: str, etiqueta: str) -> None:
    if any(item["id"] == nuevo for item in items):
        raise ErrorHerramienta(f"{etiqueta} duplicado '{nuevo}'")


def _buscar(items: list[dict[str, Any]], item_id: str, etiqueta: str) -> dict[str, Any]:
    for item in items:
        if item["id"] == item_id:
            return item
    raise ErrorHerramienta(f"{etiqueta} inexistente '{item_id}'")


@definir(
    "set_project",
    "Actualiza nombre, tensión, sistema o ubicación del proyecto.",
    {
        "type": "object",
        "properties": {
            "name": {"type": "string", "minLength": 1},
            "voltage": {"type": "number", "exclusiveMinimum": 0},
            "system": {
                "type": "string",
                "enum": ["monofasico", "bifasico", "trifasico"],
            },
            "location": {"type": "string"},
        },
        "additionalProperties": False,
    },
)
def actualizar_proyecto(
    project: dict[str, Any], arguments: dict[str, Any]
) -> dict[str, Any]:
    if not arguments:
        raise ErrorHerramienta("set_project requiere al menos un dato")
    project["project"].update(arguments)
    return {
        "name": project["project"]["name"],
        "voltage": project["project"]["voltage"],
        "system": project["project"]["system"],
    }


@definir(
    "set_supply",
    "Declara o actualiza los datos del suministro (tipo, tormentas, ICC, "
    "alimentador) que usan las protecciones y el alimentador.",
    {
        "type": "object",
        "properties": {
            "type": {"type": "string", "enum": ["aerea", "subterranea"]},
            "thunderstorm_days": {"type": "number", "minimum": 0},
            "exposed_parts": {"type": "boolean"},
            "has_lightning_rod": {"type": "boolean"},
            "sensitive_equipment": {"type": "boolean"},
            "icc_ka": {"type": "number", "exclusiveMinimum": 0},
            "feeder_length_m": {"type": "number", "exclusiveMinimum": 0},
            "feeder_method": {
                "type": "string",
                "enum": ["A1", "A2", "B1", "B2", "C", "D", "E", "F", "G"],
            },
        },
        "additionalProperties": False,
    },
)
def declarar_suministro(
    project: dict[str, Any], arguments: dict[str, Any]
) -> dict[str, Any]:
    if not arguments:
        raise ErrorHerramienta("set_supply requiere al menos un dato")
    suministro = project["project"].setdefault("supply", {})
    suministro.update(arguments)
    return {"supply": dict(suministro)}


@definir(
    "get_project_summary",
    "Resume el proyecto: datos generales, niveles, ambientes, puntos, circuitos y "
    "tableros. No calcula ni modifica nada.",
    _SIN_ARGS,
)
def resumen(project: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    datos = project["project"]
    conteo_puntos = {tipo: 0 for tipo in TIPOS_PUNTO}
    for punto in project["points"]:
        conteo_puntos[punto["type"]] += 1
    return {
        "nombre": datos["name"],
        "norma": datos["norm"],
        "sistema": datos["system"],
        "tension_v": datos["voltage"],
        "niveles": [n["id"] for n in project["levels"]],
        "ambientes": len(project["rooms"]),
        "puntos": conteo_puntos,
        "circuitos": [c["id"] for c in project["circuits"]],
        "tableros": [p["id"] for p in project["panels"]],
        "red": bool(project.get("network")),
    }


@definir(
    "add_level",
    "Agrega un nivel (piso) con su cota en metros.",
    {
        "type": "object",
        "properties": {
            "id": {"type": "string", "minLength": 1},
            "name": {"type": "string", "minLength": 1},
            "elevation": {"type": "number"},
        },
        "required": ["id", "name", "elevation"],
        "additionalProperties": False,
    },
)
def agregar_nivel(project: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    _unico(project["levels"], arguments["id"], "nivel")
    project["levels"].append(
        {
            "id": arguments["id"],
            "name": arguments["name"],
            "elevation": float(arguments["elevation"]),
        }
    )
    return {"id": arguments["id"]}


@definir(
    "add_room",
    "Agrega un ambiente con polígono en metros. Sin 'level' usa el primer nivel.",
    {
        "type": "object",
        "properties": {
            "id": {"type": "string", "minLength": 1},
            "name": {"type": "string", "minLength": 1},
            "type": {"type": "string", "enum": TIPOS_AMBIENTE},
            "polygon": {
                "type": "array",
                "minItems": 3,
                "items": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 2,
                    "maxItems": 2,
                },
            },
            "level": {"type": "string"},
        },
        "required": ["id", "name", "type", "polygon"],
        "additionalProperties": False,
    },
)
def agregar_ambiente(project: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    _unico(project["rooms"], arguments["id"], "ambiente")
    nivel = _nivel(project, arguments.get("level"))
    project["rooms"].append(
        {
            "id": arguments["id"],
            "level": nivel,
            "name": arguments["name"],
            "type": arguments["type"],
            "polygon": [
                [float(vertice[0]), float(vertice[1])] for vertice in arguments["polygon"]
            ],
        }
    )
    return {"id": arguments["id"], "level": nivel}


@definir(
    "update_room",
    "Actualiza nombre, tipo, polígono o nivel de un ambiente existente.",
    {
        "type": "object",
        "properties": {
            "id": {"type": "string", "minLength": 1},
            "name": {"type": "string", "minLength": 1},
            "type": {"type": "string", "enum": TIPOS_AMBIENTE},
            "polygon": {
                "type": "array",
                "minItems": 3,
                "items": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 2,
                    "maxItems": 2,
                },
            },
            "level": {"type": "string"},
        },
        "required": ["id"],
        "additionalProperties": False,
    },
)
def actualizar_ambiente(
    project: dict[str, Any], arguments: dict[str, Any]
) -> dict[str, Any]:
    ambiente = _buscar(project["rooms"], arguments["id"], "ambiente")
    cambios = {k: v for k, v in arguments.items() if k != "id"}
    if not cambios:
        raise ErrorHerramienta("update_room requiere al menos un campo a cambiar")
    if "level" in cambios:
        cambios["level"] = _nivel(project, cambios["level"])
    if "polygon" in cambios:
        cambios["polygon"] = [
            [float(vertice[0]), float(vertice[1])] for vertice in cambios["polygon"]
        ]
    ambiente.update(cambios)
    return {"id": ambiente["id"]}


@definir(
    "add_panel",
    "Agrega un tablero de distribución en un nivel. Sin 'level' usa el primero.",
    {
        "type": "object",
        "properties": {
            "id": {"type": "string", "minLength": 1},
            "name": {"type": "string", "minLength": 1},
            "level": {"type": "string"},
        },
        "required": ["id", "name"],
        "additionalProperties": False,
    },
)
def agregar_tablero(project: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    _unico(project["panels"], arguments["id"], "tablero")
    nivel = _nivel(project, arguments.get("level"))
    project["panels"].append(
        {"id": arguments["id"], "name": arguments["name"], "level": nivel}
    )
    return {"id": arguments["id"], "level": nivel}


@definir(
    "place_point",
    "Coloca un punto eléctrico en un ambiente. 'power' se declara en VA.",
    {
        "type": "object",
        "properties": {
            "id": {"type": "string", "minLength": 1},
            "type": {"type": "string", "enum": TIPOS_PUNTO},
            "room": {"type": "string", "minLength": 1},
            "position": {
                "type": "array",
                "items": {"type": "number"},
                "minItems": 2,
                "maxItems": 2,
            },
            "power": {"type": "number", "minimum": 0},
            "height": {"type": "number"},
            "circuit": {"type": ["string", "null"]},
            "feeds_outdoor": {"type": "boolean"},
        },
        "required": ["id", "type", "room", "position"],
        "allOf": [
            {
                "if": {
                    "properties": {"type": {"not": {"const": "tablero"}}},
                    "required": ["type"],
                },
                "then": {"required": ["power"]},
            }
        ],
        "additionalProperties": False,
    },
)
def colocar_punto(project: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    _unico(project["points"], arguments["id"], "punto")
    _buscar(project["rooms"], arguments["room"], "ambiente")
    circuito = arguments.get("circuit")
    if circuito is not None:
        _buscar(project["circuits"], circuito, "circuito")
    punto = {
        "id": arguments["id"],
        "type": arguments["type"],
        "room": arguments["room"],
        "position": [float(v) for v in arguments["position"]],
        "power": float(arguments.get("power", 0.0)),
    }
    for clave in ("height", "circuit", "feeds_outdoor"):
        if clave in arguments:
            punto[clave] = arguments[clave]
    project["points"].append(punto)
    return {"id": punto["id"]}


@definir(
    "create_circuit",
    "Crea un circuito en un tablero. Longitud, método y materiales son opcionales; "
    "el dimensionamiento lo calcula el motor.",
    {
        "type": "object",
        "properties": {
            "id": {"type": "string", "minLength": 1},
            "name": {"type": "string", "minLength": 1},
            "type": {"type": "string", "enum": TIPOS_CIRCUITO},
            "panel": {"type": "string", "minLength": 1},
            "phase": {"type": "string", "enum": FASES},
            "method": {
                "type": "string",
                "enum": ["A1", "A2", "B1", "B2", "C", "D", "E", "F", "G"],
            },
            "method_variant": {
                "type": "string",
                "enum": ["F_JUSTAPOSTO", "F_TRIFOLIO", "G_HORIZONTAL", "G_VERTICAL"],
            },
            "length_m": {"type": "number", "exclusiveMinimum": 0},
            "n_loaded": {"type": "integer", "enum": [2, 3]},
            "material": {"type": "string", "enum": ["Cu", "Al"]},
            "insulation": {"type": "string", "enum": ["PVC", "XLPE"]},
        },
        "required": ["id", "name", "type", "panel"],
        "additionalProperties": False,
    },
)
def crear_circuito(project: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    _unico(project["circuits"], arguments["id"], "circuito")
    _buscar(project["panels"], arguments["panel"], "tablero")
    circuito = {
        "id": arguments["id"],
        "name": arguments["name"],
        "type": arguments["type"],
        "panel": arguments["panel"],
    }
    for clave in (
        "phase", "method", "method_variant", "length_m",
        "n_loaded", "material", "insulation",
    ):
        if clave in arguments:
            circuito[clave] = arguments[clave]
    project["circuits"].append(circuito)
    return {"id": circuito["id"]}


@definir(
    "assign_to_circuit",
    "Asigna un punto a un circuito; con 'circuit' nulo lo deja sin circuito.",
    {
        "type": "object",
        "properties": {
            "point": {"type": "string", "minLength": 1},
            "circuit": {"type": ["string", "null"]},
        },
        "required": ["point", "circuit"],
        "additionalProperties": False,
    },
)
def asignar_circuito(project: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    punto = _buscar(project["points"], arguments["point"], "punto")
    if punto["type"] == "tablero":
        raise ErrorHerramienta("un punto de tablero no se asigna a un circuito")
    if arguments["circuit"] is not None:
        _buscar(project["circuits"], arguments["circuit"], "circuito")
    punto["circuit"] = arguments["circuit"]
    return {"point": punto["id"], "circuit": punto["circuit"]}


@definir(
    "run_validation",
    "Ejecuta el motor NBR 5410 y devuelve conformidad, errores, avisos y el "
    "dimensionamiento por circuito. La IA comunica estos números, no los calcula.",
    _SIN_ARGS,
)
def validar(project: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    from core.calc.validate import validar_proyecto

    informe = validar_proyecto(project)
    circuitos = []
    for c in ((informe.get("dimensionamiento") or {}).get("circuits") or []):
        circuitos.append(
            {
                "id": c["id"],
                "breaker_a": c.get("breaker_a"),
                "section_mm2": c.get("section_mm2"),
                "current_a": c.get("current_a"),
                "voltage_drop_pct": c.get("voltage_drop_pct"),
                "length_source": c.get("length_source"),
            }
        )
    return {
        "conforme": informe["ok"],
        "errores": informe["errores"],
        "avisos": informe["avisos"],
        "circuitos": circuitos,
        "alimentador": informe.get("alimentador"),
    }


@definir(
    "export",
    "Exporta el proyecto validado a svg, pdf, csv, ifc o todos ('todo') en la "
    "ruta indicada.",
    {
        "type": "object",
        "properties": {
            "format": {
                "type": "string",
                "enum": ["svg", "pdf", "csv", "ifc", "todo"],
            },
            "path": {"type": "string", "minLength": 1},
        },
        "required": ["format", "path"],
        "additionalProperties": False,
    },
)
def exportar(project: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    from core.calc.validate import validar_proyecto

    formato = arguments["format"]
    destino = Path(arguments["path"])
    informe = validar_proyecto(project)

    try:
        if formato == "todo":
            from exporters.export import exportar_todo

            rutas = exportar_todo(project, informe, destino)
            return {"rutas": {clave: str(ruta) for clave, ruta in rutas.items()}}
        destino.parent.mkdir(parents=True, exist_ok=True)
        if formato == "svg":
            from exporters.diagram import construir_unifilar
            from exporters.svg import escribir_svg

            escribir_svg(construir_unifilar(project, informe), destino)
        elif formato == "pdf":
            from exporters.pdf import informe_pdf

            informe_pdf(project, informe, destino)
        elif formato == "csv":
            from exporters.csv_export import cuadro_csv

            cuadro_csv(project, informe, destino)
        elif formato == "ifc":
            from exporters.ifc import disponible, modelo_ifc

            if not disponible():
                raise ErrorHerramienta(
                    "IFC no disponible: instale el extra 'cadbimelectri[bim]'"
                )
            modelo_ifc(project, informe, destino)
        else:  # pragma: no cover - el esquema ya limita los formatos
            raise ErrorHerramienta(f"formato desconocido '{formato}'")
    except (ImportError, RuntimeError) as exc:
        raise ErrorHerramienta(f"no se pudo exportar {formato}: {exc}") from exc
    return {"format": formato, "path": str(destino)}
