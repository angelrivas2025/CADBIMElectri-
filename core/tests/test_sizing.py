import copy
from pathlib import Path

import pytest

from core.calc.sizing import (
    dimensionar_alimentador,
    dimensionar_circuito,
    dimensionar_proyecto,
    n_conductores_cargados,
)
from core.model.loader import load_project
from core.norms.nbr5410.minimums import seccion_minima

EJEMPLO = Path(__file__).resolve().parents[2] / "examples" / "casa-simple.json"


def test_conductores_cargados_segun_fases():
    assert n_conductores_cargados(1) == 2
    assert n_conductores_cargados(2) == 2
    assert n_conductores_cargados(3) == 3


def test_minimos_por_tipo_de_circuito():
    assert seccion_minima("iluminacion") == 1.5
    assert seccion_minima("tug") == 2.5
    assert seccion_minima("tue") == 2.5
    assert seccion_minima("general") == 2.5
    assert seccion_minima("tug", "Al") == 16
    with pytest.raises(ValueError):
        seccion_minima("otro")


def test_dimensiona_un_circuito_por_minimo_normativo():
    r = dimensionar_circuito(
        corriente_a=1.57, n_fases=1, tension_fase_v=127, longitud_m=18, tipo_carga="iluminacion"
    )
    assert r["section_by_ampacity"] == 0.5
    assert r["section_mm2"] == 1.5  # mínimo de iluminación
    assert r["capacity_a"] == 17.5
    assert r["breaker_a"] == 6
    assert r["breaker_curve"] == "B"
    assert r["voltage_drop_pct"] == pytest.approx(0.673, rel=1e-2)
    assert r["warnings"] == []


def test_dimensiona_tug_en_2_5():
    r = dimensionar_circuito(
        corriente_a=4.72, n_fases=1, tension_fase_v=127, longitud_m=18, tipo_carga="tug"
    )
    assert r["section_mm2"] == 2.5
    assert r["breaker_a"] == 6


def test_la_caida_de_tension_manda():
    r = dimensionar_circuito(
        corriente_a=20, n_fases=1, tension_fase_v=127, longitud_m=40, tipo_carga="tug"
    )
    assert r["section_by_drop"] == 10
    assert r["section_mm2"] == 10
    assert r["voltage_drop_pct"] <= 4.0


def test_sin_longitud_avisa_y_no_verifica_caida():
    r = dimensionar_circuito(
        corriente_a=10, n_fases=1, tension_fase_v=127, longitud_m=None, tipo_carga="tug"
    )
    assert r["voltage_drop_pct"] is None
    assert r["section_by_drop"] is None
    assert any("longitud" in w for w in r["warnings"])


def test_trifasico_usa_tres_conductores_cargados():
    r = dimensionar_circuito(
        corriente_a=30, n_fases=3, tension_fase_v=127, longitud_m=10, tipo_carga="tue"
    )
    assert r["n_loaded"] == 3
    assert r["section_mm2"] >= 2.5


def test_material_aluminio_respeta_el_minimo_de_16():
    r = dimensionar_circuito(
        corriente_a=10, n_fases=1, tension_fase_v=127, longitud_m=5,
        tipo_carga="tug", material="Al",
    )
    assert r["section_mm2"] == 16.0


def test_dimensionamiento_del_proyecto():
    p = copy.deepcopy(load_project(EJEMPLO))
    for c in p["circuits"]:
        c["length_m"] = 18
    r = dimensionar_proyecto(p)
    por_id = {c["id"]: c for c in r["circuits"]}
    assert por_id["C1"]["section_mm2"] == 1.5
    assert por_id["C3"]["section_mm2"] == 2.5
    assert all(c["breaker_a"] == 6 for c in r["circuits"])
    assert any("Agrupamiento no declarado" in w for w in r["warnings"])


def test_dimensionamiento_usa_los_datos_del_circuito():
    p = copy.deepcopy(load_project(EJEMPLO))
    p["circuits"][0]["length_m"] = 60
    p["circuits"][0]["method"] = "B2"
    p["circuits"][0]["insulation"] = "XLPE"
    r = dimensionar_proyecto(p)
    c1 = next(c for c in r["circuits"] if c["id"] == "C1")
    assert c1["method"] == "B2"
    assert c1["insulation"] == "XLPE"
    assert c1["length_m"] == 60


def test_circuito_sin_fase_no_se_dimensiona():
    p = copy.deepcopy(load_project(EJEMPLO))
    p["circuits"][0]["phase"] = None
    r = dimensionar_proyecto(p)
    assert all(c["id"] != "C1" for c in r["circuits"])
    assert any("C1" in w for w in r["warnings"])


def test_alimentador_bifasico():
    p = load_project(EJEMPLO)
    r = dimensionar_alimentador(p, 760, longitud_m=12)
    assert r["current_a"] == round(760 / (3 ** 0.5 * 127), 2)
    assert r["section_mm2"] == 2.5
    assert r["breaker_a"] == 6
