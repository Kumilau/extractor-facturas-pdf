"""Utilidades para RUT chileno (cálculo y validación del dígito verificador)."""

from __future__ import annotations

import re

PATRON_RUT = re.compile(r"\b(\d{1,2}\.?\d{3}\.?\d{3})-?([\dkK])\b")


def digito_verificador(cuerpo: int) -> str:
    """Calcula el dígito verificador con el algoritmo módulo 11."""
    suma, factor = 0, 2
    for digito in reversed(str(cuerpo)):
        suma += int(digito) * factor
        factor = 2 if factor == 7 else factor + 1
    resto = 11 - (suma % 11)
    return {11: "0", 10: "K"}.get(resto, str(resto))


def normalizar(rut: str) -> str:
    """'76.123.456-k' -> '76123456-K'"""
    limpio = re.sub(r"[^\dkK]", "", rut).upper()
    return f"{limpio[:-1]}-{limpio[-1]}" if len(limpio) > 1 else limpio


def formatear(cuerpo: int) -> str:
    """76123456 -> '76.123.456-X' con su dígito verificador."""
    return f"{cuerpo:,}".replace(",", ".") + "-" + digito_verificador(cuerpo)


def es_valido(rut: str) -> bool:
    normal = normalizar(rut)
    if "-" not in normal:
        return False
    cuerpo, dv = normal.split("-")
    return cuerpo.isdigit() and digito_verificador(int(cuerpo)) == dv


def buscar_todos(texto: str) -> list[str]:
    return [normalizar(f"{c}-{d}") for c, d in PATRON_RUT.findall(texto)]


def con_puntos(rut: str | None) -> str | None:
    """'76123456-K' -> '76.123.456-K' (para mostrar)."""
    if not rut or "-" not in rut:
        return rut
    cuerpo, dv = normalizar(rut).split("-")
    return f"{int(cuerpo):,}".replace(",", ".") + f"-{dv}" if cuerpo.isdigit() else rut
