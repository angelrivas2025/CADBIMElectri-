from pathlib import Path

import pytest

from core.calc.validate import validar_proyecto
from core.model.loader import load_project
from exporters.ifc import modelo_ifc

EJEMPLOS = Path(__file__).resolve().parents[2] / "examples"
CONFORME = EJEMPLOS / "casa-conforme.json"


@pytest.fixture(scope="module")
def modelo(tmp_path_factory):
    ifcopenshell = pytest.importorskip("ifcopenshell")
    project = load_project(CONFORME)
    informe = validar_proyecto(project)
    ruta = modelo_ifc(project, informe, tmp_path_factory.mktemp("ifc") / "modelo.ifc")
    return ruta, ifcopenshell.open(str(ruta))


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
