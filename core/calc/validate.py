"""Validación integral del proyecto: una sola puerta para la IA y la interfaz.

Devuelve errores (el proyecto no cumple) y avisos (revisar, pero no invalidan).
Ninguna etapa oculta su fallo: si una no puede evaluarse, queda como aviso.
"""
from __future__ import annotations

from typing import Any

from core.calc.bom import lista_materiales
from core.calc.demand import demanda
from core.calc.grouping import (
    recomendaciones_agrupamiento,
    validar_agrupamiento,
)
from core.calc.load_forecast import previsao_cargas, validar_puntos_minimos
from core.calc.protections import resumen_protecciones
from core.calc.sizing import dimensionar_alimentador, dimensionar_proyecto
from core.model.loader import reference_issues, schema_issues
from core.net.occupancy import verificar_ocupacion
from core.net.report import analizar_red


def validar_proyecto(
    project: dict[str, Any], opciones: dict[str, Any] | None = None
) -> dict[str, Any]:
    errores = list(schema_issues(project))
    avisos: list[str] = []

    errores.extend(reference_issues(project))

    revisiones = {
        "puntos_minimos": lambda: validar_puntos_minimos(project),
        "agrupamiento": lambda: validar_agrupamiento(project),
        "recomendaciones_agrupamiento": lambda: recomendaciones_agrupamiento(project),
    }
    resultados: dict[str, Any] = {}
    for nombre, funcion in revisiones.items():
        try:
            resultados[nombre] = funcion()
        except Exception as e:
            avisos.append(f"No se pudo evaluar {nombre}: {e}")
            resultados[nombre] = []

    errores.extend(resultados["puntos_minimos"])
    errores.extend(resultados["agrupamiento"])
    avisos.extend(resultados["recomendaciones_agrupamiento"])

    etapas = {
        "prevision": lambda: previsao_cargas(project),
        "demanda": lambda: demanda(project),
        "protecciones": lambda: resumen_protecciones(project),
    }
    for nombre, funcion in etapas.items():
        try:
            resultados[nombre] = funcion()
        except Exception as e:
            avisos.append(f"No se pudo calcular {nombre}: {e}")
            resultados[nombre] = None

    red = None
    if project.get("network"):
        try:
            red = analizar_red(project)
        except Exception as e:
            avisos.append(f"No se pudo analizar la red: {e}")
        if red is not None:
            errores.extend(red["errores"])
            avisos.extend(red["avisos"])

    try:
        resultados["dimensionamiento"] = dimensionar_proyecto(
            project, opciones, red=red["por_circuito"] if red else None
        )
    except Exception as e:
        avisos.append(f"No se pudo calcular dimensionamiento: {e}")
        resultados["dimensionamiento"] = None

    if red is not None and isinstance(resultados.get("dimensionamiento"), dict):
        try:
            red["ocupacion"] = verificar_ocupacion(
                project, red, resultados["dimensionamiento"]
            )
            errores.extend(red["ocupacion"]["errores"])
            avisos.extend(red["ocupacion"]["avisos"])
        except Exception as e:
            avisos.append(f"No se pudo verificar la ocupación: {e}")
            red["ocupacion"] = None
    elif red is not None:
        red["ocupacion"] = None

    for nombre in ("prevision", "demanda", "protecciones", "dimensionamiento"):
        etapa = resultados.get(nombre)
        if isinstance(etapa, dict):
            avisos.extend(f"{nombre}: {a}" for a in etapa.get("warnings", []))

    alimentador = None
    supply = (project.get("project") or {}).get("supply") or {}
    longitud_alimentador = supply.get("feeder_length_m")
    if red is not None and red.get("alimentador_referencia"):
        referencia = red["alimentador_referencia"]
        longitud_alimentador = red["alimentadores"][referencia]["length_m"]
    demanda_calculada = resultados.get("demanda")
    if (
        longitud_alimentador
        and isinstance(demanda_calculada, dict)
        and demanda_calculada["demanda_va"] > 0
    ):
        try:
            alimentador = dimensionar_alimentador(
                project,
                demanda_calculada["demanda_va"],
                longitud_m=longitud_alimentador,
                metodo=supply.get("feeder_method"),
                opciones=opciones,
            )
            avisos.extend(f"alimentador: {a}" for a in alimentador.get("warnings", []))
        except Exception as e:
            avisos.append(f"No se pudo calcular el alimentador: {e}")

    materiales = None
    if isinstance(resultados.get("dimensionamiento"), dict):
        try:
            materiales = lista_materiales(project, resultados["dimensionamiento"])
            avisos.extend(materiales["warnings"])
        except Exception as e:
            avisos.append(f"No se pudo armar la lista de materiales: {e}")

    return {
        "ok": not errores,
        "errores": errores,
        "avisos": avisos,
        "prevision": resultados.get("prevision"),
        "demanda": resultados.get("demanda"),
        "protecciones": resultados.get("protecciones"),
        "dimensionamiento": resultados.get("dimensionamiento"),
        "alimentador": alimentador,
        "materiales": materiales,
        "red": red,
    }
