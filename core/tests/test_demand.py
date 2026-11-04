import copy
from pathlib import Path

import pytest

from core.calc.demand import ADVERTENCIA_FACTORES, FACTORES_SUGERIDOS, demanda
from core.model.loader import load_project

EJEMPLO = Path(__file__).resolve().parents[2] / "examples" / "casa-simple.json"


def test_demanda_con_factores_sugeridos():
    r = demanda(load_project(EJEMPLO))
    # 200 VA de iluminación al 100 % + 700 VA de TUG al 80 %.
    assert r["instalada_va"] == 900
    assert r["demanda_va"] == 760
    assert r["factor_global"] == 0.844
    assert ADVERTENCIA_FACTORES in r["warnings"]


def test_factores_propios_no_avisan_del_origen():
    r = demanda(load_project(EJEMPLO), {"iluminacion": 0.5, "tug": 1.0, "tue": 1.0})
    assert r["demanda_va"] == 800
    assert ADVERTENCIA_FACTORES not in r["warnings"]


def test_tipo_sin_factor_usa_uno():
    p = copy.deepcopy(load_project(EJEMPLO))
    p["circuits"][0]["type"] = "tue"
    r = demanda(p, {"iluminacion": 1.0, "tug": 0.8})
    assert any("sin factor" in w for w in r["warnings"])
    assert r["demanda_va"] == 200 + 700 * 0.8


def test_factor_invalido():
    with pytest.raises(ValueError):
        demanda(load_project(EJEMPLO), {"tug": 1.5})


def test_sin_circuitos():
    p = copy.deepcopy(load_project(EJEMPLO))
    p["circuits"] = []
    p["points"] = [pt for pt in p["points"] if pt["type"] == "tablero"]
    r = demanda(p)
    assert r["instalada_va"] == 0
    assert r["factor_global"] is None


def test_los_factores_sugeridos_son_razonables():
    assert set(FACTORES_SUGERIDOS) == {"iluminacion", "tug", "tue"}
