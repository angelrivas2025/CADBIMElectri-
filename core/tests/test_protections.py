import copy
from pathlib import Path

import pytest

from core.calc.protections import (
    CLASES_DPS,
    ProteccionInvalida,
    clases_dps,
    curva_disjuntor,
    requiere_dps,
    requiere_dr,
    resumen_protecciones,
    seleccionar_disjuntor,
    verificar_poder_corte,
)
from core.model.loader import load_project

EJEMPLO = Path(__file__).resolve().parents[2] / "examples" / "casa-simple.json"


def test_serie_de_disyuntores_y_condicion_ib_in_iz():
    assert seleccionar_disjuntor(18, 40) == 20
    assert seleccionar_disjuntor(20, 40) == 20
    assert seleccionar_disjuntor(20.1, 40) == 25
    assert seleccionar_disjuntor(4.72, 24) == 6


def test_sin_disyuntor_posible():
    with pytest.raises(ProteccionInvalida):
        seleccionar_disjuntor(33, 39)  # el siguiente de la serie es 40 > Iz
    with pytest.raises(ProteccionInvalida):
        seleccionar_disjuntor(401, 500)  # la serie termina en 400


def test_corriente_de_proyecto_invalida():
    with pytest.raises(ValueError):
        seleccionar_disjuntor(0, 100)


def test_poder_de_corte():
    assert verificar_poder_corte(6, 4.5) == []
    assert "Poder de corte" in " ".join(verificar_poder_corte(3, 4.5))
    assert "Icc" in " ".join(verificar_poder_corte(6, None))


def test_curvas():
    assert curva_disjuntor("iluminacion") == "B"
    assert curva_disjuntor("tug") == "C"
    assert curva_disjuntor("tue") == "D"
    assert curva_disjuntor("otra cosa") == "C"


def test_dr_en_bano_y_ambientes_mojados():
    assert requiere_dr("bano")
    assert requiere_dr("cocina")
    assert requiere_dr("servicio")
    assert requiere_dr("garaje")
    assert requiere_dr("externo")
    assert requiere_dr("sala") == []


def test_dr_en_toma_interior_que_alimenta_exterior():
    motivos = requiere_dr("sala", "tug", alimenta_exterior=True)
    assert any("5.1.3.2.2 c" in m for m in motivos)


def test_dr_por_circuito_del_ejemplo():
    p = copy.deepcopy(load_project(EJEMPLO))
    r = resumen_protecciones(p)
    # C3 alimenta la cocina; C1 y C2 no tienen puntos en ambientes mojados.
    assert set(r["dr_por_circuito"]) == {"C3"}
    assert r["dr_sensibilidad_ma"] == 30
    assert r["dps_requerido"] is False
    assert any("supply" in w for w in r["warnings"])


def test_dr_del_circuito_completo():
    p = copy.deepcopy(load_project(EJEMPLO))
    p["points"][2]["feeds_outdoor"] = True  # P3, sala
    r = resumen_protecciones(p)
    assert "C2" in r["dr_por_circuito"]


def test_dps_con_linea_aerea_y_tormentas():
    supply = {"type": "aerea", "thunderstorm_days": 40}
    motivos = requiere_dps(supply)
    assert any("AQ2" in m for m in motivos)
    assert clases_dps(supply) == ["II"]


def test_dps_no_obligatorio_con_pocas_tormentas():
    assert requiere_dps({"type": "aerea", "thunderstorm_days": 20}) == []
    assert requiere_dps({"type": "subterranea", "thunderstorm_days": 80}) == []


def test_dps_con_partes_expuestas_y_pararrayos():
    supply = {"type": "subterranea", "exposed_parts": True, "has_lightning_rod": True}
    assert clases_dps(supply) == ["I", "II"]


def test_dps_en_cascada_con_equipos_sensibles():
    supply = {
        "type": "aerea",
        "thunderstorm_days": 60,
        "has_lightning_rod": True,
        "sensitive_equipment": True,
    }
    assert clases_dps(supply) == ["I", "II", "III"]
    assert CLASES_DPS["I"]["iimp_ka"] == 12.5
    assert CLASES_DPS["II"]["in_ka"] == 5.0


def test_sin_datos_de_suministro():
    assert "Sin datos" in requiere_dps(None)[0]
    assert clases_dps(None) == []


def test_el_ejemplo_con_suministro_aereo_exige_dps():
    p = copy.deepcopy(load_project(EJEMPLO))
    p["project"]["supply"] = {"type": "aerea", "thunderstorm_days": 45}
    r = resumen_protecciones(p)
    assert r["dps_requerido"] is True
    assert r["dps_clases"] == ["II"]
    assert r["warnings"] == []
