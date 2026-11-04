import pytest

from core.norms.nbr5410.limits import (
    LIMITE_ALIMENTADOR_PCT,
    LIMITE_TERMINAL_PCT,
    LIMITE_TOTAL_PCT,
    CasoEntregaInvalido,
    limite_caso_pct,
    validar_caida,
)


def test_constantes_de_la_norma():
    assert LIMITE_TERMINAL_PCT == 4.0
    assert LIMITE_ALIMENTADOR_PCT == 5.0
    assert LIMITE_TOTAL_PCT == 7.0


def test_limites_por_caso_de_origen():
    assert limite_caso_pct("A") == 7.0
    assert limite_caso_pct("B") == 7.0
    assert limite_caso_pct("C") == 5.0
    assert limite_caso_pct("D") == 7.0
    assert limite_caso_pct("c") == 5.0


def test_ampliacion_por_lineas_largas_solo_en_casos_a_b_d():
    assert limite_caso_pct("A", 100) == 7.0
    assert limite_caso_pct("A", 150) == 7.25
    assert limite_caso_pct("A", 200) == 7.5
    assert limite_caso_pct("A", 500) == 7.5  # tope de +0,5 %
    assert limite_caso_pct("C", 500) == 5.0


def test_caso_invalido():
    with pytest.raises(CasoEntregaInvalido):
        limite_caso_pct("E")


def test_valida_circuito_terminal_contra_el_4_por_ciento():
    assert validar_caida(terminal_pct=3.9) == []
    assert "4.0 %" in " | ".join(validar_caida(terminal_pct=4.5))


def test_valida_caida_total_segun_el_caso():
    assert validar_caida(total_pct=4.8, caso="C") == []
    assert validar_caida(total_pct=6.0, caso="C")
    assert validar_caida(total_pct=6.0, caso="A") == []
    assert validar_caida(total_pct=7.4, caso="A", longitud_m=200) == []


def test_sin_datos_no_hay_problemas():
    assert validar_caida() == []
