import pytest

from core.norms.nbr5410.ampacity import (
    SECCIONES_COMERCIALES,
    TablaIncompleta,
    capacidad,
    cargar_tabla,
    cargar_tabla_norma,
    procedencia,
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


@pytest.mark.parametrize("material", ["Cu", "Al"])
@pytest.mark.parametrize("aislacion", ["PVC", "XLPE"])
def test_las_cuatro_tablas_de_la_norma_son_coherentes(material, aislacion):
    tabla = cargar_tabla_norma(material, aislacion)
    assert tabla
    assert validar_tabla(tabla) == []


def test_tabla_de_cobre_pvc_cubre_todas_las_secciones_y_metodos():
    tabla = cargar_tabla()
    assert set(tabla) == {
        ("A1", 2), ("A1", 3), ("A2", 2), ("A2", 3), ("B1", 2), ("B1", 3),
        ("B2", 2), ("B2", 3), ("C", 2), ("C", 3), ("D", 2), ("D", 3),
        ("E", 2), ("E", 3), ("F_JUSTAPOSTO", 2), ("F_JUSTAPOSTO", 3),
        ("F_TRIFOLIO", 3), ("G_HORIZONTAL", 3), ("G_VERTICAL", 3),
    }
    for filas in tabla.values():
        assert sorted(filas) == sorted(SECCIONES_COMERCIALES)


def test_valores_de_referencia_de_la_tabla_36():
    tabla = cargar_tabla()
    # Tabla 36, cobre PVC, 25 mm² (ver data/SOURCE.md).
    assert tabla[("A1", 3)][25.0] == 73
    assert tabla[("B2", 3)][25.0] == 80
    assert tabla[("C", 3)][25.0] == 96
    assert tabla[("D", 3)][25.0] == 86
    assert tabla[("B1", 2)][2.5] == 24


def test_a1_y_b2_no_son_identicas():
    tabla = cargar_tabla()
    for n in (2, 3):
        assert any(
            tabla[("A1", n)][s] != tabla[("B2", n)][s] for s in SECCIONES_COMERCIALES
        )


def test_regresion_95_mm2_xlpe_no_es_29_a():
    """El catálogo Nexans imprime 29 A; la tabla 37 dice 269 A."""
    assert cargar_tabla_norma("Cu", "XLPE")[("B1", 3)][95.0] == 269


def test_aluminio_empieza_en_16_mm2():
    tabla = cargar_tabla_norma("Al", "PVC")
    assert min(tabla[("C", 2)]) == 16.0
    assert 2.5 not in tabla[("C", 2)]


def test_procedencia_identifica_las_tablas():
    meta = procedencia()
    assert meta["tablas_nbr"] == [36, 38]
    assert (meta["material"], meta["aislacion"]) == ("Cu", "PVC")


def test_no_se_elige_variante_por_defecto():
    with pytest.raises(ValueError, match="F_JUSTAPOSTO"):
        seleccionar_seccion(50.0, "F", 3, cargar_tabla())
    with pytest.raises(ValueError):
        seleccionar_seccion(50.0, "G", 2, cargar_tabla())


def test_variantes_de_f_y_g():
    tabla = cargar_tabla()
    con_folio = seleccionar_seccion(110.0, "F", 3, tabla, variante="F_TRIFOLIO")
    con_justo = seleccionar_seccion(110.0, "F", 3, tabla, variante="F_JUSTAPOSTO")
    assert con_folio == 25.0 and con_justo == 25.0
    assert capacidad("F", 3, 25.0, tabla, variante="F_TRIFOLIO") == 110.0
    assert capacidad("G", 3, 25.0, tabla, variante="G_HORIZONTAL") == 146.0


def test_capacidad_aplica_factores_de_correccion():
    tabla = cargar_tabla()
    # 25 mm² A1/3 = 73 A; 0.87 (temperatura) * 0.80 (agrupamiento) = 0.696
    assert capacidad("A1", 3, 25.0, tabla, factor=0.87 * 0.80) == pytest.approx(50.808)
    with pytest.raises(ValueError):
        capacidad("A1", 3, 25.0, tabla, factor=0)


def test_capacidad_de_seccion_ausente():
    with pytest.raises(TablaIncompleta):
        capacidad("C", 2, 2.5, cargar_tabla_norma("Al", "PVC"))


def test_aluminio_630_mm2_no_se_inventa():
    """Celdas perdidas en la extracción del PDF: el motor debe detenerse."""
    tabla = cargar_tabla_norma("Al", "PVC")
    for variante in ("F_JUSTAPOSTO",):
        with pytest.raises(TablaIncompleta):
            capacidad("F", 3, 630.0, tabla, variante=variante)
    for variante in ("G_HORIZONTAL", "G_VERTICAL"):
        with pytest.raises(TablaIncompleta):
            capacidad("G", 3, 630.0, tabla, variante=variante)


@pytest.mark.parametrize("material", ["Cu", "Al"])
@pytest.mark.parametrize("aislacion", ["PVC", "XLPE"])
def test_no_hay_valores_repetidos_entre_secciones_vecinas(material, aislacion):
    """Un valor copiado de la fila anterior no rompe la monotonía: se busca aparte."""
    tabla = cargar_tabla_norma(material, aislacion)
    for clave, filas in tabla.items():
        secciones = [s for s in sorted(filas) if s >= 16]
        for a, b in zip(secciones, secciones[1:]):
            assert filas[a] != filas[b], (
                f"{material}/{aislacion} {clave}: repite {filas[a]:g} A en "
                f"{a:g} y {b:g} mm²"
            )
