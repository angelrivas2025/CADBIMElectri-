import copy
import json
from pathlib import Path

import pytest

from core.model.loader import (
    ProjectError,
    load_project,
    reference_issues,
    schema_issues,
)

EJEMPLOS = Path(__file__).resolve().parents[2] / "examples"
RED = EJEMPLOS / "casa-red.json"


@pytest.fixture
def proyecto():
    return copy.deepcopy(load_project(RED))


def _nodo(proyecto, node_id):
    return next(n for n in proyecto["network"]["nodes"] if n["id"] == node_id)


def _tramo(proyecto, seg_id):
    return next(s for s in proyecto["network"]["segments"] if s["id"] == seg_id)


def test_ejemplo_con_red_valido(proyecto):
    assert proyecto["schemaVersion"] == "0.2"
    assert len(proyecto["network"]["nodes"]) == 8
    assert len(proyecto["network"]["segments"]) == 7
    assert schema_issues(proyecto) == []
    assert reference_issues(proyecto) == []


def test_sin_red_sigue_siendo_valido():
    simple = load_project(EJEMPLOS / "casa-simple.json")
    assert "network" not in simple
    assert reference_issues(simple) == []


def test_routes_ya_no_es_valido(proyecto):
    proyecto["routes"] = []
    assert any("routes" in i for i in schema_issues(proyecto))


def test_nodo_panel_exige_ref(proyecto):
    _nodo(proyecto, "QD1").pop("ref")
    assert any("ref" in i for i in schema_issues(proyecto))


def test_nodo_supply_no_admite_ref(proyecto):
    _nodo(proyecto, "SUP")["ref"] = "QD1"
    assert any("ref" in i for i in schema_issues(proyecto))


def test_height_es_obligatoria(proyecto):
    _nodo(proyecto, "J1").pop("height")
    assert any("height" in i for i in schema_issues(proyecto))


def test_trade_size_invalido(proyecto):
    _tramo(proyecto, "T01")["trade_size"] = "veinte"
    assert any("trade_size" in i for i in schema_issues(proyecto))


def test_waypoint_debe_tener_tres_coordenadas(proyecto):
    _tramo(proyecto, "T01")["waypoints"] = [[1, 2]]
    assert any("waypoints" in i for i in schema_issues(proyecto))


def test_detecta_nodo_duplicado(proyecto):
    proyecto["network"]["nodes"].append(dict(_nodo(proyecto, "SUP")))
    assert any("duplicado" in i for i in reference_issues(proyecto))


def test_detecta_tramo_duplicado(proyecto):
    proyecto["network"]["segments"].append(dict(_tramo(proyecto, "T01")))
    assert any("duplicado" in i for i in reference_issues(proyecto))


def test_detecta_supply_faltante(proyecto):
    _nodo(proyecto, "SUP")["type"] = "junction"
    assert any("supply" in i for i in reference_issues(proyecto))


def test_detecta_supply_duplicado(proyecto):
    extra = dict(_nodo(proyecto, "SUP"))
    extra["id"] = "SUP2"
    proyecto["network"]["nodes"].append(extra)
    assert any("supply" in i for i in reference_issues(proyecto))


def test_detecta_tramo_con_extremo_inexistente(proyecto):
    _tramo(proyecto, "T03")["to"] = "NOEXISTE"
    assert any("NOEXISTE" in i for i in reference_issues(proyecto))


def test_detecta_tramo_consigo_mismo(proyecto):
    _tramo(proyecto, "T03")["to"] = "J1"
    assert any("consigo mismo" in i for i in reference_issues(proyecto))


def test_tramo_entre_niveles_exige_riser(proyecto):
    proyecto["levels"].append({"id": "N1", "name": "Planta alta", "elevation": 2.8})
    _nodo(proyecto, "L-C1")["level"] = "N1"
    _tramo(proyecto, "T06")["kind"] = "conduit"
    assert any("riser" in i for i in reference_issues(proyecto))


def test_riser_entre_niveles_es_valido(proyecto):
    proyecto["levels"].append({"id": "N1", "name": "Planta alta", "elevation": 2.8})
    _nodo(proyecto, "L-C1")["level"] = "N1"
    _tramo(proyecto, "T06")["kind"] = "riser"
    assert not any("riser" in i for i in reference_issues(proyecto))


def test_detecta_panel_sin_nodo(proyecto):
    proyecto["network"]["nodes"].remove(_nodo(proyecto, "QD1"))
    assert any("sin nodo panel" in i for i in reference_issues(proyecto))


def test_detecta_panel_con_nivel_distinto(proyecto):
    proyecto["levels"].append({"id": "N1", "name": "Planta alta", "elevation": 2.8})
    _nodo(proyecto, "QD1")["level"] = "N1"
    assert any("está en nivel" in i for i in reference_issues(proyecto))


def test_detecta_carga_con_circuito_inexistente(proyecto):
    _nodo(proyecto, "L-C1")["ref"] = "C99"
    assert any("C99" in i for i in reference_issues(proyecto))


def test_detecta_circuito_con_dos_cargas(proyecto):
    extra = dict(_nodo(proyecto, "L-C1"))
    extra["id"] = "L-C1B"
    proyecto["network"]["nodes"].append(extra)
    assert any("2 nodos load" in i for i in reference_issues(proyecto))


def test_detecta_circuito_sin_carga(proyecto):
    proyecto["network"]["nodes"].remove(_nodo(proyecto, "L-C1"))
    assert any("circuito 'C1' sin nodo load" in i for i in reference_issues(proyecto))


def test_load_project_rechaza_red_invalida(tmp_path, proyecto):
    _tramo(proyecto, "T01")["from"] = "NOEXISTE"
    ruta = tmp_path / "invalido.json"
    ruta.write_text(json.dumps(proyecto), encoding="utf-8")
    with pytest.raises(ProjectError):
        load_project(ruta)
