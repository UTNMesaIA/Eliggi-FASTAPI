import io
import os
import json
import shutil
import sqlite3
import zipfile
import tempfile
import pandas as pd
from openpyxl import load_workbook
from fastapi import APIRouter, UploadFile, File, Form
from typing import List

router = APIRouter()

# ==========================================
# FUNCIONES AUXILIARES (COLORES EXCEL)
# ==========================================

def hex_to_rgb(hex_code):
    if hex_code is None:
        return None
    hex_code = str(hex_code)
    # Excel a veces devuelve ARGB (8 caracteres), nos quedamos con los últimos 6 (RGB)
    if len(hex_code) > 6:
        hex_code = hex_code[-6:]
    try:
        return tuple(int(hex_code[i:i+2], 16) for i in (0, 2, 4))
    except (ValueError, TypeError):
        return None

def color_distance(c1, c2):
    if not c1 or not c2: return 999
    return sum((a - b) ** 2 for a, b in zip(c1, c2)) ** 0.5

def interpretar_color(color_hex: str):
    """
    Analiza el color hexadecimal y devuelve el estado del stock.
    """
    if not color_hex or color_hex == '00000000': 
        return "NO DEFINIDO"
    
    color = hex_to_rgb(color_hex)
    if not color:
        return "NO DEFINIDO"

    # Paletas de colores objetivo (Verdes, Amarillos, Rojos)
    verdes = [(0, 255, 0), (0, 176, 80), (144, 238, 144), (34, 139, 34)]
    amarillos = [(255, 255, 0), (255, 230, 0), (255, 255, 153)]
    rojos = [(255, 0, 0), (192, 0, 0), (255, 102, 102)]
    
    TOLERANCIA = 120 

    for verde in verdes:
        if color_distance(color, verde) < TOLERANCIA: return "HAY STOCK"
    for amarillo in amarillos:
        if color_distance(color, amarillo) < TOLERANCIA: return "PREGUNTAR"
    for rojo in rojos:
        if color_distance(color, rojo) < TOLERANCIA: return "NO HAY STOCK"

    return "DESCONOCIDO"

# ==========================================
# NUEVO: PROCESAR INVENTARIO COMPLETO (CONSOLIDADO)
# ==========================================

@router.post("/procesar-inventario-completo/")
async def procesar_inventario_completo(file: UploadFile = File(...)):
    """
    Lee todas las hojas, las junta en una sola lista y detecta stock por color.
    """
    try:
        contents = await file.read()
        wb = load_workbook(io.BytesIO(contents), data_only=True)
        lista_consolidada = []

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            if ws.max_row < 2: continue
                
            # Normalizar headers
            headers = [str(cell.value).strip().upper() if cell.value else f"COL_{i}" for i, cell in enumerate(ws[1])]
            
            # Buscar índice de columna STOCK (case insensitive)
            idx_stock = -1
            for i, h in enumerate(headers):
                if "STOCK" in h:
                    idx_stock = i
                    break

            for row_idx, row in enumerate(ws.iter_rows(min_row=2), start=2):
                if not any(cell.value for cell in row): continue

                item = {
                    "ORIGEN_HOJA": sheet_name, 
                    "FILA_EXCEL": row_idx
                }
                
                for idx, cell in enumerate(row):
                    if idx >= len(headers): break
                    col_name = headers[idx]
                    item[col_name] = cell.value

                    # Si es la columna de stock, procesar color
                    if idx == idx_stock:
                        color_hex = None
                        if cell.fill and hasattr(cell.fill, 'start_color'):
                            color_hex = cell.fill.start_color.rgb
                        
                        item["STOCK_ESTADO"] = interpretar_color(color_hex)
                        item["STOCK_COLOR_HEX"] = color_hex
                
                lista_consolidada.append(item)

        return {
            "archivo": file.filename,
            "total_items": len(lista_consolidada), 
            "datos": lista_consolidada
        }
    except Exception as e:
        return {"error": "Error al procesar el inventario", "detalle": str(e)}

# ==========================================
# ENDPOINTS ORIGINALES (MANTENIDOS)
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
                    color = cell.fill.start_color.rgb if cell.fill and hasattr(cell.fill.start_color, 'rgb') else None
                    fila[str(col_name)] = cell.value
                    fila[f"{col_name}__color"] = color
                    fila[f"{col_name}__estado"] = interpretar_color(color)
                hoja_datos.append(fila)
            resultado[sheet_name] = hoja_datos
        return resultado
    except Exception as e:
        return {"error": str(e)}

@router.post("/procesar-zip-sqlite/")
async def procesar_zip_sqlite(file: UploadFile = File(...), codigos: str = Form(...), codigosProveedor: str = Form(...)):
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, "archivo.zip")
    try:
        lista_codigos = json.loads(codigos) if codigos else []
        lista_codigos_prov = json.loads(codigosProveedor) if codigosProveedor else []
        with open(zip_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        db_path = None
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(temp_dir)
            for f in zf.namelist():
                if f.endswith(('.sqlite', '.db', '.sqlite3')):
                    db_path = os.path.join(temp_dir, f)
                    break
        if not db_path: return {"error": "No hay base de datos"}
        conn = sqlite3.connect(db_path)
        dfs = []
        if lista_codigos:
            p = ','.join('?' for _ in lista_codigos)
            dfs.append(pd.read_sql_query(f"SELECT * FROM Articulos WHERE Codigo IN ({p})", conn, params=lista_codigos))
        if lista_codigos_prov:
            p = ','.join('?' for _ in lista_codigos_prov)
            dfs.append(pd.read_sql_query(f"SELECT * FROM Articulos WHERE CodigoParticular IN ({p})", conn, params=lista_codigos_prov))
        resultado = pd.concat(dfs).drop_duplicates().to_dict(orient="records") if dfs else []
        conn.close()
        return {"mensaje": "Éxito", "total": len(resultado), "datos": resultado}
    except Exception as e:
        return {"error": str(e)}
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)