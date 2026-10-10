# Extractor de Facturas PDF a Excel

Script en Python que lee una carpeta de **facturas electrónicas chilenas en PDF** y genera un Excel con los datos de cada una: proveedor, RUT, folio, fecha, neto, IVA, total y detalle de productos. Además **valida** cada factura y separa las que necesitan revisión antes de contabilizarse.

Pensado para áreas de contabilidad, compras y administración que hoy digitan las facturas a mano.

**Tecnologías:** Python · pdfplumber · openpyxl · pytest

## El problema

Digitar facturas a mano es lento y propenso a errores: un número mal tipeado, una factura ingresada dos veces o un total mal calculado por el proveedor pueden pasar sin que nadie lo note.

## La solución

```bash
python extraer_facturas.py carpeta_con_facturas
```

```
  [OMITIDO] cotizacion_referencial.pdf - No es una factura (no tiene RUT ni total)
  [OK     ] factura_15514.pdf
  [REVISAR] factura_47745.pdf - Total no cuadra con neto + IVA (diferencia +10.000)
  [REVISAR] factura_66333.pdf - RUT del proveedor inválido (dígito verificador): 96.874.320-2
  ...
Excel generado: facturas_extraidas.xlsx
Total facturas OK: $33.457.476
```

### Qué extrae

- Proveedor, RUT del proveedor y del cliente
- Folio y fecha de emisión (`19/09/2026` o `2026-09-19`)
- Monto neto, IVA y total, en formato chileno (`$ 1.250.000`)
- Detalle de productos: descripción, cantidad, precio unitario y total de cada línea

Funciona con **distintos formatos de proveedor**: identifica las columnas del detalle por su nombre (Cantidad o Cant., Descripción o Producto, Total o Subtotal), no por su posición.

### Qué valida

| Validación | Ejemplo de lo que detecta |
| --- | --- |
| RUT del proveedor | Dígito verificador incorrecto (algoritmo módulo 11) |
| IVA | Que no corresponda al 19% del neto |
| Total | Que no sea igual a neto + IVA |
| Detalle | Que la suma de las líneas no coincida con el neto, o que cantidad × precio no dé el total de la línea |
| Duplicados | La misma factura (proveedor + folio) incluida dos veces |
| Campos faltantes | Folio, fecha o montos que no aparecen |
| Documentos ajenos | Cotizaciones u otros PDF que no son facturas |
| PDF escaneados | Avisa que el PDF no tiene texto y necesita OCR |

## El Excel

| Hoja | Contenido |
| --- | --- |
| Facturas | Una fila por factura con sus datos, estado (OK o Revisar) y totales |
| Detalle | Una fila por producto o servicio de cada factura |
| Por proveedor | Cantidad de facturas y montos totales por proveedor |
| Revisión | Documentos con observaciones y el motivo de cada una |

En [`ejemplos/facturas_extraidas_ejemplo.xlsx`](ejemplos/facturas_extraidas_ejemplo.xlsx) hay un Excel generado a partir de las facturas de [`facturas_ejemplo/`](facturas_ejemplo/).

## Instalación y uso

Requisitos: Python 3.10 o superior.

```bash
pip install -r requirements.txt

# Crear facturas de prueba (ficticias)
python generar_facturas_ejemplo.py

# Extraer los datos
python extraer_facturas.py facturas_ejemplo --salida facturas.xlsx
```

## Pruebas

```bash
pip install pytest
python -m pytest
```

Las pruebas cubren la validación de RUT, los dos formatos de factura, cada tipo de error, la lectura de PDF reales generados en la prueba y la estructura del Excel.

## Estructura

```
├── extraer_facturas.py          Comando principal
├── generar_facturas_ejemplo.py  Crea facturas PDF ficticias
├── extractor_facturas/
│   ├── extraccion.py            Lectura del PDF, extracción y validación
│   ├── rut.py                   Validación de RUT chileno
│   └── excel.py                 Excel con formato
├── facturas_ejemplo/            Facturas de prueba
├── tests/                       Pruebas automáticas
└── ejemplos/                    Excel de ejemplo
```

## Adaptaciones posibles

- Formatos de nuevos proveedores, ajustando las reglas de extracción
- Lectura de facturas escaneadas con OCR
- Lectura directa del XML del SII cuando esté disponible
- Envío del resultado a un sistema contable o a Google Sheets
- Procesamiento automático de los PDF que llegan por correo

---

Desarrollado por Lau, Analista Programadora. Todas las facturas, empresas y RUT de ejemplo son ficticios.
