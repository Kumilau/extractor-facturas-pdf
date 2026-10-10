"""Genera facturas PDF ficticias para probar el extractor.

Uso:
    python generar_facturas_ejemplo.py                 # 12 facturas en facturas_ejemplo/
    python generar_facturas_ejemplo.py --cantidad 30

Crea dos formatos de proveedor distintos e incluye, a propósito, una factura con
el total mal calculado, una con RUT inválido y un PDF que no es factura.
Todos los nombres, RUT y montos son inventados.
"""

import argparse
import random
from datetime import date, timedelta
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from extractor_facturas.rut import formatear

PROVEEDORES_A = [  # formato clásico
    ("Embalajes del Sur SpA", 76482113),
    ("Transportes Cordillera Ltda.", 77215908),
    ("Servicios Portuarios Bahía S.A.", 96874320),
]
PROVEEDORES_B = [  # formato moderno
    ("TecnoOficina Chile SpA", 77930441),
    ("Combustibles Ruta 5 Ltda.", 76118562),
]
CLIENTE = ("Comercial Logística Ejemplo Ltda.", 76555222)

PRODUCTOS = {
    "Embalajes del Sur SpA": [("Pallet de madera 120x100", 8500), ("Film stretch 50 cm", 12900),
                              ("Caja corrugada doble", 1450), ("Zuncho plástico rollo", 18900)],
    "Transportes Cordillera Ltda.": [("Flete Santiago - San Antonio", 285000),
                                     ("Flete Santiago - Valparaíso", 310000), ("Estadía camión (hora)", 25000)],
    "Servicios Portuarios Bahía S.A.": [("Almacenaje contenedor 20' (día)", 42000),
                                        ("Manipulación de carga", 95000), ("Consolidación LCL", 168000)],
    "TecnoOficina Chile SpA": [("Resma papel carta", 4290), ("Tóner impresora láser", 58900),
                               ("Etiquetas térmicas rollo", 7990)],
    "Combustibles Ruta 5 Ltda.": [("Petróleo diésel (litro)", 1089), ("Lubricante motor 5 L", 32500)],
}


def pesos(monto: int) -> str:
    return f"{monto:,}".replace(",", ".")


def items_aleatorios(proveedor: str, rng: random.Random) -> list[tuple[int, str, int]]:
    elegidos = rng.sample(PRODUCTOS[proveedor], k=rng.randint(1, len(PRODUCTOS[proveedor])))
    resultado = []
    for nombre, precio in elegidos:
        cantidad = rng.randint(100, 900) if "litro" in nombre else rng.randint(1, 40)
        resultado.append((cantidad, nombre, precio))
    return resultado


def _estilo_tabla(color_encabezado) -> TableStyle:
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), color_encabezado),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (-2, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ])


