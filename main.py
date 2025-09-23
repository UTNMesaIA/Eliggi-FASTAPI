from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from openpyxl import load_workbook
import io

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def hex_to_rgb(hex_code):
    if hex_code is None:
        return None
    hex_code = hex_code[-6:]
    return tuple(int(hex_code[i:i+2], 16) for i in (0, 2, 4))

def color_distance(c1, c2):
    return sum((a - b) ** 2 for a, b in zip(c1, c2)) ** 0.5

def interpretar_color(color_hex: str):
    if not color_hex:
        return "NO DEFINIDO"

    color = hex_to_rgb(color_hex)

    verdes = [(0, 255, 0), (0, 176, 80), (144, 238, 144)]
    amarillos = [(255, 255, 0), (255, 230, 0), (255, 255, 153)]
    rojos = [(255, 0, 0), (192, 0, 0), (255, 102, 102)]

    TOLERANCIA = 100

    for verde in verdes:
        if color_distance(color, verde) < TOLERANCIA:
            return "HAY STOCK"
    for amarillo in amarillos:
        if color_distance(color, amarillo) < TOLERANCIA:
            return "PREGUNTAR"
    for rojo in rojos:
        if color_distance(color, rojo) < TOLERANCIA:
            return "NO HAY STOCK"

    return "DESCONOCIDO"

# -----------------------
# Ruta principal
# -----------------------

@app.post("/leer-excel/")
async def leer_excel(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        wb = load_workbook(io.BytesIO(contents), data_only=True)

        resultado = {}

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            headers = [cell.value for cell in ws[1]]
            hoja_datos = []

            for row in ws.iter_rows(min_row=2):
                fila = {}
                for idx, cell in enumerate(row):
                    col_name = headers[idx] if idx < len(headers) else f"Col_{idx}"
                    valor = cell.value

                    # Detectar color y estado
                    color = None
                    estado = "NO DEFINIDO"
                    if (
                        cell.fill and
                        cell.fill.start_color and
                        hasattr(cell.fill.start_color, 'rgb') and
                        isinstance(cell.fill.start_color.rgb, str)
                    ):
                        color = cell.fill.start_color.rgb
                        estado = interpretar_color(color)

                    # Guardar en la fila
                    fila[col_name] = valor
                    fila[f"{col_name}__color"] = color
                    fila[f"{col_name}__estado"] = estado

                hoja_datos.append(fila)

            resultado[sheet_name] = hoja_datos

        return resultado

    except Exception as e:
        return {
            "error": "Error interno al procesar el archivo",
            "detalle": str(e)
        }

        
from fastapi import FastAPI, UploadFile, File
import sqlite3
import pandas as pd
import tempfile

app = FastAPI()

@app.post("/extract")
async def extract(file: UploadFile = File(...)):
    # 1. Guardar archivo temporal
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite")
    contents = await file.read()
    tmp.write(contents)
    tmp.close()

    # 2. Conectar a SQLite
    conn = sqlite3.connect(tmp.name)
    cursor = conn.cursor()

    # 3. Leer tabla productos
    df = pd.read_sql("SELECT * FROM productos", conn)
    conn.close()

    # 4. Devolver en JSON
    return df.to_dict(orient="records")
