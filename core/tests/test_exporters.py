import csv
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from core.calc.validate import validar_proyecto
from core.model.loader import load_project
from exporters.__main__ import main
from exporters.csv_export import cuadro_csv
from exporters.diagram import construir_unifilar
from exporters.svg import unifilar_svg

EJEMPLOS = Path(__file__).resolve().parents[2] / "examples"
CONFORME = EJEMPLOS / "casa-conforme.json"
SIMPLE = EJEMPLOS / "casa-simple.json"


@pytest.fixture(scope="module")
def proyecto_informe():
    project = load_project(CONFORME)
    return project, validar_proyecto(project)


def test_svg_es_xml_valido_y_determinista(proyecto_informe):
    project, informe = proyecto_informe
    primero = unifilar_svg(construir_unifilar(project, informe))
    segundo = unifilar_svg(construir_unifilar(project, informe))
    assert primero == segundo
    raiz = ET.fromstring(primero)
    assert raiz.tag.endswith("svg")


def test_svg_incluye_circuitos_protecciones_y_alimentador(proyecto_informe):
    project, informe = proyecto_informe
    svg = unifilar_svg(construir_unifilar(project, informe))
    assert "C1" in svg and "C3" in svg
    assert "DR 30 mA" in svg
    assert "DPS" in svg and "clase II + III" in svg
    assert "Alimentador 3x2.5 mm²" in svg
    assert "Demanda 2540 VA" in svg
    assert "1900 VA" in svg


def test_csv_tiene_una_fila_por_circuito(tmp_path, proyecto_informe):
    project, informe = proyecto_informe
    ruta = cuadro_csv(project, informe, tmp_path / "cuadro.csv")
    with ruta.open(newline="", encoding="utf-8-sig") as archivo:
        filas = list(csv.DictReader(archivo, delimiter=";"))
    assert len(filas) == 3
    c3 = next(f for f in filas if f["ID"] == "C3")
    assert c3["VA"] == "1900"
    assert c3["DR"] == "Si"
    assert c3["Seccion_mm2"] == "2.5"
    assert c3["Conductores"] == "2"
    assert c3["Caida_pct"] == "3.42"


def test_pdf_completo(tmp_path, proyecto_informe):
    pytest.importorskip("fpdf")
    from exporters.pdf import informe_pdf

    project, informe = proyecto_informe
    ruta = informe_pdf(project, informe, tmp_path / "informe.pdf")
    datos = ruta.read_bytes()
    assert datos.startswith(b"%PDF-")
    assert datos.count(b"/Type /Page") >= 5
    assert len(datos) > 4000


def test_cli_exporta_las_tres_salidas(tmp_path):
    destino = tmp_path / "salida"
    assert main([str(CONFORME), "--salida", str(destino)]) == 0
    for nombre in ("unifilar.svg", "informe.pdf", "cuadro_cargas.csv"):
        assert (destino / nombre).is_file()


def test_cli_sale_con_error_si_el_proyecto_no_cumple(tmp_path):
    assert main([str(SIMPLE), "--salida", str(tmp_path / "salida")]) == 1
