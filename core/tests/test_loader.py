import copy
from pathlib import Path

import pytest

from core.model.loader import ProjectError, load_project, reference_issues, schema_issues

EJEMPLO = Path(__file__).resolve().parents[2] / "examples" / "casa-simple.json"


def test_ejemplo_carga_sin_errores():
    proyecto = load_project(EJEMPLO)
    assert proyecto["project"]["norm"] == "NBR5410"
    assert len(proyecto["points"]) == 5


def test_detecta_error_de_esquema():
    p = load_project(EJEMPLO)
    p["project"]["system"] = "cuatrifasico"
    assert any("system" in i for i in schema_issues(p))


def test_detecta_circuito_inexistente():
    p = copy.deepcopy(load_project(EJEMPLO))
    p["points"][0]["circuit"] = "C99"
    assert any("C99" in i for i in reference_issues(p))


def test_detecta_id_duplicado():
    p = copy.deepcopy(load_project(EJEMPLO))
    p["rooms"].append(dict(p["rooms"][0]))
    assert any("duplicado" in i for i in reference_issues(p))


def test_load_project_lanza_error(tmp_path):
    malo = tmp_path / "malo.json"
    malo.write_text('{"schemaVersion": "0.1"}', encoding="utf-8")
    with pytest.raises(ProjectError):
        load_project(malo)


def test_todos_los_ejemplos_son_validos():
    for f in sorted(EJEMPLO.parent.glob("*.json")):
        load_project(f)