def factura_formato_a(ruta, proveedor, rut_emisor, folio, fecha, items, total_override=None):
    estilos = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(ruta), pagesize=letter, topMargin=1.5 * cm)
    neto = sum(c * p for c, _, p in items)
    iva = round(neto * 0.19)
    total = total_override if total_override is not None else neto + iva

    encabezado = Table([
        [Paragraph(f"<b>{proveedor}</b><br/>Giro: Servicios logísticos<br/>Av. Ejemplo 1234, Santiago", estilos["Normal"]),
         Paragraph(f"<para align=center><font color=red><b>R.U.T.: {rut_emisor}<br/>FACTURA ELECTRÓNICA<br/>"
                   f"N° {folio}</b></font></para>", estilos["Normal"])],
    ], colWidths=[10 * cm, 7 * cm])
    encabezado.setStyle(TableStyle([("BOX", (1, 0), (1, 0), 1.5, colors.red), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))

    filas = [["Cantidad", "Descripción", "Precio Unit.", "Total"]]
    filas += [[str(c), d, pesos(p), pesos(c * p)] for c, d, p in items]
    detalle = Table(filas, colWidths=[2.2 * cm, 8.8 * cm, 3 * cm, 3 * cm])
    detalle.setStyle(_estilo_tabla(colors.HexColor("#7F7F7F")))

    totales = Table([["Monto Neto", f"$ {pesos(neto)}"], ["IVA (19%)", f"$ {pesos(iva)}"],
                     ["Total", f"$ {pesos(total)}"]], colWidths=[3 * cm, 3 * cm], hAlign="RIGHT")
    totales.setStyle(TableStyle([("ALIGN", (1, 0), (1, -1), "RIGHT"), ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
                                 ("LINEABOVE", (0, 2), (-1, 2), 1, colors.black)]))

    doc.build([
        encabezado, Spacer(1, 0.6 * cm),
        Paragraph(f"Fecha de emisión: {fecha:%d/%m/%Y}", estilos["Normal"]),
        Paragraph(f"Señor(es): {CLIENTE[0]}", estilos["Normal"]),
        Paragraph(f"RUT: {formatear(CLIENTE[1])}", estilos["Normal"]),
        Spacer(1, 0.5 * cm), detalle, Spacer(1, 0.5 * cm), totales,
    ])


def factura_formato_b(ruta, proveedor, rut_emisor, folio, fecha, items, total_override=None):
    estilos = getSampleStyleSheet()
    titulo = ParagraphStyle("t", parent=estilos["Title"], textColor=colors.HexColor("#1F4E79"), alignment=0)
    doc = SimpleDocTemplate(str(ruta), pagesize=letter, topMargin=1.5 * cm)
    neto = sum(c * p for c, _, p in items)
    iva = round(neto * 0.19)
    total = total_override if total_override is not None else neto + iva

    filas = [["Código", "Producto", "Cant.", "Unitario", "Subtotal"]]
    filas += [[f"P-{100 + i}", d, str(c), pesos(p), pesos(c * p)] for i, (c, d, p) in enumerate(items)]
    detalle = Table(filas, colWidths=[2 * cm, 8 * cm, 1.8 * cm, 2.6 * cm, 2.6 * cm])
    detalle.setStyle(_estilo_tabla(colors.HexColor("#1F4E79")))

    doc.build([
        Paragraph("Factura Electrónica", titulo),
        Paragraph(f"Emisor: {proveedor} - RUT {rut_emisor}", estilos["Normal"]),
        Paragraph(f"Folio: {folio}", estilos["Normal"]),
        Paragraph(f"Fecha: {fecha:%Y-%m-%d}", estilos["Normal"]),
        Paragraph(f"Cliente: {CLIENTE[0]} - RUT {formatear(CLIENTE[1])}", estilos["Normal"]),
        Spacer(1, 0.6 * cm), detalle, Spacer(1, 0.5 * cm),
        Paragraph(f"<para align=right>Neto: {pesos(neto)}<br/>IVA 19%: {pesos(iva)}<br/>"
                  f"<b>TOTAL A PAGAR: {pesos(total)}</b></para>", estilos["Normal"]),
    ])


def documento_no_factura(ruta):
    estilos = getSampleStyleSheet()
    SimpleDocTemplate(str(ruta), pagesize=letter).build([
        Paragraph("Cotización de servicios", estilos["Title"]),
        Paragraph("Este documento es una cotización referencial y no constituye factura.", estilos["Normal"]),
    ])


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera facturas PDF ficticias.")
    parser.add_argument("--cantidad", type=int, default=12)
    parser.add_argument("--semilla", type=int, default=2026)
    parser.add_argument("--carpeta", type=Path, default=Path("facturas_ejemplo"))
    args = parser.parse_args()

    rng = random.Random(args.semilla)
    args.carpeta.mkdir(parents=True, exist_ok=True)
    for i in range(args.cantidad):
        formato_a = i % 3 != 2
        proveedor, cuerpo = rng.choice(PROVEEDORES_A if formato_a else PROVEEDORES_B)
        rut = formatear(cuerpo)
        folio = rng.randint(1000, 99999)
        fecha = date(2026, 1, 5) + timedelta(days=rng.randint(0, 260))
        items = items_aleatorios(proveedor, rng)
        total_override = None
        if i == 4:  # total mal calculado por el proveedor
            neto = sum(c * p for c, _, p in items)
            total_override = neto + round(neto * 0.19) + 10000
        if i == 7:  # RUT con dígito verificador incorrecto
            rut = rut[:-1] + ("1" if rut[-1] != "1" else "2")
        nombre = f"factura_{folio}.pdf"
        generar = factura_formato_a if formato_a else factura_formato_b
        generar(args.carpeta / nombre, proveedor, rut, folio, fecha, items, total_override)

    documento_no_factura(args.carpeta / "cotizacion_referencial.pdf")
    print(f"Listo: {args.cantidad} facturas y 1 cotización en {args.carpeta}/")


if __name__ == "__main__":
    main()
