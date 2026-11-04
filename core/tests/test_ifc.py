from pathlib import Path

import pytest

from core.calc.validate import validar_proyecto
from core.model.loader import load_project
from exporters.ifc import modelo_ifc

EJEMPLOS = Path(__file__).resolve().parents[2] / "examples"
CONFORME = EJEMPLOS / "casa-conforme.json"
RED = EJEMPLOS / "casa-red.json"


@pytest.fixture(scope="module")
def modelo(tmp_path_factory):
    ifcopenshell = pytest.importorskip("ifcopenshell")
    project = load_project(CONFORME)
    informe = validar_proyecto(project)
    ruta = modelo_ifc(project, informe, tmp_path_factory.mktemp("ifc") / "modelo.ifc")
    return ruta, ifcopenshell.open(str(ruta))


@pytest.fixture(scope="module")
def modelo_red(tmp_path_factory):
    ifcopenshell = pytest.importorskip("ifcopenshell")
    project = load_project(RED)
    informe = validar_proyecto(project)
    ruta = modelo_ifc(project, informe, tmp_path_factory.mktemp("ifc_red") / "modelo.ifc")
    return ruta, ifcopenshell.open(str(ruta))


def _props(model, objeto, nombre_pset):
    for relacion in model.by_type("IfcRelDefinesByProperties"):
        pset = relacion.RelatingPropertyDefinition
        if pset.Name == nombre_pset and objeto in relacion.RelatedObjects:
            return {
                p.Name: p.NominalValue.wrappedValue for p in pset.HasProperties
            }
    return {}


def _sin_errores(model):
    import ifcopenshell.validate

    registro = ifcopenshell.validate.json_logger()
    ifcopenshell.validate.validate(model, registro, express_rules=True)
    return registro.statements


def test_archivo_ifc4_valido(modelo):
    ruta, model = modelo
    assert ruta.read_text(encoding="utf-8").startswith("ISO-10303-21;")
    assert model.schema == "IFC4"
    assert len(model.by_type("IfcProject")) == 1


def test_jerarquia_espacial_y_ambientes(modelo):
    _, model = modelo
    assert len(model.by_type("IfcSite")) == 1
    assert len(model.by_type("IfcBuilding")) == 1
    assert len(model.by_type("IfcBuildingStorey")) == 1
    assert sorted(s.Name for s in model.by_type("IfcSpace")) == [
        "Cocina", "Dormitorio", "Sala"
    ]


def test_puntos_y_tablero_sin_duplicados(modelo):
    _, model = modelo
    assert len(model.by_type("IfcElectricDistributionBoard")) == 1
    assert len(model.by_type("IfcOutlet")) == 10
    assert len(model.by_type("IfcLightFixture")) == 3
    for espacio in model.by_type("IfcSpace"):
        assert espacio.Representation is not None
        assert espacio.Representation.Representations[0].RepresentationType == "SweptSolid"


def test_circuitos_con_propiedades_de_calculo(modelo):
    _, model = modelo
    circuitos = model.by_type("IfcDistributionCircuit")
    assert len(circuitos) == 3
    por_descripcion = {c.Description: c for c in circuitos}
    c3 = por_descripcion["Circuito C3"]
    assert c3.PredefinedType == "ELECTRICAL"
    psets = {
        (r.RelatingPropertyDefinition.Name, r.RelatingPropertyDefinition)
        for r in model.by_type("IfcRelDefinesByProperties")
        if c3 in r.RelatedObjects
    }
    props = {
        p.Name: p.NominalValue.wrappedValue
        for _, pset in psets for p in pset.HasProperties
    }
    assert props["Identificador"] == "C3"
    assert props["Seccion_mm2"] == 2.5
    assert props["DR_30mA"] is True


def test_global_ids_unicos(modelo):
    _, model = modelo
    guids = [e.GlobalId for e in model.by_type("IfcRoot")]
    assert len(guids) == len(set(guids))


def test_contencion_y_asignacion_a_circuitos(modelo):
    _, model = modelo
    for relacion in model.by_type("IfcRelContainedInSpatialStructure"):
        assert relacion.RelatingStructure.is_a("IfcBuildingStorey")
    assert len(model.by_type("IfcRelAssignsToGroup")) == 3


def test_espacios_agregados_al_nivel(modelo):
    _, model = modelo
    espacios = set(model.by_type("IfcSpace"))
    agregados = set()
    for relacion in model.by_type("IfcRelAggregates"):
        if relacion.RelatingObject.is_a("IfcBuildingStorey"):
            agregados.update(relacion.RelatedObjects)
    assert espacios <= agregados
    for relacion in model.by_type("IfcRelContainedInSpatialStructure"):
        assert not any(o.is_a("IfcSpace") for o in relacion.RelatedElements)


def test_modelo_sin_errores_de_reglas(modelo):
    _, model = modelo
    assert _sin_errores(model) == []


