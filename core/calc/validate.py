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
from core.calc.sizing import dimensionar_proyecto
from core.model.loader import reference_issues, schema_issues


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
        "dimensionamiento": lambda: dimensionar_proyecto(project, opciones),
    }
    for nombre, funcion in etapas.items():
        try:
            resultados[nombre] = funcion()
        except Exception as e:
            avisos.append(f"No se pudo calcular {nombre}: {e}")
            resultados[nombre] = None

    for nombre in ("prevision", "demanda", "protecciones", "dimensionamiento"):
        etapa = resultados.get(nombre)
        if isinstance(etapa, dict):
            avisos.extend(f"{nombre}: {a}" for a in etapa.get("warnings", []))

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
        "materiales": materiales,
    }
