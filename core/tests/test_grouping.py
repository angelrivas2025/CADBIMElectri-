import copy
from pathlib import Path

from core.calc.grouping import (
    recomendaciones_agrupamiento,
    sugerir_circuitos,
    validar_agrupamiento,
)
from core.model.loader import load_project

EJEMPLO = Path(__file__).resolve().parents[2] / "examples" / "casa-simple.json"


def test_el_ejemplo_agrupa_correctamente():
    assert validar_agrupamiento(load_project(EJEMPLO)) == []


def test_detecta_iluminacion_mezclada_con_tug():
    p = copy.deepcopy(load_project(EJEMPLO))
    p["points"][2]["circuit"] = "C1"  # P3 (tug) al circuito de iluminación
    problemas = " | ".join(validar_agrupamiento(p))
    assert "C1" in problemas and "tug" in problemas


def test_detecta_cocina_compartiendo_circuito():
    p = copy.deepcopy(load_project(EJEMPLO))
    p["points"][2]["circuit"] = "C3"  # P3 (sala) al circuito de la cocina
    problemas = " | ".join(validar_agrupamiento(p))
    assert "exclusivo" in problemas


def test_detecta_dos_tue_en_un_circuito():
    p = copy.deepcopy(load_project(EJEMPLO))
    for i, room in enumerate(("R1", "R3"), start=1):
        p["points"].append(
            {"id": f"E{i}", "type": "tue", "room": room, "position": [0, 0], "power": 3000, "circuit": "C9"}
        )
    p["circuits"].append({"id": "C9", "name": "TUE", "type": "tue", "panel": "QD1", "phase": "B"})
    problemas = " | ".join(validar_agrupamiento(p))
    assert "2 TUE" in problemas


def test_exige_un_circuito_por_cada_60_m2():
    p = copy.deepcopy(load_project(EJEMPLO))
    p["rooms"].append(
        {"id": "R9", "level": "N0", "name": "Salón grande", "type": "sala",
         "polygon": [[0, 0], [20, 0], [20, 10], [0, 10]]}
    )  # 200 m² más: el total pasa de 238 m² -> 4 circuitos
    problemas = " | ".join(validar_agrupamiento(p))
    assert "el mínimo es 4" in problemas


def test_recomienda_no_superar_ocho_puntos():
    p = copy.deepcopy(load_project(EJEMPLO))
    for i in range(9):
        p["points"].append(
            {"id": f"X{i}", "type": "luminaria", "room": "R1", "position": [0, 0], "power": 10, "circuit": "C1"}
        )
    assert any("C1" in a for a in recomendaciones_agrupamiento(p))


def test_propuesta_de_circuitos_del_ejemplo():
    p = load_project(EJEMPLO)
    propuesta = sugerir_circuitos(p)
    tipos = [(c["type"], c["phase"]) for c in propuesta["circuits"]]
    assert len(tipos) == 3
    assert tipos[0][0] == "iluminacion"
    assert tipos[1][0] == "tug"  # cocina, antes que las tomas generales
    assert propuesta["assignments"]["P1"] == "C1"
    assert propuesta["assignments"]["P4"] == "C2"
    assert propuesta["assignments"]["P5"] is None  # tablero


def test_la_propuesta_cumple_las_reglas():
    p = copy.deepcopy(load_project(EJEMPLO))
    propuesta = sugerir_circuitos(p)
    p["circuits"] = propuesta["circuits"]
    for punto in p["points"]:
        punto["circuit"] = propuesta["assignments"][punto["id"]]
    assert validar_agrupamiento(p) == []
    assert recomendaciones_agrupamiento(p) == []


def test_propuesta_en_trifasico_reparte_fases():
    p = copy.deepcopy(load_project(EJEMPLO))
    p["project"]["system"] = "trifasico"
    for i, room in enumerate(("R1", "R2", "R3"), start=1):
        p["points"].append(
            {"id": f"E{i}", "type": "tue", "room": room, "position": [0, 0], "power": 2000, "circuit": None}
        )
    propuesta = sugerir_circuitos(p)
    fases_usadas = {c["phase"] for c in propuesta["circuits"]}
    assert fases_usadas == {"A", "B", "C"}
    tues = [c for c in propuesta["circuits"] if c["type"] == "tue"]
    assert len(tues) == 3
    assert len({c["phase"] for c in tues}) == 3
