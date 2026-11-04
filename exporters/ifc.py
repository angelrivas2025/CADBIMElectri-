"""Exportación BIM/IFC4: espacios, puntos eléctricos, tablero y circuitos.

Usa IfcOpenShell (dependencia opcional ``bim``). El modelo es un IFC4 válido con
unidades SI, jerarquía espacial, geometría de espacios por extrusión y propiedades
de cálculo en property sets propios (``Pset_CADBIMElectri_*``).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from core.calc.validate import validar_proyecto

ALTURA_ESPACIO_M = 2.6
TAMANO_CAJA_M = 0.1
TAMANO_TABLERO_M = 0.35
TAMANO_MINIMO_TRAMO_M = 0.01

TIPO_TRAMO_IFC = {
    "conduit": "CONDUITSEGMENT",
    "tray": "CABLETRAYSEGMENT",
    "riser": "CONDUITSEGMENT",
}
FLUJO_NODO = {
    "supply": "SOURCE",
    "panel": "SOURCEANDSINK",
    "junction": "SOURCEANDSINK",
    "load": "SINK",
}


def disponible() -> bool:
    """Indica si IfcOpenShell está instalado."""
    return importlib.util.find_spec("ifcopenshell") is not None

CLASES_PUNTO = {
    "luminaria": ("IfcLightFixture", "POINTSOURCE"),
    "interruptor": ("IfcSwitchingDevice", "TOGGLESWITCH"),
    "tug": ("IfcOutlet", "POWEROUTLET"),
    "tue": ("IfcOutlet", "POWEROUTLET"),
    "tablero": ("IfcElectricDistributionBoard", "DISTRIBUTIONBOARD"),
}


def _ifc():
    try:
        import ifcopenshell
        import ifcopenshell.guid
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise RuntimeError(
            "La exportación IFC requiere ifcopenshell. Instale el extra: "
            "pip install 'cadbimelectri[bim]'"
        ) from exc
    return ifcopenshell


def _punto(model: Any, x: float, y: float, z: float) -> Any:
    return model.create_entity("IfcCartesianPoint", (float(x), float(y), float(z)))


def _eje(model: Any, x: float = 0.0, y: float = 0.0, z: float = 0.0) -> Any:
    return model.create_entity("IfcAxis2Placement3D", Location=_punto(model, x, y, z))


def _propiedad(model: Any, nombre: str, valor: Any) -> Any:
    if isinstance(valor, bool):
        envuelto = model.create_entity("IfcBoolean", valor)
    elif isinstance(valor, int):
        envuelto = model.create_entity("IfcInteger", valor)
    elif isinstance(valor, float):
        envuelto = model.create_entity("IfcReal", valor)
    else:
        envuelto = model.create_entity("IfcLabel", str(valor))
    return model.create_entity(
        "IfcPropertySingleValue", Name=nombre, Description=None,
        NominalValue=envuelto, Unit=None,
    )


def _pset(model: Any, guid: Any, objeto: Any, nombre: str, props: dict[str, Any]) -> None:
    pset = model.create_entity(
        "IfcPropertySet",
        GlobalId=guid.new(),
        OwnerHistory=None,
        Name=nombre,
        Description=None,
        HasProperties=[_propiedad(model, k, v) for k, v in props.items()],
    )
    model.create_entity(
        "IfcRelDefinesByProperties",
        GlobalId=guid.new(),
        OwnerHistory=None,
        Name=None,
        Description=None,
        RelatedObjects=[objeto],
        RelatingPropertyDefinition=pset,
    )


def _perfil_poligono(model: Any, poligono: list[list[float]]) -> Any:
    puntos = [
        model.create_entity("IfcCartesianPoint", (float(x), float(y)))
        for x, y in poligono
    ]
    puntos.append(puntos[0])
    return model.create_entity(
        "IfcArbitraryClosedProfileDef",
        ProfileType="AREA",
        ProfileName=None,
        OuterCurve=model.create_entity("IfcPolyline", Points=puntos),
    )


def _representacion_espacio(model: Any, contexto: Any, poligono: list[list[float]]) -> Any:
    solido = model.create_entity(
        "IfcExtrudedAreaSolid",
        SweptArea=_perfil_poligono(model, poligono),
        Position=_eje(model),
        ExtrudedDirection=model.create_entity("IfcDirection", (0.0, 0.0, 1.0)),
        Depth=ALTURA_ESPACIO_M,
    )
    forma = model.create_entity(
        "IfcShapeRepresentation",
        ContextOfItems=contexto,
        RepresentationIdentifier="Body",
        RepresentationType="SweptSolid",
        Items=[solido],
    )
    return model.create_entity(
        "IfcProductDefinitionShape", Name=None, Description=None, Representations=[forma]
    )


def _representacion_bbox(
    model: Any, contexto: Any, x: float, y: float, z: float
) -> Any:
    caja = model.create_entity(
        "IfcBoundingBox",
        Corner=_punto(model, 0.0, 0.0, 0.0),
        XDim=max(float(x), TAMANO_MINIMO_TRAMO_M),
        YDim=max(float(y), TAMANO_MINIMO_TRAMO_M),
        ZDim=max(float(z), TAMANO_MINIMO_TRAMO_M),
    )
    forma = model.create_entity(
        "IfcShapeRepresentation",
        ContextOfItems=contexto,
        RepresentationIdentifier="Box",
        RepresentationType="BoundingBox",
        Items=[caja],
    )
    return model.create_entity(
        "IfcProductDefinitionShape", Name=None, Description=None, Representations=[forma]
    )


def _representacion_caja(model: Any, contexto: Any, tamano: float) -> Any:
    return _representacion_bbox(model, contexto, tamano, tamano, tamano)


def _colocacion(model: Any, relativa_a: Any, x: float, y: float, z: float) -> Any:
    return model.create_entity(
        "IfcLocalPlacement",
        PlacementRelTo=relativa_a,
        RelativePlacement=_eje(model, x, y, z),
    )


def _puerto(
    model: Any,
    guid: Any,
    elemento: Any,
    flujo: str,
    x: float = 0.0,
    y: float = 0.0,
    z: float = 0.0,
) -> Any:
    puerto = model.create_entity(
        "IfcDistributionPort",
        GlobalId=guid.new(),
        OwnerHistory=None,
        Name=None,
        Description=None,
        ObjectType=None,
        ObjectPlacement=_colocacion(model, elemento.ObjectPlacement, x, y, z),
        Representation=None,
        FlowDirection=flujo,
        PredefinedType="CABLECARRIER",
        SystemType=None,
    )
    model.create_entity(
        "IfcRelConnectsPortToElement",
        GlobalId=guid.new(),
        OwnerHistory=None,
        Name=None,
        Description=None,
        RelatingPort=puerto,
        RelatedElement=elemento,
    )
    return puerto


def _conectar(model: Any, guid: Any, puerto_a: Any, puerto_b: Any, elemento: Any) -> None:
    model.create_entity(
        "IfcRelConnectsPorts",
        GlobalId=guid.new(),
        OwnerHistory=None,
        Name=None,
        Description=None,
        RelatingPort=puerto_a,
        RelatedPort=puerto_b,
        RealizingElement=elemento,
    )


def modelo_ifc(
    project: dict[str, Any], informe: dict[str, Any] | None, ruta: str | Path
) -> Path:
    """Genera un IFC4 con el modelo eléctrico básico y devuelve la ruta escrita."""
    ifcopenshell = _ifc()
    guid = ifcopenshell.guid
    if informe is None:
        informe = validar_proyecto(project)

    model = ifcopenshell.file(schema="IFC4")
    nombre_proyecto = project["project"]["name"]

    origen = _eje(model)
    contexto = model.create_entity(
        "IfcGeometricRepresentationContext",
        ContextIdentifier="Model",
        ContextType="Model",
        CoordinateSpaceDimension=3,
        Precision=1e-5,
        WorldCoordinateSystem=origen,
    )
    unidades = model.create_entity(
        "IfcUnitAssignment",
        Units=[
            model.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE"),
            model.create_entity("IfcSIUnit", UnitType="AREAUNIT", Name="SQUARE_METRE"),
            model.create_entity("IfcSIUnit", UnitType="VOLUMEUNIT", Name="CUBIC_METRE"),
            model.create_entity("IfcSIUnit", UnitType="ELECTRICCURRENTUNIT", Name="AMPERE"),
            model.create_entity("IfcSIUnit", UnitType="ELECTRICVOLTAGEUNIT", Name="VOLT"),
            model.create_entity("IfcSIUnit", UnitType="POWERUNIT", Name="WATT"),
        ],
    )
    proyecto = model.create_entity(
        "IfcProject",
        GlobalId=guid.new(),
        OwnerHistory=None,
        Name=nombre_proyecto,
        Description=(
            f"{project['project']['norm']} · {project['project']['system']} · "
            f"{project['project']['voltage']:g} V fase-neutro"
        ),
        ObjectType=None,
        LongName=project["project"].get("location"),
        Phase=None,
        RepresentationContexts=[contexto],
        UnitsInContext=unidades,
    )

    sitio = model.create_entity(
        "IfcSite",
        GlobalId=guid.new(), OwnerHistory=None, Name="Sitio",
        Description=project["project"].get("location"), ObjectType=None,
        ObjectPlacement=_colocacion(model, None, 0.0, 0.0, 0.0), Representation=None,
        LongName=None, CompositionType="ELEMENT", RefLatitude=None,
        RefLongitude=None, RefElevation=None, LandTitleNumber=None, SiteAddress=None,
    )
    edificio = model.create_entity(
        "IfcBuilding",
        GlobalId=guid.new(), OwnerHistory=None, Name="Edificio",
        Description=None, ObjectType=None,
        ObjectPlacement=_colocacion(model, sitio.ObjectPlacement, 0.0, 0.0, 0.0),
        Representation=None, LongName=None, CompositionType="ELEMENT",
        ElevationOfRefHeight=None, ElevationOfTerrain=None, BuildingAddress=None,
    )
    model.create_entity(
        "IfcRelAggregates", GlobalId=guid.new(), OwnerHistory=None, Name=None,
        Description=None, RelatingObject=proyecto, RelatedObjects=[sitio],
    )
    model.create_entity(
        "IfcRelAggregates", GlobalId=guid.new(), OwnerHistory=None, Name=None,
        Description=None, RelatingObject=sitio, RelatedObjects=[edificio],
    )

    niveles = project["levels"] or [{"id": "N0", "name": "Nivel 0", "elevation": 0}]
    pisos: dict[str, Any] = {}
    for nivel in niveles:
        elevacion = float(nivel.get("elevation", 0.0))
        piso = model.create_entity(
            "IfcBuildingStorey",
            GlobalId=guid.new(), OwnerHistory=None, Name=nivel["name"],
            Description=None, ObjectType=None,
            ObjectPlacement=_colocacion(model, edificio.ObjectPlacement, 0.0, 0.0, elevacion),
            Representation=None, LongName=None, CompositionType="ELEMENT",
            Elevation=elevacion,
        )
        pisos[nivel["id"]] = piso
    model.create_entity(
        "IfcRelAggregates", GlobalId=guid.new(), OwnerHistory=None, Name=None,
        Description=None, RelatingObject=edificio, RelatedObjects=list(pisos.values()),
    )
    elevaciones = {
        nivel["id"]: float(nivel.get("elevation", 0.0)) for nivel in niveles
    }

    rooms = {r["id"]: r for r in project["rooms"]}
    nivel_por_defecto = niveles[0]["id"]
    contenidos: dict[str, list[Any]] = {nivel["id"]: [] for nivel in niveles}
    espacios_por_nivel: dict[str, list[Any]] = {nivel["id"]: [] for nivel in niveles}

    for room in project["rooms"]:
        nivel_id = room.get("level") or nivel_por_defecto
        piso = pisos.get(nivel_id, pisos[nivel_por_defecto])
        poligono = room.get("polygon") or []
        representacion = (
            _representacion_espacio(model, contexto, poligono)
            if len(poligono) >= 3
            else None
        )
        punto = room.get("type") == "externo"
        espacio = model.create_entity(
            "IfcSpace",
            GlobalId=guid.new(), OwnerHistory=None, Name=room["name"],
            Description=f"Tipo: {room['type']}", ObjectType=None,
            ObjectPlacement=_colocacion(model, piso.ObjectPlacement, 0.0, 0.0, 0.0),
            Representation=representacion, LongName=room["name"],
            CompositionType="ELEMENT",
            PredefinedType="EXTERNAL" if punto else "SPACE",
            ElevationWithFlooring=float(pisos[nivel_id].Elevation) if nivel_id in pisos else 0.0,
        )
        _pset(
            model, guid, espacio, "Pset_CADBIMElectri_Ambiente",
            {"Tipo": room["type"], "Nivel": nivel_id},
        )
        espacios_por_nivel[
            nivel_id if nivel_id in espacios_por_nivel else nivel_por_defecto
        ].append(espacio)

    for nivel_id, espacios in espacios_por_nivel.items():
        if espacios:
            model.create_entity(
                "IfcRelAggregates",
                GlobalId=guid.new(), OwnerHistory=None, Name=None, Description=None,
                RelatingObject=pisos[nivel_id], RelatedObjects=espacios,
            )

    tableros: dict[str, Any] = {}
    nodos_red = {
        nodo["id"]: nodo
        for nodo in (project.get("network") or {}).get("nodes", [])
    }
    nodos_panel = {
        nodo["ref"]: nodo for nodo in nodos_red.values() if nodo["type"] == "panel"
    }
    for panel in project["panels"]:
        nivel_id = panel.get("level") or nivel_por_defecto
        piso = pisos.get(nivel_id, pisos[nivel_por_defecto])
        nodo = nodos_panel.get(panel["id"])
        if nodo is not None:
            x, y = (float(v) for v in nodo["position"][:2])
            z = float(nodo["height"])
        else:
            ubicacion = next(
                (p for p in project["points"] if p["type"] == "tablero" and p["room"] in rooms),
                None,
            )
            x = float(ubicacion["position"][0]) if ubicacion else 0.0
            y = float(ubicacion["position"][1]) if ubicacion else 0.0
            z = float(ubicacion.get("height", 1.5)) if ubicacion else 1.5
        tablero = model.create_entity(
            "IfcElectricDistributionBoard",
            GlobalId=guid.new(), OwnerHistory=None, Name=panel["name"],
            Description="Tablero de distribución", ObjectType=None,
            ObjectPlacement=_colocacion(model, piso.ObjectPlacement, x, y, z),
            Representation=_representacion_caja(model, contexto, TAMANO_TABLERO_M),
            Tag=panel["id"], PredefinedType="DISTRIBUTIONBOARD",
        )
        tableros[panel["id"]] = tablero
        contenidos[nivel_id if nivel_id in contenidos else nivel_por_defecto].append(tablero)

    dimensionado = {
        c["id"]: c for c in ((informe.get("dimensionamiento") or {}).get("circuits") or [])
    }
    dr_por_circuito = (informe.get("protecciones") or {}).get("dr_por_circuito") or {}

    elementos_por_circuito: dict[str, list[Any]] = {}
    for point in project["points"]:
        if point["type"] == "tablero":
            continue
        clase, predefined = CLASES_PUNTO.get(
            point["type"], ("IfcBuildingElementProxy", None)
        )
        room = rooms.get(point["room"])
        if not room:
            continue
        nivel_id = room.get("level") or nivel_por_defecto
        piso = pisos.get(nivel_id, pisos[nivel_por_defecto])
        x, y = (float(v) for v in point["position"][:2])
        z = float(point.get("height", 0.3))
        atributos = {
            "GlobalId": guid.new(), "OwnerHistory": None, "Name": point["id"],
            "Description": f"{point['type']} · {room['name']}", "ObjectType": None,
            "ObjectPlacement": _colocacion(model, piso.ObjectPlacement, x, y, z),
            "Representation": _representacion_caja(model, contexto, TAMANO_CAJA_M),
            "Tag": point["id"],
        }
        if clase != "IfcBuildingElementProxy":
            atributos["PredefinedType"] = predefined
        elemento = model.create_entity(clase, **atributos)
        _pset(
            model, guid, elemento, "Pset_CADBIMElectri_Punto",
            {
                "Referencia": point["id"],
                "Tipo": point["type"],
                "Circuito": point.get("circuit") or "",
                "PotenciaVA": float(point.get("power") or 0.0),
                "Nivel": nivel_id,
                "Ambiente": room["name"],
            },
        )
        contenidos[nivel_id if nivel_id in contenidos else nivel_por_defecto].append(elemento)
        circuito = point.get("circuit")
        if circuito:
            elementos_por_circuito.setdefault(circuito, []).append(elemento)

    red = informe.get("red") or {}
    nodos_ifc: dict[str, Any] = {}
    tramos_ifc: dict[str, Any] = {}
    geometria_tramos: dict[str, tuple] = {}
    if red.get("presente"):
        for nodo in project["network"]["nodes"]:
            if nodo["type"] == "panel":
                tablero = tableros.get(nodo["ref"])
                if tablero is not None:
                    nodos_ifc[nodo["id"]] = tablero
                continue
            nivel_id = nodo["level"]
            elemento = model.create_entity(
                "IfcJunctionBox",
                GlobalId=guid.new(), OwnerHistory=None, Name=f"Nodo {nodo['id']}",
                Description=f"Nodo de red: {nodo['type']}", ObjectType=None,
                ObjectPlacement=_colocacion(
                    model, pisos.get(nivel_id, pisos[nivel_por_defecto]).ObjectPlacement,
                    float(nodo["position"][0]), float(nodo["position"][1]),
                    float(nodo["height"]),
                ),
                Representation=_representacion_caja(model, contexto, TAMANO_CAJA_M),
                Tag=nodo["id"], PredefinedType="POWER",
            )
            _pset(
                model, guid, elemento, "Pset_CADBIMElectri_NodoRed",
                {
                    "Tipo": nodo["type"],
                    "Referencia": nodo.get("ref") or nodo["id"],
                    "Nivel": nivel_id,
                    "AlturaM": float(nodo["height"]),
                },
            )
            contenidos[nivel_id if nivel_id in contenidos else nivel_por_defecto].append(elemento)
            nodos_ifc[nodo["id"]] = elemento

        por_tramo = red.get("por_tramo") or {}

        def _coords(nodo: dict[str, Any]) -> tuple[float, float, float]:
            return (
                float(nodo["position"][0]),
                float(nodo["position"][1]),
                elevaciones.get(nodo["level"], 0.0) + float(nodo["height"]),
            )

        for tramo in project["network"]["segments"]:
            sid = tramo["id"]
            origen = nodos_red[tramo["from"]]
            destino = nodos_red[tramo["to"]]
            puntos = [
                _coords(origen),
                *(
                    (float(p[0]), float(p[1]), float(p[2]))
                    for p in tramo.get("waypoints") or []
                ),
                _coords(destino),
            ]
            xs = [p[0] for p in puntos]
            ys = [p[1] for p in puntos]
            zs = [p[2] for p in puntos]
            minimo = (min(xs), min(ys), min(zs))
            dimensiones = (max(xs) - minimo[0], max(ys) - minimo[1], max(zs) - minimo[2])
            nivel_id = origen["level"]
            info = por_tramo.get(sid) or {}
            elemento = model.create_entity(
                "IfcCableCarrierSegment",
                GlobalId=guid.new(), OwnerHistory=None, Name=f"Tramo {sid}",
                Description=f"{tramo['kind']} {tramo['trade_size']}", ObjectType=None,
                ObjectPlacement=_colocacion(
                    model,
                    pisos.get(nivel_id, pisos[nivel_por_defecto]).ObjectPlacement,
                    minimo[0],
                    minimo[1],
                    minimo[2] - elevaciones.get(nivel_id, 0.0),
                ),
                Representation=_representacion_bbox(model, contexto, *dimensiones),
                Tag=sid, PredefinedType=TIPO_TRAMO_IFC[tramo["kind"]],
            )
            _pset(
                model, guid, elemento, "Pset_CADBIMElectri_Tramo",
                {
                    "Identificador": sid,
                    "Tipo": tramo["kind"],
                    "MedidaComercial": tramo["trade_size"],
                    "LongitudM": float(info.get("length_m") or 0.0),
                    "Circuitos": ", ".join(info.get("circuits") or []),
                    "NCircuitos": int(info.get("n_circuits") or 0),
                    "Nivel": nivel_id,
                },
            )
            contenidos[nivel_id if nivel_id in contenidos else nivel_por_defecto].append(elemento)
            tramos_ifc[sid] = elemento
            geometria_tramos[sid] = (puntos, minimo)

        for tramo in project["network"]["segments"]:
            sid = tramo["id"]
            elemento = tramos_ifc.get(sid)
            if elemento is None:
                continue
            puntos, minimo = geometria_tramos[sid]
            puertos = {
                "from": _puerto(
                    model, guid, elemento, "NOTDEFINED",
                    puntos[0][0] - minimo[0],
                    puntos[0][1] - minimo[1],
                    puntos[0][2] - minimo[2],
                ),
                "to": _puerto(
                    model, guid, elemento, "NOTDEFINED",
                    puntos[-1][0] - minimo[0],
                    puntos[-1][1] - minimo[1],
                    puntos[-1][2] - minimo[2],
                ),
            }
            for extremo, puerto in puertos.items():
                nodo_id = tramo[extremo]
                padre = nodos_ifc.get(nodo_id)
                if padre is None:
                    continue
                puerto_nodo = _puerto(
                    model, guid, padre, FLUJO_NODO[nodos_red[nodo_id]["type"]]
                )
                _conectar(model, guid, puerto, puerto_nodo, elemento)

    tramos_por_circuito: dict[str, list[Any]] = {}
    for cid, recorrido in (red.get("por_circuito") or {}).items():
        tramos_por_circuito[cid] = [
            tramos_ifc[sid]
            for sid in recorrido.get("segments", [])
            if sid in tramos_ifc
        ]

    circuitos = []
    for circuito in project["circuits"]:
        dim = dimensionado.get(circuito["id"], {})
        entidad = model.create_entity(
            "IfcDistributionCircuit",
            GlobalId=guid.new(), OwnerHistory=None, Name=circuito["name"],
            Description=f"Circuito {circuito['id']}", ObjectType=None,
            LongName=f"{circuito['id']} · fase {circuito.get('phase') or '-'}",
            PredefinedType="LIGHTING" if circuito["type"] == "iluminacion" else "ELECTRICAL",
        )
        _pset(
            model, guid, entidad, "Pset_CADBIMElectri_Circuito",
            {
                "Identificador": circuito["id"],
                "Tipo": circuito["type"],
                "Fase": circuito.get("phase") or "",
                "PotenciaVA": float(dim.get("power_va") or 0.0),
                "CorrienteA": float(dim.get("current_a") or 0.0),
                "Seccion_mm2": float(dim.get("section_mm2") or 0.0),
                "DisyuntorA": int(dim.get("breaker_a") or 0),
                "Caida_pct": float(dim.get("voltage_drop_pct") or 0.0),
                "DR_30mA": circuito["id"] in dr_por_circuito,
            },
        )
        asignados = elementos_por_circuito.get(circuito["id"], []) + tramos_por_circuito.get(
            circuito["id"], []
        )
        if asignados:
            model.create_entity(
                "IfcRelAssignsToGroup",
                GlobalId=guid.new(), OwnerHistory=None, Name=None, Description=None,
                RelatedObjects=asignados, RelatedObjectsType=None,
                RelatingGroup=entidad,
            )
        circuitos.append(entidad)

    for panel_id, tablero in tableros.items():
        del_panel = [
            entidad for circuito, entidad in zip(project["circuits"], circuitos)
            if circuito["panel"] == panel_id
        ]
        if del_panel:
            model.create_entity(
                "IfcRelAggregates",
                GlobalId=guid.new(), OwnerHistory=None, Name=None, Description=None,
                RelatingObject=tablero, RelatedObjects=del_panel,
            )

    for nivel_id, elementos in contenidos.items():
        if not elementos:
            continue
        model.create_entity(
            "IfcRelContainedInSpatialStructure",
            GlobalId=guid.new(), OwnerHistory=None, Name=None, Description=None,
            RelatedElements=elementos, RelatingStructure=pisos[nivel_id],
        )

    if informe.get("alimentador"):
        props_proyecto = {
            "Norma": project["project"]["norm"],
            "Sistema": project["project"]["system"],
            "TensionFN_V": float(project["project"]["voltage"]),
            "SeccionAlimentador_mm2": float(informe["alimentador"]["section_mm2"]),
            "DisyuntorGeneralA": int(informe["alimentador"]["breaker_a"]),
        }
        if red.get("presente"):
            props_proyecto["NodosRed"] = len(nodos_ifc)
            props_proyecto["TramosRed"] = len(tramos_ifc)
        _pset(
            model, guid, proyecto, "Pset_CADBIMElectri_Proyecto", props_proyecto
        )

    destino = Path(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    model.write(str(destino))
    return destino
