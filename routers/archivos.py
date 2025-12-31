import io
import os
import json
import shutil
import sqlite3
import tempfile
import pandas as pd
from openpyxl import load_workbook
from fastapi import APIRouter, UploadFile, File, Form

router = APIRouter()

# ==========================================
# FUNCIONES AUXILIARES (COLORES EXCEL)
# ==========================================

def hex_to_rgb(hex_code):
    if hex_code is None:
        return None
    hex_code = str(hex_code)
    if len(hex_code) > 6:
        hex_code = hex_code[-6:]
    return tuple(int(hex_code[i:i+2], 16) for i in (0, 2, 4))

def color_distance(c1, c2):
    return sum((a - b) ** 2 for a, b in zip(c1, c2)) ** 0.5

def interpretar_color(color_hex: str):
    if not color_hex:
        return "NO DEFINIDO"
    try:
        color = hex_to_rgb(color_hex)
    except:
        return "NO DEFINIDO"

    verdes = [(0, 255, 0), (0, 176, 80), (144, 238, 144)]
    amarillos = [(255, 255, 0), (255, 230, 0), (255, 255, 153)]
    rojos = [(255, 0, 0), (192, 0, 0), (255, 102, 102)]
    TOLERANCIA = 100

    for verde in verdes:
        if color_distance(color, verde) < TOLERANCIA: return "HAY STOCK"
    for amarillo in amarillos:
        if color_distance(color, amarillo) < TOLERANCIA: return "PREGUNTAR"
    for rojo in rojos:
        if color_distance(color, rojo) < TOLERANCIA: return "NO HAY STOCK"

    return "DESCONOCIDO"

# ==========================================
# ENDPOINTS
# ==========================================

@router.post("/leer-excel/")
async def leer_excel(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        wb = load_workbook(io.BytesIO(contents), data_only=True)
        resultado = {}

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            if ws.max_row < 2: continue
                
            headers = [cell.value for cell in ws[1]]
            hoja_datos = []

            for row in ws.iter_rows(min_row=2):
                fila = {}
                for idx, cell in enumerate(row):
                    if idx >= len(headers): break
                    col_name = headers[idx] if headers[idx] else f"Col_{idx}"
                    valor = cell.value

                    color = None
                    estado = "NO DEFINIDO"
                    if (cell.fill and cell.fill.start_color and 
                        hasattr(cell.fill.start_color, 'rgb') and 
                        isinstance(cell.fill.start_color.rgb, str)):
                        color = cell.fill.start_color.rgb
                        estado = interpretar_color(color)

                    fila[str(col_name)] = valor
                    fila[f"{col_name}__color"] = color
                    fila[f"{col_name}__estado"] = estado

                hoja_datos.append(fila)
            resultado[sheet_name] = hoja_datos
        return resultado
    except Exception as e:
        return {"error": "Error interno", "detalle": str(e)}

@router.post("/extract")
async def extract(file: UploadFile = File(...)):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite")
    try:
        contents = await file.read()
        tmp.write(contents)
        tmp.close()
        conn = sqlite3.connect(tmp.name)
        df = pd.read_sql("SELECT * FROM Articulos", conn)
        conn.close()
        return df.to_dict(orient="records")
    except Exception as e:
        return {"error": str(e)}
    finally:
        os.unlink(tmp.name)

@router.post("/procesar-zip-sqlite/")
async def procesar_zip_sqlite(file: UploadFile = File(...), codigos: str = Form(...)):
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, "archivo.zip")
    try:
        try:
            lista_codigos = json.loads(codigos)
            if not isinstance(lista_codigos, list): raise ValueError
        except:
            return {"error": "El campo 'codigos' debe ser array JSON"}

        with open(zip_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        db_path = None
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(temp_dir)
                for filename in zf.namelist():
                    if filename.endswith(('.sqlite', '.db', '.sqlite3')):
                        db_path = os.path.join(temp_dir, filename)
                        break
        except zipfile.BadZipFile:
            return {"error": "ZIP inválido"}

        if not db_path: return {"error": "No hay .sqlite en el ZIP"}

        conn = sqlite3.connect(db_path)
        placeholders = ','.join('?' for _ in lista_codigos)
        query = f"SELECT * FROM Articulos WHERE Codigo IN ({placeholders})"
        try:
            df = pd.read_sql_query(query, conn, params=lista_codigos)
            resultado = df.to_dict(orient="records")
        except Exception as sql_e:
            return {"error": "Error SQL", "detalle": str(sql_e)}
        finally:
            conn.close()

        return {"mensaje": "Éxito", "encontrados": len(resultado), "datos": resultado}
    except Exception as e:
        return {"error": "Error servidor", "detalle": str(e)}
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)