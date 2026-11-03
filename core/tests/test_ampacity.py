import pytest

from core.norms.nbr5410.ampacity import (
    TablaIncompleta,
    cargar_tabla,
    seleccionar_seccion,
    validar_tabla,
)

# Tabla SINTÉTICA, con valores inventados, solo para probar la lógica. No es la norma.
FALSA = {
    ("B1", 2): {1.5: 10.0, 2.5: 20.0, 4: 30.0},
    ("B1", 3): {1.5: 9.0, 2.5: 18.0, 4: 27.0},
}


def test_selecciona_la_menor_seccion_suficiente():
    assert seleccionar_seccion(10.0, "B1", 2, FALSA) == 1.5
    assert seleccionar_seccion(10.1, "b1", 2, FALSA) == 2.5
    assert seleccionar_seccion(27.0, "B1", 3, FALSA) == 4


def test_error_si_no_hay_seccion_suficiente():
    with pytest.raises(TablaIncompleta):
        seleccionar_seccion(31.0, "B1", 2, FALSA)


def test_error_si_falta_el_metodo():
    with pytest.raises(TablaIncompleta):
        seleccionar_seccion(5.0, "C", 2, FALSA)


def test_tabla_sintetica_es_coherente():
    assert validar_tabla(FALSA) == []


def test_validador_detecta_errores_de_transcripcion():
    mala = {
        ("B1", 2): {1.5: 10.0, 2.5: 9.0},       # no crece
        ("B1", 3): {1.5: 12.0},                  # 3 conductores > 2 conductores
        ("C", 2): {3.0: 10.0},                   # sección no comercial
    }
    problemas = " | ".join(validar_tabla(mala))
    assert "no crece" in problemas
    assert "supera" in problemas
    assert "no es comercial" in problemas


def test_la_tabla_real_se_valida_cuando_se_llena():
    """Si el CSV real tiene datos, deben pasar el validador. Vacío = sin comprobaciones."""
    assert validar_tabla(cargar_tabla()) == []
