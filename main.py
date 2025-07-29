from fastapi import FastAPI, UploadFile, File, Form
from typing import List
from openpyxl import load_workbook
import io
app = FastAPI()

from fastapi.middleware.cors import CORSMiddleware

origins = [
    "https://utnmesaia.app.n8n.cloud",
    "https://www.postman.com",  # Para llamadas desde Postman web
    "http://localhost:3000",     # Si usás frontend local
    "http://localhost:8000"      # Debug local
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

def interpretar_color(color_hex: str):
    if not color_hex:
        return "NO DEFINIDO"
    color_hex = color_hex.upper()
    if color_hex.endswith("00FF00"):  # Verde
        return "HAY STOCK"
    elif color_hex.endswith("FFFF00"):  # Amarillo
        return "PREGUNTAR"
    elif color_hex.endswith("FF0000"):  # Rojo
        return "NO HAY STOCK"
    else:
        return "DESCONOCIDO"
