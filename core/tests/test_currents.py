import copy
from math import sqrt
from pathlib import Path

import pytest

from core.calc.currents import circuit_currents, corriente_de_circuito, tension_de_servicio
from core.model.loader import load_project

EJEMPLO = Path(__file__).resolve().parents[2] / "examples" / "casa-simple.json"


def test_corrientes_del_ejemplo():
    r = circuit_currents(load_project(EJEMPLO))
    i = {c["id"]: c["current_a"] for c in r["circuits"]}
    assert i["C1"] == round(200 / 127, 2)  # 1.57 A
    assert i["C2"] == round(100 / 127, 2)  # 0.79 A
    assert i["C3"] == round(600 / 127, 2)  # 4.72 A
    assert r["warnings"] == []


def test_circuito_bifasico_usa_tension_de_linea():
    p = copy.deepcopy(load_project(EJEMPLO))
    p["circuits"][2]["phase"] = "AB"  # C3: 600 VA
    r = circuit_currents(p)
    c3 = next(c for c in r["circuits"] if c["id"] == "C3")
    assert c3["current_a"] == round(600 / (sqrt(3) * 127), 2)  # 2.73 A
    assert c3["voltage_v"] == pytest.approx(sqrt(3) * 127)
    assert c3["phases"] == 2
    assert r["warnings"] == []


def test_circuito_trifasico_usa_tres_veces_la_tension_de_fase():
    p = copy.deepcopy(load_project(EJEMPLO))
    p["project"]["system"] = "trifasico"
    p["project"]["voltage"] = 127
    p["circuits"][2]["phase"] = "ABC"
    r = circuit_currents(p)
    c3 = next(c for c in r["circuits"] if c["id"] == "C3")
    assert c3["current_a"] == round(600 / (3 * 127), 2)  # 1.57 A
    assert c3["phases"] == 3


def test_formulas_de_corriente():
    assert corriente_de_circuito(1000, 1, 127) == round(1000 / 127, 2)
    assert corriente_de_circuito(1000, 2, 127) == round(1000 / (sqrt(3) * 127), 2)
    assert corriente_de_circuito(1000, 3, 127) == round(1000 / (3 * 127), 2)
    assert tension_de_servicio(127, 1) == 127
    assert tension_de_servicio(127, 3) == pytest.approx(127 * sqrt(3))


def test_fase_inexistente_no_calcula_corriente():
    p = copy.deepcopy(load_project(EJEMPLO))
    p["circuits"][0]["phase"] = "C"  # el sistema es bifásico
    r = circuit_currents(p)
    c1 = next(c for c in r["circuits"] if c["id"] == "C1")
    assert c1["current_a"] is None
    assert any("no existen" in w for w in r["warnings"])
