"""Extrae los datos de una carpeta de facturas PDF y los guarda en Excel.

Uso:
    python extraer_facturas.py facturas_ejemplo
    python extraer_facturas.py "C:/Facturas/Septiembre" --salida facturas_septiembre.xlsx
"""

import argparse
import sys
from pathlib import Path

from extractor_facturas.excel import generar_excel
from extractor_facturas.extraccion import extraer_carpeta


def main() -> int:
    parser = argparse.ArgumentParser(description="Extrae datos de facturas PDF a Excel.")
    parser.add_argument("carpeta", type=Path, help="Carpeta con las facturas en PDF")
    parser.add_argument("--salida", type=Path, default=Path("facturas_extraidas.xlsx"),
                        help="Ruta del Excel a generar")
    args = parser.parse_args()

    try:
        facturas = extraer_carpeta(args.carpeta)
    except (FileNotFoundError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    generar_excel(facturas, args.salida)
    for f in facturas:
        simbolo = {"OK": "OK     ", "Revisar": "REVISAR", "No reconocido": "OMITIDO"}[f.estado]
        detalle = f" - {f.observaciones[0]}" if f.observaciones else ""
        print(f"  [{simbolo}] {f.archivo}{detalle}")
    total_ok = sum(f.total for f in facturas if f.estado == "OK")
    print(f"\nExcel generado: {args.salida}")
    print(f"Total facturas OK: ${total_ok:,}".replace(",", "."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
