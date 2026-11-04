"""Dimensionamiento integrado de circuitos y alimentador.

La sección final es la mayor de tres criterios:
1. capacidad de conducción corregida (Ib <= Iz);
2. sección mínima por caída de tensión (límite que fija la norma);
3. sección comercial mínima de la tabla.

El disyuntor se elige con Ib <= In <= Iz. Ningún dato faltante se estima en
silencio: si no hay longitud, el circuito queda sin verificación de caída y con
una advertencia.
"""
from __future__ import annotations

from typing import Any, Sequence

from core.calc.currents import FACTOR_TENSION, circuit_currents
from core.calc.protections import ProteccionInvalida, curva_disjuntor, seleccionar_disjuntor
from core.calc.voltage_drop import caida_tension_pct, seccion_minima_por_caida
from core.norms.nbr5410.ampacity import (
    Tabla,
    cargar_tabla_norma,
    capacidad,
    seleccionar_seccion,
)
from core.norms.nbr5410.corrections import (
    factor_agrupamiento,
    factor_temperatura,
    factor_total,
)
from core.norms.nbr5410.limits import LIMITE_TERMINAL_PCT
from core.norms.nbr5410.minimums import seccion_minima
from core.calc.load_schedule import FASES_POR_SISTEMA

METODO_POR_DEFECTO = "B1"
MATERIAL_POR_DEFECTO = "Cu"
AISLACION_POR_DEFECTO = "PVC"
TEMPERATURA_AMBIENTE_C = 30.0

TEMPERATURA_OPERACION_C = {"PVC": 70.0, "XLPE": 90.0}


def n_conductores_cargados(n_fases: int) -> int:
    return 3 if n_fases == 3 else 2


def dimensionar_circuito(
    *,
    corriente_a: float,
    n_fases: int,
    tension_fase_v: float,
    longitud_m: float | None,
    metodo: str = METODO_POR_DEFECTO,
    variante: str | None = None,
    n_loaded: int | None = None,
    material: str = MATERIAL_POR_DEFECTO,
    aislacion: str = AISLACION_POR_DEFECTO,
    factores: Sequence[float] = (1.0,),
    limite_pct: float = LIMITE_TERMINAL_PCT,
    tipo_carga: str = "general",
    tabla: Tabla | None = None,
) -> dict[str, Any]:
    warnings: list[str] = []
    material = material.capitalize()
    aislacion = aislacion.upper()
    tabla = tabla if tabla is not None else cargar_tabla_norma(material, aislacion)
    n_loaded = n_loaded or n_conductores_cargados(n_fases)
    factor = factor_total(*factores)

    seccion_amp = seleccionar_seccion(corriente_a, metodo, n_loaded, tabla, variante=variante)

    seccion_caida = None
    caida_pct = None
    if longitud_m is None:
        warnings.append("Sin longitud de circuito: no se verificó la caída de tensión")
    else:
        seccion_caida = seccion_minima_por_caida(
            corriente_a,
            longitud_m,
            tension_fase_v,
            limite_pct,
            n_fases=n_fases,
            material=material,
            temperatura_c=TEMPERATURA_OPERACION_C[aislacion],
        )

    seccion_norma = seccion_minima(tipo_carga, material)
    seccion = max(seccion_amp, seccion_caida or 0, seccion_norma)
    capacidad_a = capacidad(metodo, n_loaded, seccion, tabla, factor=factor, variante=variante)

    if longitud_m is not None:
        caida_pct = caida_tension_pct(
            corriente_a,
            longitud_m,
            seccion,
            tension_fase_v,
            n_fases=n_fases,
            material=material,
            temperatura_c=TEMPERATURA_OPERACION_C[aislacion],
        )
        if caida_pct > limite_pct:
            warnings.append(
                f"Caída de tensión {caida_pct:.2f} % supera el límite {limite_pct:.1f} %"
            )

    breaker_a = None
    try:
        breaker_a = seleccionar_disjuntor(corriente_a, capacidad_a)
    except ProteccionInvalida as e:
        warnings.append(str(e))

    return {
        "section_mm2": seccion,
        "section_by_ampacity": seccion_amp,
        "section_by_drop": seccion_caida,
        "section_min_rule": seccion_norma,
        "capacity_a": capacidad_a,
        "breaker_a": breaker_a,
        "breaker_curve": curva_disjuntor(tipo_carga),
        "correction_factor": factor,
        "voltage_drop_pct": caida_pct,
        "length_m": longitud_m,
        "method": metodo,
        "variant": variante,
        "n_loaded": n_loaded,
        "material": material,
        "insulation": aislacion,
        "warnings": warnings,
    }


