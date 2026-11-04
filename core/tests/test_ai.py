import copy
import json
from pathlib import Path

import pytest

from ai import Agente
from ai.__main__ import main, proyecto_nuevo
from ai.tools import CATALOGO, ErrorHerramienta, describir, ejecutar
from core.calc.validate import validar_proyecto
from core.model.loader import load_project

EJEMPLOS = Path(__file__).resolve().parents[2] / "examples"
CONFORME = EJEMPLOS / "casa-conforme.json"


@pytest.fixture()
def agente():
    return Agente(load_project(CONFORME))


def _plan_casa() -> list[dict]:
    luminarias = [
        ("P1", "R1", [2, 1.75], 220),
        ("P2", "R2", [5.75, 1.75], 160),
        ("P6", "R3", [2, 5], 160),
    ]
    tomas = [
        ("P3", "R1", [0.2, 1.75], 100, "C2"),
        ("P7", "R1", [3.8, 1.75], 100, "C2"),
        ("P8", "R1", [2, 0.2], 100, "C2"),
        ("P9", "R2", [4.2, 1.75], 100, "C2"),
        ("P10", "R2", [7.3, 1.75], 100, "C2"),
        ("P11", "R2", [5.75, 0.2], 100, "C2"),
        ("P4", "R3", [0.2, 5], 600, "C3"),
        ("P12", "R3", [1.5, 5], 600, "C3"),
        ("P13", "R3", [3, 5], 600, "C3"),
        ("P14", "R3", [3.8, 6.3], 100, "C3"),
    ]
    plan = [
        {
            "tool": "set_supply",
            "arguments": {
                "type": "aerea",
                "thunderstorm_days": 60,
                "exposed_parts": False,
                "has_lightning_rod": False,
                "sensitive_equipment": True,
                "icc_ka": 3,
                "feeder_length_m": 12,
                "feeder_method": "D",
            },
        },
        {"tool": "add_panel", "arguments": {"id": "QD1", "name": "Tablero principal"}},
        {
            "tool": "add_room",
            "arguments": {
                "id": "R1", "name": "Sala", "type": "sala",
                "polygon": [[0, 0], [4, 0], [4, 3.5], [0, 3.5]],
            },
        },
        {
            "tool": "add_room",
            "arguments": {
                "id": "R2", "name": "Dormitorio", "type": "dormitorio",
                "polygon": [[4, 0], [7.5, 0], [7.5, 3.5], [4, 3.5]],
            },
        },
        {
            "tool": "add_room",
            "arguments": {
                "id": "R3", "name": "Cocina", "type": "cocina",
                "polygon": [[0, 3.5], [4, 3.5], [4, 6.5], [0, 6.5]],
            },
        },
    ]
    for cid, nombre, tipo, longitud in [
        ("C1", "Iluminación", "iluminacion", 18),
        ("C2", "TUG sala y dormitorio", "tug", 22),
        ("C3", "TUG cocina", "tug", 16),
    ]:
        plan.append(
            {
                "tool": "create_circuit",
                "arguments": {
                    "id": cid, "name": nombre, "type": tipo, "panel": "QD1",
                    "phase": "A", "method": "B1", "length_m": longitud,
                    "n_loaded": 2,
                },
            }
        )
    for pid, room, position, power in luminarias:
        plan.append(
            {
                "tool": "place_point",
                "arguments": {
                    "id": pid, "type": "luminaria", "room": room,
                    "position": position, "height": 2.6, "power": power,
                    "circuit": "C1",
                },
            }
        )
    for pid, room, position, power, circuit in tomas:
        plan.append(
            {
                "tool": "place_point",
                "arguments": {
                    "id": pid, "type": "tug", "room": room,
                    "position": position, "height": 1.1 if room == "R3" else 0.3,
                    "power": power, "circuit": circuit,
                },
            }
        )
    plan.append(
        {
            "tool": "place_point",
            "arguments": {
                "id": "P5", "type": "tablero", "room": "R1",
                "position": [0.2, 0.3], "height": 1.5,
            },
        }
    )
    return plan


def test_catalogo_con_esquemas_cerrados():
    assert set(CATALOGO) == {
        "add_level",
        "add_panel",
        "add_room",
        "assign_to_circuit",
        "create_circuit",
        "export",
        "get_project_summary",
        "place_point",
        "run_validation",
        "set_project",
        "set_supply",
        "update_room",
    }
    descritas = describir()
    assert [h["name"] for h in descritas] == sorted(CATALOGO)
    for herramienta in descritas:
        assert herramienta["description"]
        assert herramienta["parameters"]["type"] == "object"
        assert herramienta["parameters"]["additionalProperties"] is False


def test_resumen_no_muta(agente):
    antes = copy.deepcopy(agente.proyecto)
    resumen = ejecutar(agente.proyecto, "get_project_summary", {})
    assert resumen["ambientes"] == 3
    assert resumen["circuitos"] == ["C1", "C2", "C3"]
    assert resumen["puntos"]["luminaria"] == 3
    assert resumen["red"] is False
    assert agente.proyecto == antes


