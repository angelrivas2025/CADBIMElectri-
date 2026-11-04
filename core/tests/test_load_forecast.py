import copy
from pathlib import Path

import pytest

from core.calc.load_forecast import (
    area_perimetro,
    prever_ambiente,
    prever_iluminacion,
    prever_tug,
    previsao_cargas,
    validar_puntos_minimos,
)
from core.model.loader import load_project

EJEMPLO = Path(__file__).resolve().parents[2] / "examples" / "casa-simple.json"


def test_area_y_perimetro_de_un_rectangulo():
    area, perimetro = area_perimetro([[0, 0], [4, 0], [4, 3.5], [0, 3.5]])
    assert area == pytest.approx(14.0)
    assert perimetro == pytest.approx(15.0)


def test_area_de_un_poligono_en_l():
    area, perimetro = area_perimetro([[0, 0], [4, 0], [4, 2], [2, 2], [2, 4], [0, 4]])
    assert area == pytest.approx(12.0)
    assert perimetro == pytest.approx(16.0)


def test_poligono_degenerado():
    with pytest.raises(ValueError):
        area_perimetro([[0, 0], [1, 1]])


@pytest.mark.parametrize(
    "area,esperado",
    [(4, 100), (6, 100), (9, 100), (10, 160), (11, 160), (14, 220), (18, 280)],
)
def test_prevision_de_iluminacion(area, esperado):
    assert prever_iluminacion(area) == esperado


def test_prevision_de_tug_en_ambiente_seco():
    assert prever_tug("sala", 5, 9) == {"points": 1, "power_va": 100}
    assert prever_tug("sala", 14, 15) == {"points": 3, "power_va": 300}


def test_prevision_de_tug_en_cocina():
    assert prever_tug("cocina", 12, 14) == {"points": 4, "power_va": 1900}
    assert prever_tug("servicio", 4, 6) == {"points": 2, "power_va": 1200}


def test_prevision_de_tug_en_banos_y_garaje():
    assert prever_tug("bano", 3, 6) == {"points": 1, "power_va": 600}
    assert prever_tug("garaje", 12, 14) == {"points": 1, "power_va": 100}


def test_exterior_sin_minimo():
    assert prever_tug("externo", 20, 18) == {"points": 0, "power_va": 0}


def test_prevision_del_ejemplo():
    r = previsao_cargas(load_project(EJEMPLO))
    por_id = {a["room"]: a for a in r["rooms"]}
    assert por_id["R1"]["area_m2"] == 14.0
    assert por_id["R1"]["lighting_va"] == 220
    assert por_id["R1"]["tug_va"] == 300
    assert por_id["R2"]["lighting_va"] == 160
    assert por_id["R3"]["tug_va"] == 1900
    assert r["total_lighting_va"] == 540
    assert r["total_tug_va"] == 2500
    assert r["warnings"] == []


def test_el_ejemplo_no_cumple_los_minimos():
    problemas = validar_puntos_minimos(load_project(EJEMPLO))
    texto = " | ".join(problemas)
    assert "R1" in texto and "mínimo es 3" in texto
    assert "R3" in texto


def test_proyecto_que_cumple_los_minimos():
    p = copy.deepcopy(load_project(EJEMPLO))
    p["points"] = []
    specs = {
        "R1": (220, [100, 100, 100]),
        "R2": (160, [100, 100, 100]),
        "R3": (160, [600, 600, 600, 100]),
    }
    n = 0
    for room, (luz, tugs) in specs.items():
        n += 1
        p["points"].append(
            {"id": f"L{n}", "type": "luminaria", "room": room, "position": [0, 0], "power": luz, "circuit": "C1"}
        )
        for _ in tugs:
            n += 1
            p["points"].append(
                {"id": f"T{n}", "type": "tug", "room": room, "position": [0, 0], "power": _, "circuit": "C2"}
            )
    assert validar_puntos_minimos(p) == []
