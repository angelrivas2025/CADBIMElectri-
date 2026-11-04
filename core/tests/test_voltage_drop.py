import pytest

from core.calc.voltage_drop import (
    caida_tension_pct,
    caida_tension_v,
    resistencia_ohm_por_m,
    seccion_minima_por_caida,
)


def test_resistencia_del_cobre_a_70c():
    # 0.017241 * (1 + 0.00393 * 50) / 2.5 = 0.0082513 Ω/m
    assert resistencia_ohm_por_m(2.5, 70) == pytest.approx(0.0082513, rel=1e-3)


def test_caida_calculada_a_mano():
    # I=10 A, L=20 m, 2.5 mm², sin margen: 2*10*20*0.0082513 = 3.3005 V
    assert caida_tension_v(10, 20, 2.5, margen=1.0) == pytest.approx(3.3005, rel=1e-3)
    assert caida_tension_pct(10, 20, 2.5, 127, margen=1.0) == pytest.approx(2.599, rel=1e-3)


def test_mayor_seccion_menor_caida():
    assert caida_tension_v(10, 20, 4) < caida_tension_v(10, 20, 2.5)


def test_seccion_minima_por_caida():
    # Con límite 2 % a 127 V (2.54 V): 2.5 mm² no alcanza (3.63 V con margen), 4 mm² sí (2.27 V).
    assert seccion_minima_por_caida(10, 20, 127, 2.0) == 4


def test_sin_solucion_lanza_error():
    with pytest.raises(ValueError):
        seccion_minima_por_caida(500, 500, 127, 1.0)


def test_trifasico_usa_raiz_de_tres_y_tension_de_linea():
    from math import sqrt

    ida = caida_tension_v(10, 20, 2.5, margen=1.0, n_fases=1) / 2  # un solo conductor
    assert caida_tension_v(10, 20, 2.5, margen=1.0, n_fases=3) == pytest.approx(ida * sqrt(3))
    # El porcentaje se mide sobre la tensión de línea (√3 · 127).
    assert caida_tension_pct(10, 20, 2.5, 127, margen=1.0, n_fases=3) == pytest.approx(
        ida * sqrt(3) / (sqrt(3) * 127) * 100
    )


def test_bifasico_mantiene_doble_conductor_pero_mide_sobre_linea():
    from math import sqrt

    assert caida_tension_v(10, 20, 2.5, margen=1.0, n_fases=2) == caida_tension_v(
        10, 20, 2.5, margen=1.0
    )
    assert caida_tension_pct(10, 20, 2.5, 127, margen=1.0, n_fases=2) == pytest.approx(
        caida_tension_v(10, 20, 2.5, margen=1.0) / (sqrt(3) * 127) * 100
    )


def test_trifasico_admite_menor_seccion_que_monofasico():
    mono = seccion_minima_por_caida(10, 20, 127, 4.0)
    tri = seccion_minima_por_caida(10, 20, 127, 4.0, n_fases=3)
    assert tri <= mono


def test_aluminio_resiste_mas_que_el_cobre():
    assert caida_tension_v(10, 20, 2.5, margen=1.0, material="Al") > caida_tension_v(
        10, 20, 2.5, margen=1.0, material="Cu"
    )