def test_agregar_ambiente_y_deshacer(agente):
    original = copy.deepcopy(agente.proyecto)
    agente.aplicar(
        "add_room",
        {
            "id": "R9", "name": "Varanda", "type": "externo",
            "polygon": [[7.5, 0], [9, 0], [9, 3.5], [7.5, 3.5]],
        },
    )
    assert len(agente.proyecto["rooms"]) == 4
    assert agente.historial[-1]["tool"] == "add_room"
    assert agente.proyecto["history"][-1]["author"] == "ia"
    assert agente.proyecto["history"][-1]["action"].startswith("add_room ")
    leidas = len(agente.proyecto["history"])
    agente.aplicar("get_project_summary", {})
    assert len(agente.proyecto["history"]) == leidas
    agente.deshacer()
    assert agente.proyecto == original
    assert agente.historial == []


def test_error_revierte_la_llamada(agente):
    antes = copy.deepcopy(agente.proyecto)
    with pytest.raises(ErrorHerramienta, match="duplicado"):
        agente.aplicar(
            "add_room",
            {
                "id": "R1", "name": "Otra", "type": "sala",
                "polygon": [[0, 0], [1, 0], [1, 1]],
            },
        )
    assert agente.proyecto == antes
    assert agente.historial == []

    with pytest.raises(ErrorHerramienta, match="argumentos inválidos"):
        agente.aplicar("place_point", {"id": "PX", "type": "tug", "room": "R1"})
    assert agente.proyecto == antes


def test_herramienta_desconocida(agente):
    with pytest.raises(ErrorHerramienta, match="desconocida"):
        agente.aplicar("borrar_todo", {})


def test_datos_generales_y_potencia_obligatoria(agente):
    agente.aplicar("set_project", {"voltage": 220, "system": "bifasico"})
    assert agente.proyecto["project"]["voltage"] == 220
    assert agente.proyecto["project"]["system"] == "bifasico"
    with pytest.raises(ErrorHerramienta, match="power"):
        agente.aplicar(
            "place_point",
            {"id": "PX", "type": "tug", "room": "R1", "position": [0, 0]},
        )
    assert all(p["id"] != "PX" for p in agente.proyecto["points"])


def test_plan_es_atomico(agente):
    antes = copy.deepcopy(agente.proyecto)
    plan = [
        {
            "tool": "update_room",
            "arguments": {"id": "R1", "name": "Living"},
        },
        {
            "tool": "add_room",
            "arguments": {
                "id": "R2", "name": "Otra", "type": "sala",
                "polygon": [[0, 0], [1, 0], [1, 1]],
            },
        },
    ]
    with pytest.raises(ErrorHerramienta, match="llamada 2"):
        agente.aplicar_plan(plan)
    assert agente.proyecto == antes
    assert agente.historial == []


def test_deshacer_fuera_de_rango(agente):
    with pytest.raises(ErrorHerramienta, match="no hay 1 cambio"):
        agente.deshacer()


def test_plan_crea_casa_conforme():
    agente = Agente(proyecto_nuevo("Casa simple"))
    agente.aplicar_plan(_plan_casa())
    resultado = agente.aplicar("run_validation", {})
    assert resultado["conforme"] is True
    assert resultado["errores"] == []
    assert len(resultado["circuitos"]) == 3
    for circuito in resultado["circuitos"]:
        assert circuito["breaker_a"] and circuito["section_mm2"]
        assert circuito["voltage_drop_pct"] is not None
    assert agente.proyecto["project"]["supply"]["icc_ka"] == 3


def test_sin_suministro_avisa():
    agente = Agente(proyecto_nuevo("Sin datos"))
    informe = validar_proyecto(agente.proyecto)
    assert any("no declara datos de suministro" in a for a in informe["avisos"])
    agente.aplicar("set_supply", {"icc_ka": 4.5})
    informe = validar_proyecto(agente.proyecto)
    assert not any("no declara datos de suministro" in a for a in informe["avisos"])


def test_export_svg_y_csv(agente, tmp_path):
    svg = tmp_path / "unifilar.svg"
    assert agente.aplicar("export", {"format": "svg", "path": str(svg)})["path"]
    assert svg.read_text(encoding="utf-8").lstrip().startswith("<?xml")
    csv = tmp_path / "cuadro.csv"
    agente.aplicar("export", {"format": "csv", "path": str(csv)})
    assert "ID" in csv.read_text(encoding="utf-8-sig")
    with pytest.raises(ErrorHerramienta, match="argumentos inválidos"):
        agente.aplicar("export", {"format": "qet", "path": str(tmp_path / "x.qet")})


def test_cli_aplicar_y_validar(tmp_path):
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps(_plan_casa()), encoding="utf-8")
    salida = tmp_path / "casa.json"
    assert main([
        "aplicar", str(plan), "--nuevo", "Casa simple", "--salida", str(salida),
    ]) == 0
    project = load_project(salida)
    assert len(project["rooms"]) == 3
    assert len(project["points"]) == 14
    assert main(["validar", str(salida)]) == 0


def test_cli_rechaza_plan_invalido_sin_guardar(tmp_path):
    plan = tmp_path / "plan.json"
    plan.write_text(
        json.dumps([{"tool": "add_room", "arguments": {"id": "R9"}}]),
        encoding="utf-8",
    )
    salida = tmp_path / "casa.json"
    assert main([
        "aplicar", str(plan), "--nuevo", "Casa simple", "--salida", str(salida),
    ]) == 2
    assert not salida.exists()


def test_cli_herramientas_json(capsys):
    assert main(["herramientas", "--json"]) == 0
    datos = json.loads(capsys.readouterr().out)
    assert {h["name"] for h in datos} == set(CATALOGO)
