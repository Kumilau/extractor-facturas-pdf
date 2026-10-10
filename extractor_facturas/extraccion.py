"""Extracción de datos de facturas electrónicas chilenas en PDF."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import pdfplumber

from . import rut as rut_util

TASA_IVA = 0.19
TOLERANCIA = 1  # pesos de diferencia aceptados por redondeo

_MONTO = r"\$?[ \t]*(\d{1,3}(?:\.\d{3})+|\d+)"
PATRONES = {
    "folio": re.compile(r"(?:N[°ºo]\.?|Folio:?)[ \t]*(\d+)", re.IGNORECASE),
    "fecha": re.compile(r"Fecha[^:\n]*:[ \t]*(\d{1,2}[/-]\d{1,2}[/-]\d{4}|\d{4}-\d{2}-\d{2})", re.IGNORECASE),
    "neto": re.compile(r"Neto:?[ \t]*" + _MONTO, re.IGNORECASE),
    "iva": re.compile(r"IVA[ \t]*\(?19[ \t]*%\)?:?[ \t]*" + _MONTO, re.IGNORECASE),
    "total": re.compile(r"^[ \t]*Total(?:[ \t]+a[ \t]+pagar)?:?[ \t]*" + _MONTO + r"[ \t]*$",
                        re.IGNORECASE | re.MULTILINE),
    "emisor": re.compile(r"Emisor:[ \t]*(.+?)[ \t]*-[ \t]*RUT", re.IGNORECASE),
}

COLUMNAS_DETALLE = {
    "cantidad": ["cantidad", "cant"],
    "descripcion": ["descripcion", "producto", "detalle", "item"],
    "precio_unitario": ["precio unit", "unitario", "p. unit", "valor unit"],
    "total_linea": ["subtotal", "total", "monto"],
}


@dataclass
class Factura:
    archivo: str
    proveedor: str | None = None
    rut_proveedor: str | None = None
    rut_cliente: str | None = None
    folio: int | None = None
    fecha: date | None = None
    neto: int | None = None
    iva: int | None = None
    total: int | None = None
    items: list[dict] = field(default_factory=list)
    observaciones: list[str] = field(default_factory=list)

    @property
    def estado(self) -> str:
        if any(o.startswith("No es una factura") for o in self.observaciones):
            return "No reconocido"
        return "Revisar" if self.observaciones else "OK"


def _sin_tildes(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c)).lower().strip()


def a_entero(texto: str | None) -> int | None:
    if texto is None:
        return None
    limpio = re.sub(r"[^\d]", "", str(texto))
    return int(limpio) if limpio else None


def _fecha(texto: str) -> date | None:
    for formato in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    return None


def _primero(nombre: str, texto: str, ultimo: bool = False) -> str | None:
    hallazgos = PATRONES[nombre].findall(texto)
    if not hallazgos:
        return None
    return hallazgos[-1] if ultimo else hallazgos[0]


def _proveedor(texto: str) -> str | None:
    emisor = _primero("emisor", texto)
    if emisor:
        return emisor.strip()
    # Formato clásico: el nombre del emisor es la primera línea, antes del RUT
    for linea in texto.splitlines():
        linea = re.split(r"R\.?U\.?T\.?", linea, flags=re.IGNORECASE)[0].strip()
        if linea and not linea.lower().startswith("factura"):
            return linea
    return None


def _mapear_columnas(encabezado: list[str]) -> dict[str, int]:
    mapa: dict[str, int] = {}
    normalizados = [_sin_tildes(c or "") for c in encabezado]
    for campo, alias in COLUMNAS_DETALLE.items():
        for i, nombre in enumerate(normalizados):
            if i in mapa.values():
                continue
            if any(nombre.startswith(a) for a in alias):
                mapa[campo] = i
                break
    return mapa


def _items(tablas: list[list[list[str]]]) -> list[dict]:
    items = []
    for tabla in tablas:
        if not tabla or len(tabla) < 2:
            continue
        mapa = _mapear_columnas(tabla[0])
        if not {"descripcion", "total_linea"} <= mapa.keys():
            continue
        for fila in tabla[1:]:
            descripcion = (fila[mapa["descripcion"]] or "").strip()
            total_linea = a_entero(fila[mapa["total_linea"]])
            if not descripcion or total_linea is None:
                continue
            items.append({
                "descripcion": descripcion,
                "cantidad": a_entero(fila[mapa["cantidad"]]) if "cantidad" in mapa else None,
                "precio_unitario": a_entero(fila[mapa["precio_unitario"]]) if "precio_unitario" in mapa else None,
                "total_linea": total_linea,
            })
    return items


def validar(f: Factura) -> None:
    """Agrega observaciones si faltan datos o los montos no cuadran."""
    obligatorios = {"rut_proveedor": "RUT del proveedor", "folio": "folio", "fecha": "fecha",
                    "neto": "monto neto", "iva": "IVA", "total": "total"}
    for atributo, nombre in obligatorios.items():
        if getattr(f, atributo) is None:
            f.observaciones.append(f"No se encontró el {nombre}")

    if f.rut_proveedor and not rut_util.es_valido(f.rut_proveedor):
        f.observaciones.append(f"RUT del proveedor inválido (dígito verificador): {rut_util.con_puntos(f.rut_proveedor)}")

    if f.neto is not None and f.iva is not None:
        esperado = round(f.neto * TASA_IVA)
        if abs(esperado - f.iva) > TOLERANCIA:
            f.observaciones.append(f"IVA no corresponde al 19% del neto (esperado {esperado:,})".replace(",", "."))
    if None not in (f.neto, f.iva, f.total) and abs(f.neto + f.iva - f.total) > TOLERANCIA:
        diferencia = f.total - (f.neto + f.iva)
        f.observaciones.append(f"Total no cuadra con neto + IVA (diferencia {diferencia:+,})".replace(",", "."))
    if f.items and f.neto is not None:
        suma = sum(i["total_linea"] for i in f.items)
        if abs(suma - f.neto) > TOLERANCIA:
            f.observaciones.append(f"Suma del detalle ({suma:,}) distinta del neto".replace(",", "."))
    for item in f.items:
        if item["cantidad"] and item["precio_unitario"] and \
                abs(item["cantidad"] * item["precio_unitario"] - item["total_linea"]) > TOLERANCIA:
            f.observaciones.append(f"Línea con cantidad × precio incorrecto: {item['descripcion']}")


def extraer_de_texto(texto: str, tablas: list, archivo: str) -> Factura:
    f = Factura(archivo=archivo)
    if "factura" not in _sin_tildes(texto):
        f.observaciones.append("No es una factura (no se encontró la palabra 'Factura')")
        return f

    ruts = rut_util.buscar_todos(texto)
    if not ruts and PATRONES["total"].search(texto) is None:
        # Menciona "factura" pero no tiene RUT ni total: cotización, guía, carta, etc.
        f.observaciones.append("No es una factura (no tiene RUT ni total)")
        return f
    f.rut_proveedor = ruts[0] if ruts else None
    f.rut_cliente = ruts[1] if len(ruts) > 1 else None
    f.proveedor = _proveedor(texto)
    f.folio = a_entero(_primero("folio", texto))
    fecha = _primero("fecha", texto)
    f.fecha = _fecha(fecha) if fecha else None
    f.neto = a_entero(_primero("neto", texto))
    f.iva = a_entero(_primero("iva", texto))
    f.total = a_entero(_primero("total", texto, ultimo=True))
    f.items = _items(tablas)
    validar(f)
    return f


def extraer(ruta: Path) -> Factura:
    ruta = Path(ruta)
    try:
        with pdfplumber.open(ruta) as pdf:
            texto = "\n".join(p.extract_text() or "" for p in pdf.pages)
            tablas = [t for p in pdf.pages for t in p.extract_tables()]
    except Exception as error:  # PDF dañado o protegido
        f = Factura(archivo=ruta.name)
        f.observaciones.append(f"No es una factura legible: no se pudo abrir el PDF ({type(error).__name__})")
        return f
    if not texto.strip():
        f = Factura(archivo=ruta.name)
        f.observaciones.append("No es una factura legible: el PDF no tiene texto (¿escaneado? requiere OCR)")
        return f
    return extraer_de_texto(texto, tablas, ruta.name)


def extraer_carpeta(carpeta: Path) -> list[Factura]:
    carpeta = Path(carpeta)
    if not carpeta.is_dir():
        raise FileNotFoundError(f"No existe la carpeta: {carpeta}")
    archivos = sorted(p for p in carpeta.iterdir() if p.suffix.lower() == ".pdf")
    if not archivos:
        raise ValueError(f"No hay archivos PDF en {carpeta}")
    facturas = [extraer(p) for p in archivos]

    # La misma factura (proveedor + folio) cargada dos veces
    vistas: dict[tuple, str] = {}
    for f in facturas:
        if f.rut_proveedor and f.folio:
            clave = (f.rut_proveedor, f.folio)
            if clave in vistas:
                f.observaciones.append(f"Factura duplicada: mismo proveedor y folio que {vistas[clave]}")
            else:
                vistas[clave] = f.archivo
    return facturas
