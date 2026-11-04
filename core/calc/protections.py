"""Protecciones: disyuntor termomagnético, DR y DPS (NBR 5410).

Disyuntor (6.3.4): Ib <= In <= Iz, con In de la serie comercial.
DR (5.1.3.2.2): 30 mA obligatorio en baños, tomas exteriores, tomas interiores que
puedan alimentar equipos en el exterior y ambientes mojados o sujetos a lavado.
DPS (5.4.2.1 y 6.3.5): obligatorio con alimentación aérea en zona AQ2 (> 25 días de
tormenta al año) o con partes expuestas a descargas directas (AQ3).

La protección contra sobrecorriente no reemplaza al DR: el DR es protección
adicional (5.1.3.2.1.1) y no sustituye el seccionamiento automático.
"""
from __future__ import annotations

from typing import Any

SERIE_IN = [
    6, 10, 16, 20, 25, 32, 40, 50, 63, 70, 80, 100, 125, 160, 200, 225, 250, 300, 400,
]

DR_SENSIBILIDAD_MA = 30

CLASES_DPS = {
    "I": {"iimp_ka": 12.5, "uso": "Entrada principal (BEP) en edificio con pararrayos"},
    "II": {"in_ka": 5.0, "uso": "Entrada principal o cuadro de distribución; sobrecargas indirectas"},
    "III": {"uso": "Junto al equipo electrónico sensible (protección fina)"},
}

# Ambientes que exigen DR de 30 mA en todos sus circuitos (5.1.3.2.2 a y d).
AMBIENTES_CON_DR = {"bano", "cocina", "servicio", "garaje"}


class ProteccionInvalida(Exception):
    """Los datos no satisfacen la condición de protección."""


def seleccionar_disjuntor(
    corriente_proyecto_a: float,
    capacidad_corregida_a: float,
    serie: list[int] = SERIE_IN,
) -> int:
    """Menor In de la serie que cumple Ib <= In <= Iz."""
    if corriente_proyecto_a <= 0:
        raise ValueError("La corriente de proyecto debe ser positiva")
    validos = [i for i in sorted(serie) if corriente_proyecto_a <= i <= capacidad_corregida_a]
    if not validos:
        raise ProteccionInvalida(
            f"No hay disyuntor en la serie para Ib={corriente_proyecto_a:g} A e "
            f"Iz={capacidad_corregida_a:g} A; hay que aumentar la sección del conductor"
        )
    return validos[0]


def verificar_poder_corte(icn_ka: float, icc_prevista_ka: float | None) -> list[str]:
    """El poder de corte debe superar la corriente de cortocircuito presumida."""
    if icc_prevista_ka is None:
        return ["No se conoce la Icc presumida: verifique el poder de corte del disyuntor"]
    if icn_ka < icc_prevista_ka:
        return [
            f"Poder de corte {icn_ka:g} kA < Icc presumida {icc_prevista_ka:g} kA"
        ]
    return []


def curva_disjuntor(tipo_carga: str) -> str:
    """B para resistivas, C para uso general, D para motores y transformadores."""
    tipo = tipo_carga.strip().lower()
    if tipo in {"iluminacion", "resistiva", "calefaccion"}:
        return "B"
    if tipo in {"general", "tug", "tomas"}:
        return "C"
    if tipo in {"tue", "motor", "transformador"}:
        return "D"
    return "C"


def requiere_dr(
    room_type: str,
    point_type: str | None = None,
    *,
    alimenta_exterior: bool = False,
) -> list[str]:
    """Motivos por los que el circuito necesita DR de 30 mA (lista vacía si no).

    `point_type=None` significa que se evalúa el circuito completo y se aplica el
    criterio más exigente. En baños alcanza a cualquier punto de utilización
    (5.1.3.2.2 a); en cocinas, servicio y garajes la norma habla de tomacorrientes
    (5.1.3.2.2 d), así que la iluminación de esos ambientes no lo exige.
    """
    motivos: list[str] = []
    room_type = room_type.strip().lower()
    toma = point_type is None or point_type in ("tug", "tue")
    if room_type == "bano":
        motivos.append("Baño o local con bañera/ducha (5.1.3.2.2 a)")
    elif room_type in AMBIENTES_CON_DR and toma:
        motivos.append(
            f"Local mojado o sujeto a lavado ({room_type}) (5.1.3.2.2 d)"
        )
    if room_type == "externo" and toma:
        motivos.append("Tomacorriente en el exterior de la edificación (5.1.3.2.2 b)")
    if alimenta_exterior and toma:
        motivos.append(
            "Tomacorriente interior que puede alimentar equipos en el exterior (5.1.3.2.2 c)"
        )
    return motivos


def requisitos_dr(project: dict[str, Any]) -> dict[str, list[str]]:
    """DR exigido por circuito, agrupando los motivos de sus puntos."""
    ambientes = {r["id"]: r["type"] for r in project["rooms"]}
    motivos_por_circuito: dict[str, set[str]] = {}
    for p in project["points"]:
        cid = p.get("circuit")
        if cid is None or p["type"] == "tablero":
            continue
        motivos = requiere_dr(
            ambientes.get(p["room"], "otro"),
            p["type"],
            alimenta_exterior=bool(p.get("feeds_outdoor", False)),
        )
        if motivos:
            motivos_por_circuito.setdefault(cid, set()).update(motivos)
    return {cid: sorted(m) for cid, m in motivos_por_circuito.items()}


def requiere_dps(supply: dict[str, Any] | None) -> list[str]:
    """Motivos por los que la instalación necesita DPS (5.4.2.1)."""
    if not supply:
        return ["Sin datos de suministro: no se puede evaluar la necesidad de DPS"]
    motivos: list[str] = []
    aerea = str(supply.get("type", "")).lower() == "aerea"
    dias = supply.get("thunderstorm_days")
    if aerea and dias is not None and dias > 25:
        motivos.append(
            f"Línea aérea con {dias:g} días de tormenta al año (zona AQ2, 5.4.2.1)"
        )
    if supply.get("exposed_parts"):
        motivos.append("Partes de la instalación expuestas a descargas directas (AQ3, 5.4.2.1)")
    if supply.get("sensitive_equipment"):
        motivos.append("Equipos electrónicos sensibles que requieren protección (6.3.5)")
    return motivos


def clases_dps(supply: dict[str, Any] | None) -> list[str]:
    """Clases de DPS a instalar en cascada, de mayor a menor exposición."""
    if not supply or not requiere_dps(supply):
        return []
    clases: list[str] = []
    if supply.get("has_lightning_rod") or supply.get("exposed_parts"):
        clases.append("I")
    clases.append("II")
    if supply.get("sensitive_equipment"):
        clases.append("III")
    return clases


def resumen_protecciones(project: dict[str, Any]) -> dict[str, Any]:
    dr = requisitos_dr(project)
    supply = project["project"].get("supply")
    motivos_dps = requiere_dps(supply)
    return {
        "dr_por_circuito": dr,
        "dr_sensibilidad_ma": DR_SENSIBILIDAD_MA,
        "dps_requerido": bool(motivos_dps) and "Sin datos" not in motivos_dps[0],
        "dps_motivos": motivos_dps,
        "dps_clases": clases_dps(supply),
        "warnings": [] if supply else ["El proyecto no declara datos de suministro (supply)"],
    }
