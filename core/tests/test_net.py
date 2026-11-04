import copy
from pathlib import Path

import pytest

from core.calc.bom import lista_materiales
from core.calc.sizing import dimensionar_proyecto
from core.calc.validate import validar_proyecto
from core.model.loader import load_project, reference_issues
from core.net.graph import RedInvalida, construir_grafo
from core.net.occupancy import conductores_por_circuito, verificar_ocupacion
from core.net.report import analizar_red
from core.net.routing import camino_minimo

EJEMPLOS = Path(__file__).resolve().parents[2] / "examples"
RED = EJEMPLOS / "casa-red.json"
SIMPLE = EJEMPLOS / "casa-simple.json"


@pytest.fixture
def proyecto():
    return copy.deepcopy(load_project(RED))


def _dimensionado(proyecto, red=None):
    red = red or analizar_red(proyecto)
    return dimensionar_proyecto(proyecto, red=red["por_circuito"])


def _tablas(tmp_path, *, diametros=((1.5, 3.0), (2.5, 3.8)), limites=((1, 8, 40.0),)):
    (tmp_path / "conductores_diametros.csv").write_text(
        "material,aislacion,seccion_mm2,diametro_mm\n"
        + "\n".join(f"Cu,PVC,{s:g},{d:g}" for s, d in diametros)
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "electrodutos_diametros.csv").write_text(
        "designacion,diametro_interno_mm\n20,14\n25,18\n32,24\n",
        encoding="utf-8",
    )
    (tmp_path / "limites_ocupacion.csv").write_text(
        "n_conductores_min,n_conductores_max,limite_pct\n"
        + "\n".join(f"{a},{b},{pct:g}" for a, b, pct in limites)
        + "\n",
        encoding="utf-8",
    )


def test_rutas_y_longitudes_de_circuito(proyecto):
    red = analizar_red(proyecto)
    assert red["errores"] == []
    assert red["avisos"] == []
    assert red["por_circuito"]["C1"]["segments"] == ["T02", "T04", "T06"]
    assert red["por_circuito"]["C1"]["length_m"] == pytest.approx(5.93, abs=0.01)
    assert red["por_circuito"]["C2"]["length_m"] == pytest.approx(8.84, abs=0.01)
    assert red["por_circuito"]["C3"]["length_m"] == pytest.approx(8.3, abs=0.01)


def test_ruteo_es_reproducible(proyecto):
    assert analizar_red(proyecto) == analizar_red(proyecto)


def test_agrupamiento_por_tramo(proyecto):
    red = analizar_red(proyecto)
    assert red["por_tramo"]["T02"]["n_circuits"] == 3
    assert red["por_tramo"]["T02"]["circuits"] == ["C1", "C2", "C3"]
    assert red["por_tramo"]["T06"]["n_circuits"] == 1
    assert {c["grouped_circuits"] for c in red["por_circuito"].values()} == {3}


def test_sin_red_no_hay_resultado(proyecto):
    sin_red = load_project(SIMPLE)
    red = analizar_red(sin_red)
    assert red["presente"] is False
    assert red["errores"] == []
    assert red["por_circuito"] == {}


def test_dijkstra_desempata_por_id_de_tramo():
    base = {
        "network": {
            "nodes": [
                {"id": "A", "type": "supply", "level": "N0", "position": [0, 0], "height": 0},
                {"id": "B", "type": "junction", "level": "N0", "position": [1, 0], "height": 0},
                {"id": "C", "type": "load", "level": "N0", "position": [2, 0], "height": 0},
            ],
            "segments": [
                {"id": "S1", "from": "A", "to": "B", "kind": "conduit", "trade_size": "20"},
                {"id": "S2", "from": "B", "to": "C", "kind": "conduit", "trade_size": "20"},
                {"id": "Z9", "from": "A", "to": "C", "kind": "conduit", "trade_size": "20"},
            ],
        }
    }
    grafo = construir_grafo(base)
    ruta = camino_minimo(grafo, "A", "C")
    assert ruta["segments"] == ["S1", "S2"]
    assert ruta["length_m"] == pytest.approx(2.0)

    base["network"]["segments"][2]["id"] = "A0"
    grafo = construir_grafo(base)
    assert camino_minimo(grafo, "A", "C")["segments"] == ["A0"]


