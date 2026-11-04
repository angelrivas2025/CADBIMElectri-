"""Registro de herramientas: argumentos validados antes de tocar el proyecto.

La IA propone llamadas estructuradas; este registro valida la forma de los
argumentos con JSON Schema. Los valores numéricos los calcula siempre el motor.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from jsonschema import Draft202012Validator


class ErrorHerramienta(Exception):
    """La llamada no cumple el contrato o no puede aplicarse al proyecto."""


@dataclass(frozen=True)
class Herramienta:
    nombre: str
    descripcion: str
    esquema: dict[str, Any]
    funcion: Callable[[dict[str, Any], dict[str, Any]], Any]

    def llamar(self, project: dict[str, Any], arguments: dict[str, Any]) -> Any:
        errores = sorted(
            Draft202012Validator(self.esquema).iter_errors(arguments),
            key=lambda e: (list(e.absolute_path), e.message),
        )
        if errores:
            detalle = "; ".join(
                f"{'/'.join(str(p) for p in e.absolute_path) or '(raíz)'}: {e.message}"
                for e in errores
            )
            raise ErrorHerramienta(
                f"argumentos inválidos para '{self.nombre}': {detalle}"
            )
        return self.funcion(project, arguments)


CATALOGO: dict[str, Herramienta] = {}


def definir(
    nombre: str,
    descripcion: str,
    esquema: dict[str, Any],
) -> Callable[[Callable], Callable]:
    def decorador(funcion: Callable) -> Callable:
        if nombre in CATALOGO:
            raise RuntimeError(f"herramienta duplicada: {nombre}")
        CATALOGO[nombre] = Herramienta(nombre, descripcion, esquema, funcion)
        return funcion

    return decorador


def ejecutar(
    project: dict[str, Any], nombre: str, arguments: dict[str, Any]
) -> Any:
    herramienta = CATALOGO.get(nombre)
    if herramienta is None:
        disponibles = ", ".join(sorted(CATALOGO))
        raise ErrorHerramienta(
            f"herramienta desconocida '{nombre}' (disponibles: {disponibles})"
        )
    return herramienta.llamar(project, arguments)


def describir() -> list[dict[str, Any]]:
    return [
        {
            "name": herramienta.nombre,
            "description": herramienta.descripcion,
            "parameters": herramienta.esquema,
        }
        for herramienta in (CATALOGO[n] for n in sorted(CATALOGO))
    ]
