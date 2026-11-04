import pytest

from core.norms.nbr5410.corrections import (
    FactorIndefinido,
    factor_agrupamiento,
    factor_enterrado,
    factor_multicamada,
    factor_resistividad,
    factor_temperatura,
    factor_total,
    validar_factores,
)


def test_las_tablas_de_correccion_son_coherentes():
    assert validar_factores() == []


def test_temperatura_del_aire_pvc():
    assert factor_temperatura(30, "PVC") == 1.0
    assert factor_temperatura(40, "PVC") == 0.87
    assert factor_temperatura(60, "PVC") == 0.50


def test_temperatura_entre_filas_toma_la_mas_desfavorable():
    # 38 °C no está tabulado: se usa el factor de 40 °C.
    assert factor_temperatura(38, "PVC") == 0.87
    assert factor_temperatura(27, "XLPE") == 1.0


def test_temperatura_del_suelo_usa_otra_referencia():
    assert factor_temperatura(20, "PVC", ambiente="solo") == 1.0
    assert factor_temperatura(25, "PVC", ambiente="solo") == 0.95


def test_temperatura_fuera_de_tabla():
    with pytest.raises(FactorIndefinido):
        factor_temperatura(65, "PVC")
    assert factor_temperatura(70, "XLPE") == 0.58


def test_resistividad_del_suelo():
    assert factor_resistividad(2.5) == 0.96  # directamente enterrado
    assert factor_resistividad(2.5, "duto") == 0.90
    # El 3 K.m/W del origen estaba con las columnas invertidas (ver SOURCE.md).
    assert factor_resistividad(3.0, "duto") == 0.90
    assert factor_resistividad(3.0, "enterrado") == 0.96


def test_resistividad_fuera_de_tabla():
    with pytest.raises(FactorIndefinido):
        factor_resistividad(4.0)


def test_agrupamiento_por_disposicion():
    assert factor_agrupamiento("feixe_1camada", 1) == 1.0
    assert factor_agrupamiento("feixe_1camada", 2) == 0.80
    assert factor_agrupamiento("feixe_1camada", 3) == 0.70
    assert factor_agrupamiento("camada_teto", 10) == 0.61
    assert factor_agrupamiento("camada_parede_piso", 11) == 0.70


def test_agrupamiento_fuera_de_tabla():
    with pytest.raises(FactorIndefinido):
        factor_agrupamiento("camada_parede_piso", 12)


def test_agrupamiento_con_disposicion_invalida():
    with pytest.raises(ValueError):
        factor_agrupamiento("bandeja", 2)


def test_multicamada():
    assert factor_multicamada(2, 2) == 0.68
    assert factor_multicamada(3, 4) == 0.55
    assert factor_multicamada(9, 10) == 0.46


def test_enterrado_toma_la_distancia_inferior():
    assert factor_enterrado(2, 0) == 0.75
    assert factor_enterrado(2, "1D") == 0.80
    assert factor_enterrado(2, 0.3) == 0.90  # usa 0,25 m
    assert factor_enterrado(2, 0.5) == 0.90


def test_factor_total():
    assert factor_total(0.87, 0.80, 0.90) == pytest.approx(0.6264)
    with pytest.raises(ValueError):
        factor_total(0.9, 0)
