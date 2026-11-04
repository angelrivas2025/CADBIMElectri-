import copy
from pathlib import Path

from core.calc.validate import validar_proyecto
from core.model.loader import load_project

EJEMPLO = Path(__file__).resolve().parents[2] / "examples" / "casa-simple.json"
CONFORME = Path(__file__).resolve().parents[2] / "examples" / "casa-conforme.json"


def _proyecto_completo():
    p = copy.deepcopy(load_project(EJEMPLO))
    p["points"] = []
    especificaciones = {
        "R1": (220, [100, 100, 100]),
        "R2": (160, [100, 100, 100]),
        "R3": (160, [600, 600, 600, 100]),
    }
    n = 0
    for room, (luz, tugs) in especificaciones.items():
        n += 1
        p["points"].append(
            {"id": f"L{n}", "type": "luminaria", "room": room, "position": [0, 0],
             "power": luz, "circuit": "C1"}
        )
        for poder in tugs:
            n += 1
            circuito = "C3" if room == "R3" else "C2"
            p["points"].append(
                {"id": f"T{n}", "type": "tug", "room": room, "position": [0, 0],
                 "power": poder, "circuit": circuito}
            )
    p["circuits"][0]["length_m"] = 15
    p["circuits"][1]["length_m"] = 20
    p["circuits"][2]["length_m"] = 12
    return p


def test_el_ejemplo_tiene_errores_de_minimos():
    r = validar_proyecto(load_project(EJEMPLO))
    assert r["ok"] is False
    assert any("mínimo" in e for e in r["errores"])


def test_proyecto_completo_pasa():
    r = validar_proyecto(_proyecto_completo())
    assert r["errores"] == []
    assert r["ok"] is True
    assert r["dimensionamiento"]["circuits"]
    assert r["materiales"]["items"]
    assert r["prevision"]["total_va"] == 3040


def test_resumen_incluye_las_etapas():
    r = validar_proyecto(_proyecto_completo())
    assert r["demanda"]["demanda_va"] > 0
    assert set(r["protecciones"]["dr_por_circuito"]) == {"C3"}
    assert r["prevision"]["rooms"]


def test_sin_suministro_avisa_de_dps():
    r = validar_proyecto(_proyecto_completo())
    assert any("supply" in a for a in r["avisos"])


def test_el_ejemplo_conforme_pasa_completo():
    r = validar_proyecto(load_project(CONFORME))
    assert r["errores"] == []
    assert r["ok"] is True
    assert r["prevision"]["total_va"] == 3040
    assert set(r["protecciones"]["dr_por_circuito"]) == {"C3"}
    assert r["protecciones"]["dps_clases"] == ["II", "III"]
    assert all(c["voltage_drop_pct"] < 4 for c in r["dimensionamiento"]["circuits"])


def test_alimentador_se_calcula_con_longitud_declarada():
    r = validar_proyecto(load_project(CONFORME))
    alimentador = r["alimentador"]
    assert alimentador is not None
    assert alimentador["phases"] == 2
    assert alimentador["length_m"] == 12
    assert alimentador["section_mm2"] >= 2.5
    assert alimentador["breaker_a"] >= 16
    assert alimentador["voltage_drop_pct"] < 4


def test_sin_longitud_no_hay_alimentador():
    r = validar_proyecto(load_project(EJEMPLO))
    assert r["alimentador"] is None
