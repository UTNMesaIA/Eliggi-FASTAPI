from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from openpyxl import load_workbook
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

# --- Funciones auxiliares ---

def hex_to_rgb(hex_code):
    if hex_code is None:
        return None
    hex_code = hex_code[-6:]  # últimos 6 caracteres
    r = int(hex_code[0:2], 16)
    g = int(hex_code[2:4], 16)
    b = int(hex_code[4:6], 16)
    return (r, g, b)

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

# --- Ruta principal ---

@app.post("/procesar-excel/")
async def procesar_excel(
    file: UploadFile = File(...),
    codigo_col: str = Form(...),
    stock_col: str = Form(...)
):
    contents = await file.read()
    wb = load_workbook(io.BytesIO(contents))

    output = []

    for sheet in wb.sheetnames:
        ws = wb[sheet]
        headers = [cell.value for cell in ws[1]]

        try:
            codigo_index = headers.index(codigo_col)
            stock_index = headers.index(stock_col)
        except ValueError:
            continue  # Si la hoja no tiene las columnas necesarias, la salta

        for row in ws.iter_rows(min_row=2):
            codigo = row[codigo_index].value
            stock_value = row[stock_index].value

            fill = row[stock_index].fill
            color = None
            if fill and fill.start_color and fill.start_color.rgb:
                color = fill.start_color.rgb

            estado = interpretar_color(color)

            output.append({
                "hoja": sheet,
                "codigo": codigo,
                "stock_value": stock_value,
                "color": color,
                "estado": estado
            })

    return output