def test_sin_red_no_se_crean_elementos_de_red(modelo):
    _, model = modelo
    assert len(model.by_type("IfcCableCarrierSegment")) == 0
    assert len(model.by_type("IfcJunctionBox")) == 0
    assert len(model.by_type("IfcDistributionPort")) == 0


def test_red_nodos_tramos_y_puertos(modelo_red):
    _, model = modelo_red
    assert len(model.by_type("IfcCableCarrierSegment")) == 7
    assert len(model.by_type("IfcJunctionBox")) == 7
    assert len(model.by_type("IfcElectricDistributionBoard")) == 1
    assert len(model.by_type("IfcDistributionPort")) == 28
    assert len(model.by_type("IfcRelConnectsPortToElement")) == 28
    assert len(model.by_type("IfcRelConnectsPorts")) == 14
    assert _sin_errores(model) == []


def test_tramos_con_propiedades_de_red(modelo_red):
    _, model = modelo_red
    tramos = {t.Tag: t for t in model.by_type("IfcCableCarrierSegment")}
    t02 = tramos["T02"]
    assert t02.PredefinedType == "CONDUITSEGMENT"
    props = _props(model, t02, "Pset_CADBIMElectri_Tramo")
    assert props["Identificador"] == "T02"
    assert props["Tipo"] == "conduit"
    assert props["MedidaComercial"] == "25"
    assert props["LongitudM"] == pytest.approx(2.48, abs=0.01)
    assert props["Circuitos"] == "C1, C2, C3"
    assert props["NCircuitos"] == 3
    assert props["Nivel"] == "N0"
    t01 = tramos["T01"]
    assert _props(model, t01, "Pset_CADBIMElectri_Tramo")["Circuitos"] == ""


def test_nodos_con_propiedades_de_red(modelo_red):
    _, model = modelo_red
    nodos = {
        n.Tag: n for n in model.by_type("IfcJunctionBox")
    }
    assert sorted(nodos) == ["J1", "J2", "J3", "L-C1", "L-C2", "L-C3", "SUP"]
    assert _props(model, nodos["SUP"], "Pset_CADBIMElectri_NodoRed") == {
        "Tipo": "supply",
        "Referencia": "SUP",
        "Nivel": "N0",
        "AlturaM": pytest.approx(1.2),
    }
    assert _props(model, nodos["L-C1"], "Pset_CADBIMElectri_NodoRed")["Referencia"] == "C1"
    assert _props(model, nodos["L-C1"], "Pset_CADBIMElectri_NodoRed")["Tipo"] == "load"


def test_tramos_asignados_a_cada_circuito(modelo_red):
    _, model = modelo_red
    asignados = {}
    for relacion in model.by_type("IfcRelAssignsToGroup"):
        if relacion.RelatingGroup.is_a("IfcDistributionCircuit"):
            circuito = next(
                c for c in model.by_type("IfcDistributionCircuit")
                if c.Description == relacion.RelatingGroup.Description
            )
            nombres = {
                o.Tag for o in relacion.RelatedObjects
                if o.is_a("IfcCableCarrierSegment")
            }
            asignados[circuito.Description] = nombres
    assert asignados["Circuito C1"] == {"T02", "T04", "T06"}
    assert asignados["Circuito C2"] == {"T02", "T03", "T05"}
    assert asignados["Circuito C3"] == {"T02", "T04", "T07"}


def test_conectividad_de_puertos(modelo_red):
    _, model = modelo_red
    elemento_por_puerto = {
        r.RelatingPort: r.RelatedElement
        for r in model.by_type("IfcRelConnectsPortToElement")
    }
    for relacion in model.by_type("IfcRelConnectsPorts"):
        assert relacion.RelatingPort in elemento_por_puerto
        assert relacion.RelatedPort in elemento_por_puerto
        tipos = {
            elemento_por_puerto[relacion.RelatingPort].is_a(),
            elemento_por_puerto[relacion.RelatedPort].is_a(),
        }
        assert "IfcCableCarrierSegment" in tipos

    por_elemento = {}
    for puerto, elemento in elemento_por_puerto.items():
        por_elemento.setdefault(elemento, set()).add(puerto)
    for tramo in model.by_type("IfcCableCarrierSegment"):
        puertos = por_elemento[tramo]
        assert len(puertos) == 2
        assert {p.FlowDirection for p in puertos} == {"NOTDEFINED"}
        assert {p.PredefinedType for p in puertos} == {"CABLECARRIER"}

    nodos = {n.Tag: n for n in model.by_type("IfcJunctionBox")}
    flujos = {
        p.FlowDirection for p in por_elemento[nodos["SUP"]]
    }
    assert flujos == {"SOURCE"}
    assert {p.FlowDirection for p in por_elemento[nodos["L-C1"]]} == {"SINK"}
