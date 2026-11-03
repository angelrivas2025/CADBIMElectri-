import copy
from pathlib import Path

from core.calc.load_schedule import load_schedule
from core.model.loader import load_project

EJEMPLO = Path(__file__).resolve().parents[2] / "examples" / "casa-simple.json"


def test_cuadro_de_cargas_del_ejemplo():
    r = load_schedule(load_project(EJEMPLO))
    por_id = {c["id"]: c for c in r["circuits"]}
    assert por_id["C1"]["power_va"] == 200 and por_id["C1"]["points"] == 2
    assert por_id["C2"]["power_va"] == 100
    assert por_id["C3"]["power_va"] == 600
    assert r["by_phase_va"] == {"A": 800.0, "B": 100.0}
    assert r["total_va"] == 900
    assert r["imbalance_pct"] == 87.5
    assert r["warnings"] == []


def test_avisa_punto_sin_circuito():
    p = copy.deepcopy(load_project(EJEMPLO))
    p["points"][0]["circuit"] = None
    r = load_schedule(p)
    assert any("P1" in w for w in r["warnings"])


def test_circuito_en_dos_fases_reparte_por_igual():
    p = copy.deepcopy(load_project(EJEMPLO))
    p["circuits"][2]["phase"] = "AB"  # C3: 600 VA
    r = load_schedule(p)
    assert r["by_phase_va"] == {"A": 500.0, "B": 400.0}


def test_fase_inexistente_en_el_sistema():
    p = copy.deepcopy(load_project(EJEMPLO))
    p["circuits"][0]["phase"] = "C"  # el sistema es bifásico
    r = load_schedule(p)
    assert any("no existen" in w for w in r["warnings"])