def test_grafo_rechaza_arista_sin_extremo():
    with pytest.raises(RedInvalida):
        construir_grafo(
            {
                "network": {
                    "nodes": [
                        {"id": "A", "type": "supply", "level": "N0", "position": [0, 0], "height": 0}
                    ],
                    "segments": [
                        {"id": "S1", "from": "A", "to": "B", "kind": "conduit", "trade_size": "20"}
                    ],
                }
            }
        )


def test_red_desconectada_reporta_error(proyecto):
    proyecto["network"]["segments"] = [
        s for s in proyecto["network"]["segments"] if s["id"] != "T05"
    ]
    red = analizar_red(proyecto)
    assert "C2" not in red["por_circuito"]
    assert any("sin camino" in e and "C2" in e for e in red["errores"])


def test_validate_marca_error_si_la_red_esta_desconectada(proyecto):
    proyecto["network"]["segments"] = [
        s for s in proyecto["network"]["segments"] if s["id"] != "T05"
    ]
    resultado = validar_proyecto(proyecto)
    assert resultado["ok"] is False
    assert any("sin camino" in e and "C2" in e for e in resultado["errores"])


def test_avisa_si_la_longitud_declarada_difiere(proyecto):
    proyecto["circuits"][0]["length_m"] = 10.0
    red = analizar_red(proyecto)
    assert red["por_circuito"]["C1"]["length_m"] == pytest.approx(5.93, abs=0.01)
    assert red["por_circuito"]["C1"]["difference_pct"] == pytest.approx(40.7, abs=0.2)
    assert any("circuito 'C1'" in a and "manda la red" in a for a in red["avisos"])


def test_c01_subcuadro_con_prumada(proyecto):
    proyecto["levels"].append({"id": "N1", "name": "Planta alta", "elevation": 2.8})
    proyecto["panels"].append({"id": "QD2", "name": "Tablero superior", "level": "N1"})
    proyecto["network"]["nodes"].append(
        {"id": "N-QD2", "type": "panel", "ref": "QD2", "level": "N1",
         "position": [0.2, 0.3], "height": 2.9}
    )
    proyecto["network"]["segments"].append(
        {"id": "R01", "from": "QD1", "to": "N-QD2", "kind": "riser", "trade_size": "32"}
    )
    assert reference_issues(proyecto) == []

    red = analizar_red(proyecto)
    assert red["errores"] == []
    assert red["alimentadores"]["QD2"]["segments"] == ["T01", "R01"]
    assert red["alimentadores"]["QD2"]["length_m"] == pytest.approx(10.24, abs=0.01)
    assert red["alimentador_referencia"] == "QD2"
    assert any("varios tableros" in a for a in red["avisos"])


def test_c03_factor_de_agrupamiento_se_aplica(proyecto):
    resultado = validar_proyecto(proyecto)
    por_id = {c["id"]: c for c in resultado["dimensionamiento"]["circuits"]}
    assert por_id["C1"]["length_source"] == "red"
    assert por_id["C1"]["correction_factor"] == pytest.approx(0.7)
    assert all(
        c["grouped_circuits"] == 3
        for c in analizar_red(proyecto)["por_circuito"].values()
    )


def test_c05_caida_usa_longitud_de_red():
    proyecto = copy.deepcopy(load_project(SIMPLE))
    por_defecto = {c["id"]: c for c in dimensionar_proyecto(proyecto)["circuits"]}
    assert por_defecto["C1"]["length_m"] is None

    largo = {"C1": {"length_m": 120.0, "grouped_circuits": 1}}
    resultado = {c["id"]: c for c in dimensionar_proyecto(proyecto, red=largo)["circuits"]}
    c1 = resultado["C1"]
    assert c1["length_m"] == 120.0
    assert c1["length_source"] == "red"
    assert c1["section_by_drop"] >= 2.5
    assert c1["voltage_drop_pct"] < 4.0


def test_validate_usa_longitudes_y_alimentador_de_la_red(proyecto):
    resultado = validar_proyecto(proyecto)
    assert resultado["ok"] is True
    assert resultado["red"]["presente"] is True
    assert resultado["alimentador"]["length_m"] == pytest.approx(8.84, abs=0.01)
    por_id = {c["id"]: c for c in resultado["dimensionamiento"]["circuits"]}
    assert {c["length_source"] for c in por_id.values()} == {"red"}
    assert por_id["C2"]["length_m"] == pytest.approx(8.84, abs=0.01)


