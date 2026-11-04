import copy
from pathlib import Path

import pytest

from core.calc.bom import lista_materiales
from core.calc.sizing import dimensionar_proyecto
from core.model.loader import load_project

EJEMPLO = Path(__file__).resolve().parents[2] / "examples" / "casa-simple.json"


def _proyecto_con_longitudes(metros=18):
    p = copy.deepcopy(load_project(EJEMPLO))
    for c in p["circuits"]:
        c["length_m"] = metros
    return p


def test_lista_de_materiales_del_ejemplo():
    p = _proyecto_con_longitudes()
    r = lista_materiales(p, dimensionar_proyecto(p))
    por_tipo = {}
    for item in r["items"]:
        por_tipo.setdefault(item["tipo"], []).append(item)
    assert any("1.5 mm²" in i["descripcion"] for i in por_tipo["cable"])
    assert any(i["cantidad"] == 36 and "2.5 mm²" in i["descripcion"] for i in por_tipo["cable"])
    assert por_tipo["disyuntor"][0]["cantidad"] == 3
    assert por_tipo["dr"][0]["cantidad"] == 1  # solo la cocina
    assert por_tipo["tablero"][0]["cantidad"] == 1
    assert "dps" not in por_tipo


def test_margen_de_desperdicio():
    p = _proyecto_con_longitudes(10)
    base = lista_materiales(p, dimensionar_proyecto(p))
    con_margen = lista_materiales(p, dimensionar_proyecto(p), margen_percent=10)
    total_base = sum(i["cantidad"] for i in base["items"] if i["tipo"] == "cable")
    total_margen = sum(i["cantidad"] for i in con_margen["items"] if i["tipo"] == "cable")
    assert total_margen == pytest.approx(total_base * 1.1)


def test_sin_longitud_no_hay_cable():
    p = load_project(EJEMPLO)
    r = lista_materiales(p, dimensionar_proyecto(p))
    assert not [i for i in r["items"] if i["tipo"] == "cable"]
    assert any("sin longitud" in w for w in r["warnings"])


def test_dps_en_la_lista():
    p = _proyecto_con_longitudes()
    p["project"]["supply"] = {"type": "aerea", "thunderstorm_days": 45}
    r = lista_materiales(p, dimensionar_proyecto(p))
    dps = [i for i in r["items"] if i["tipo"] == "dps"]
    assert len(dps) == 1 and "clase II" in dps[0]["descripcion"]


def test_margen_negativo():
    p = load_project(EJEMPLO)
    with pytest.raises(ValueError):
        lista_materiales(p, dimensionar_proyecto(p), margen_percent=-5)
