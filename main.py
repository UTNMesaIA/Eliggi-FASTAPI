from fastapi import FastAPI, UploadFile, File, Form
from typing import List
from openpyxl import load_workbook
from fastapi.middleware.cors import CORSMiddleware
import io

app = FastAPI()

# CORS config
origins = [
    "https://utnmesaia.app.n8n.cloud",
    "https://www.postman.com",
    "http://localhost:3000",
    "http://localhost:8000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/procesar-excel/")
async def procesar_excel(
    file: UploadFile = File(...),
    codigo_col: str = Form(...),
    stock_col: str = Form(...)
):
    contents = await file.read()
    wb = load_workbook(io.BytesIO(contents))
    ws = wb.active

    headers = [cell.value for cell in ws[1]]

    try:
        codigo_index = headers.index(codigo_col)
        stock_index = headers.index(stock_col)
    except ValueError:
        return {"error": "No se encontraron las columnas especificadas"}

    output = []

    for row in ws.iter_rows(min_row=2):
        codigo = row[codigo_index].value
        stock_value = row[stock_index].value

        fill = row[stock_index].fill
        color = None
        if fill and fill.start_color and fill.start_color.rgb:
            color = fill.start_color.rgb

        estado = interpretar_color(color)

        output.append({
            "codigo": codigo,
            "stock_value": stock_value,
            "color": color,
            "estado": estado
        })

    return output

# Función: convertir hex a RGB
def hex_to_rgb(hex_code):
    if hex_code is None:
        return None
    hex_code = hex_code[-6:]  # tomar últimos 6 caracteres
    r = int(hex_code[0:2], 16)
    g = int(hex_code[2:4], 16)
    b = int(hex_code[4:6], 16)
    return (r, g, b)

# Función: calcular distancia entre colores
def color_distance(c1, c2):
    return sum((a - b) ** 2 for a, b in zip(c1, c2)) ** 0.5

# Función: interpretar color por cercanía
def interpretar_color(color_hex: str):
    if not color_hex:
        return "NO DEFINIDO"
    
    color = hex_to_rgb(color_hex)

    # Colores base
    verde = (0, 255, 0)
    rojo = (255, 0, 0)
    amarillo = (255, 255, 0)

    TOLERANCIA = 100  # rango de cercanía

    if color_distance(color, verde) < TOLERANCIA:
        return "HAY STOCK"
    elif color_distance(color, amarillo) < TOLERANCIA:
        return "PREGUNTAR"
    elif color_distance(color, rojo) < TOLERANCIA:
        return "NO HAY STOCK"
    else:
        return "DESCONOCIDO"