def test_bom_refleja_longitudes_de_red(proyecto):
    resultado = validar_proyecto(proyecto)
    cables = [i for i in resultado["materiales"]["items"] if i["tipo"] == "cable"]
    total = sum(i["cantidad"] for i in cables)
    largo_red = sum(c["length_m"] for c in resultado["dimensionamiento"]["circuits"])
    assert total == pytest.approx(largo_red, abs=0.01)

    sin_red = lista_materiales(proyecto, _dimensionado(proyecto))
    assert sum(i["cantidad"] for i in sin_red["items"] if i["tipo"] == "cable") == pytest.approx(
        total, abs=0.01
    )


def test_ocupacion_sin_tablas_no_verifica(proyecto, tmp_path):
    red = analizar_red(proyecto)
    vacio = tmp_path / "sin_tablas"
    vacio.mkdir()
    ocupacion = verificar_ocupacion(proyecto, red, _dimensionado(proyecto), data_dir=vacio)
    assert ocupacion["verificable"] is False
    assert ocupacion["tramos"] == []
    assert ocupacion["errores"] == []
    assert any("faltan las tablas" in a for a in ocupacion["avisos"])


def test_ocupacion_por_defecto_avisa_que_no_es_verificable(proyecto):
    resultado = validar_proyecto(proyecto)
    assert resultado["ok"] is True
    assert resultado["red"]["ocupacion"]["verificable"] is False
    assert any("Ocupación no verificable" in a for a in resultado["avisos"])


def test_ocupacion_con_tablas_verifica_por_tramo(proyecto, tmp_path):
    _tablas(tmp_path)
    red = analizar_red(proyecto)
    ocupacion = verificar_ocupacion(proyecto, red, _dimensionado(proyecto), data_dir=tmp_path)
    assert ocupacion["verificable"] is True
    assert ocupacion["errores"] == []
    assert {t["estado"] for t in ocupacion["tramos"]} == {"ok"}
    t02 = next(t for t in ocupacion["tramos"] if t["trade_size"] == "25")
    assert t02["n_conductores"] == 6
    assert 0 < t02["ocupacion_pct"] < 40


def test_c04_conducto_excedido_informa_siguiente_medida(proyecto, tmp_path):
    _tablas(tmp_path, diametros=((1.5, 3.5), (2.5, 4.5)))
    for tramo in proyecto["network"]["segments"]:
        if tramo["id"] == "T02":
            tramo["trade_size"] = "20"
    red = analizar_red(proyecto)
    ocupacion = verificar_ocupacion(proyecto, red, _dimensionado(proyecto), data_dir=tmp_path)
    assert ocupacion["verificable"] is True
    assert len(ocupacion["errores"]) == 1
    error = ocupacion["errores"][0]
    assert "T02" in error
    assert "C1, C2, C3" in error
    assert "Siguiente medida comercial: 25" in error
    assert any(t["estado"] == "excedido" for t in ocupacion["tramos"])


def test_ocupacion_sin_diametro_para_una_seccion_no_verifica(proyecto, tmp_path):
    _tablas(tmp_path, diametros=((1.5, 3.0),))
    red = analizar_red(proyecto)
    ocupacion = verificar_ocupacion(proyecto, red, _dimensionado(proyecto), data_dir=tmp_path)
    assert ocupacion["verificable"] is False
    assert any(t["estado"] == "no_verificable" for t in ocupacion["tramos"])
    assert any("falta diámetro" in a for a in ocupacion["avisos"])


def test_ocupacion_sin_limite_para_el_numero_de_conductores(proyecto, tmp_path):
    _tablas(tmp_path, limites=((1, 4, 40.0),))
    red = analizar_red(proyecto)
    ocupacion = verificar_ocupacion(proyecto, red, _dimensionado(proyecto), data_dir=tmp_path)
    assert ocupacion["verificable"] is False
    assert any("falta límite de ocupación para 6 conductores" in a for a in ocupacion["avisos"])


def test_conductores_por_circuito_sigue_la_convencion_del_bom():
    assert conductores_por_circuito({"phase": "A"}) == 2
    assert conductores_por_circuito({"phase": "AB"}) == 3
    assert conductores_por_circuito({"phase": "ABC"}) == 4
    assert conductores_por_circuito({"phase": None}) == 0
