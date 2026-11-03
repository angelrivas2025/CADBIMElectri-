import copy
from pathlib import Path

from core.calc.currents import circuit_currents
from core.model.loader import load_project

EJEMPLO = Path(__file__).resolve().parents[2] / "examples" / "casa-simple.json"


def test_corrientes_del_ejemplo():
    r = circuit_currents(load_project(EJEMPLO))
    i = {c["id"]: c["current_a"] for c in r["circuits"]}
    assert i["C1"] == round(200 / 127, 2)  # 1.57 A
    assert i["C2"] == round(100 / 127, 2)  # 0.79 A
    assert i["C3"] == round(600 / 127, 2)  # 4.72 A
    assert r["warnings"] == []


def test_circuito_multifase_no_se_calcula():
    p = copy.deepcopy(load_project(EJEMPLO))
    p["circuits"][2]["phase"] = "AB"
    r = circuit_currents(p)
    c3 = next(c for c in r["circuits"] if c["id"] == "C3")
    assert c3["current_a"] is None
    assert any("C3" in w for w in r["warnings"])