def opciones_por_defecto(project: dict[str, Any]) -> dict[str, Any]:
    return {
        "temperatura_c": TEMPERATURA_AMBIENTE_C,
        "ambiente": "aire",
        "n_circuitos_agrupados": 1,
        "disposicion": "feixe_1camada",
        "limite_pct": LIMITE_TERMINAL_PCT,
    }


def _factores_correccion(aislacion: str, opciones: dict[str, Any]) -> tuple[list[float], list[str]]:
    warnings: list[str] = []
    factores = [
        factor_temperatura(opciones["temperatura_c"], aislacion, opciones["ambiente"])
    ]
    agrupados = opciones["n_circuitos_agrupados"]
    if agrupados > 1:
        factores.append(factor_agrupamiento(opciones["disposicion"], agrupados))
    else:
        warnings.append(
            "Agrupamiento no declarado: se supone 1 circuito por canalización; "
            "confirme el número real de circuitos agrupados"
        )
    return factores, warnings


def dimensionar_proyecto(project: dict[str, Any], opciones: dict[str, Any] | None = None) -> dict[str, Any]:
    opciones = {**opciones_por_defecto(project), **(opciones or {})}
    tension = project["project"]["voltage"]
    corrientes = circuit_currents(project)
    propios = {c["id"]: c for c in project["circuits"]}
    warnings = list(corrientes["warnings"])
    resultados = []

    for c in corrientes["circuits"]:
        if c["current_a"] is None:
            warnings.append(f"Circuito '{c['id']}' sin corriente calculable: no se dimensiona")
            continue
        crudo = propios[c["id"]]
        aislacion = (crudo.get("insulation") or AISLACION_POR_DEFECTO).upper()
        try:
            factores, avisos = _factores_correccion(aislacion, opciones)
            dim = dimensionar_circuito(
                corriente_a=c["current_a"],
                n_fases=c["phases"],
                tension_fase_v=tension,
                longitud_m=crudo.get("length_m"),
                metodo=crudo.get("method") or METODO_POR_DEFECTO,
                variante=crudo.get("method_variant"),
                n_loaded=crudo.get("n_loaded"),
                material=crudo.get("material") or MATERIAL_POR_DEFECTO,
                aislacion=aislacion,
                factores=factores,
                limite_pct=opciones["limite_pct"],
                tipo_carga=c["type"],
            )
        except Exception as e:  # tabla sin la sección pedida, método ambiguo, etc.
            warnings.append(f"Circuito '{c['id']}': {e}")
            continue
        resultados.append({**c, **dim})
        warnings.extend(f"{c['id']}: {a}" for a in avisos)
        warnings.extend(f"{c['id']}: {w}" for w in dim["warnings"])

    return {"circuits": resultados, "warnings": warnings}


def dimensionar_alimentador(
    project: dict[str, Any],
    demanda_va: float,
    *,
    longitud_m: float | None = None,
    metodo: str | None = None,
    opciones: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Alimentador desde el punto de entrega hasta el tablero general."""
    opciones = {**opciones_por_defecto(project), **(opciones or {})}
    fases = FASES_POR_SISTEMA[project["project"]["system"]]
    tension = project["project"]["voltage"]
    corriente = round(demanda_va / (FACTOR_TENSION[len(fases)] * tension), 2)
    metodo = metodo or opciones.get("metodo_alimentador", "D")
    factores, avisos = _factores_correccion(AISLACION_POR_DEFECTO, opciones)
    resultado = dimensionar_circuito(
        corriente_a=corriente,
        n_fases=len(fases),
        tension_fase_v=tension,
        longitud_m=longitud_m,
        metodo=metodo,
        material=MATERIAL_POR_DEFECTO,
        aislacion=AISLACION_POR_DEFECTO,
        factores=factores,
        limite_pct=opciones["limite_pct"],
        tipo_carga="general",
    )
    return {
        "current_a": corriente,
        "phases": len(fases),
        **resultado,
        "warnings": avisos + resultado["warnings"],
    }
