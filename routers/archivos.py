import io
import os
import json
import shutil
import sqlite3
import zipfile
import tempfile
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles.colors import COLOR_INDEX
from fastapi import APIRouter, UploadFile, File, Form
from typing import List

router = APIRouter()

# ==========================================
# FUNCIONES AUXILIARES DE COLOR (REFORZADAS)
# ==========================================

def get_color_from_cell(cell):
    try:
        if not cell.fill or not hasattr(cell.fill, 'start_color'):
            return None
        sc = cell.fill.start_color
        if sc.type == 'rgb' and sc.rgb and isinstance(sc.rgb, str):
            color = str(sc.rgb).upper()
            return color[-6:] if len(color) >= 6 else color
        if sc.type == 'indexed' and sc.indexed is not None:
            try:
                idx_color = COLOR_INDEX[sc.indexed]
                return str(idx_color).upper()[-6:]
            except:
                pass
        if sc.type == 'theme':
            return f"THEME_{sc.theme}"
        return None
    except:
        return None

def hex_to_rgb(hex_code):
    if not hex_code or "THEME" in str(hex_code):
        return None
    try:
        h = str(hex_code).strip().upper()
        if h.startswith('#'): h = h[1:]
        if len(h) != 6: return None
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    except:
        return None

def color_distance(c1, c2):
    if not c1 or not c2: return 999
    return sum((a - b) ** 2 for a, b in zip(c1, c2)) ** 0.5

def interpretar_stock_por_valor_y_color(cell):
    val_texto = str(cell.value).strip().upper() if cell.value else ""
    
    # Prioridad Texto (SI/NO)
    if val_texto in ["SI", "HAY", "STOCK", "DISPONIBLE"]:
        return "HAY STOCK", "TEXTO_SI"
    if val_texto in ["NO", "SIN", "AGOTADO"]:
        return "NO HAY STOCK", "TEXTO_NO"

    raw_color = get_color_from_cell(cell)
    if not raw_color:
        return "NO DEFINIDO", "SIN_INFO"

    rgb = hex_to_rgb(raw_color)
    if not rgb:
        # Fallback para colores de tema
        if raw_color in ["THEME_5", "THEME_9"]: return "CONSULTAR", raw_color
        if raw_color in ["THEME_4", "THEME_8"]: return "HAY STOCK", raw_color
        if raw_color in ["THEME_6", "THEME_7"]: return "NO HAY STOCK", raw_color
        return "DESCONOCIDO", raw_color

    # Ajuste de objetivos y orden de detección para evitar falsos verdes
    targets = {
        "CONSULTAR": [(255, 255, 0), (255, 230, 0), (255, 255, 102), (255, 192, 0), (255, 255, 153)],
        "HAY STOCK": [(0, 176, 80), (0, 255, 0), (146, 208, 80), (0, 128, 0), (0, 255, 153)],
        "NO HAY STOCK": [(255, 0, 0), (192, 0, 0), (255, 102, 102), (255, 199, 206)]
    }
    
    # Tolerancia más ajustada para evitar solapamientos entre amarillo y verde claro
    TOLERANCIA = 110
    
    for estado, colores_rgb in targets.items():
        for target_rgb in colores_rgb:
            if color_distance(rgb, target_rgb) < TOLERANCIA:
                return estado, raw_color

    return "DESCONOCIDO", raw_color

# ==========================================
# ENDPOINT: PROCESAR INVENTARIO
# ==========================================

@router.post("/procesar-inventario-completo/")
async def procesar_inventario_completo(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        wb = load_workbook(io.BytesIO(contents), data_only=True)
        lista_consolidada = []

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            
            # 1. Encontrar la fila de encabezados
            header_row_idx = 1
            idx_stock = -1
            idx_codigo = 0
            headers = []

            for r in range(1, 6):
                row_cells = list(ws.iter_rows(min_row=r, max_row=r))[0]
                temp_headers = [str(c.value).strip().upper() if c.value else "" for c in row_cells]
                if "STOCK" in temp_headers or "CODIGO" in temp_headers or "CODIGOS" in temp_headers:
                    header_row_idx = r
                    headers = [h if h else f"COL_{i}" for i, h in enumerate(temp_headers)]
                    for i, h in enumerate(headers):
                        if h == "STOCK": idx_stock = i
                        if h in ["CODIGO", "CODIGOS"]: idx_codigo = i
                    break
            
            if not headers:
                headers = [str(c.value).strip().upper() if c.value else f"COL_{i}" for i, c in enumerate(ws[1])]
                for i, h in enumerate(headers):
                    if h == "STOCK": idx_stock = i
                    if h in ["CODIGO", "CODIGOS"]: idx_codigo = i

            # 2. Procesar filas de datos
            for row in ws.iter_rows(min_row=header_row_idx + 1):
                raw_codigo = row[idx_codigo].value
                if raw_codigo is None or str(raw_codigo).strip() == "":
                    continue

                item = {
                    "ORIGEN_HOJA": sheet_name,
                    "CODIGO": str(raw_codigo).strip()
                }

                for idx, cell in enumerate(row):
                    if idx >= len(headers): break
                    nombre_col = headers[idx]
                    item[nombre_col] = cell.value

                    if idx == idx_stock:
                        estado, raw_info = interpretar_stock_por_valor_y_color(cell)
                        item["STOCK_ESTADO"] = estado
                        item["STOCK_DETALLE"] = raw_info

                lista_consolidada.append(item)

        return {
            "archivo": file.filename,
            "total_items": len(lista_consolidada),
            "datos": lista_consolidada
        }

    except Exception as e:
        import traceback
        return {"error": str(e), "trace": traceback.format_exc()}

@router.post("/leer-excel/")
async def leer_excel(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        wb = load_workbook(io.BytesIO(contents), data_only=True)
        resultado = {}
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            if ws.max_row < 2: continue
            headers = [str(c.value) for c in ws[1]]
            hoja_datos = []
            for row in ws.iter_rows(min_row=2):
                fila = {}
                for idx, cell in enumerate(row):
                    if idx >= len(headers): break
                    fila[headers[idx]] = cell.value
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