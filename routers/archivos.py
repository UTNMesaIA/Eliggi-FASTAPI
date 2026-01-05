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
async def procesar_zip_sqlite(
    file: UploadFile = File(...), 
    codigos: str = Form(...), 
    codigosProveedor: str = Form(...) # Nuevo parámetro
):
    print(f"--- INICIO PROCESO: {file.filename} ---")
    
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, "archivo.zip")
    
    try:
        # 1. Validar inputs (Parsear ambos JSONs)
        lista_codigos = []
        lista_codigos_prov = []
        
        try:
            # Parsear lista 1 (Codigo)
            if codigos:
                lista_codigos = json.loads(codigos)
                if not isinstance(lista_codigos, list): raise ValueError
            
            # Parsear lista 2 (CodigoParticular)
            if codigosProveedor:
                lista_codigos_prov = json.loads(codigosProveedor)
                if not isinstance(lista_codigos_prov, list): raise ValueError

            print(f"LOG INPUT: Buscando {len(lista_codigos)} por 'Codigo' y {len(lista_codigos_prov)} por 'CodigoParticular'.")
            
        except:
            return {"error": "Los campos 'codigos' y 'codigosProveedor' deben ser arrays JSON validos"}

        # 2. Guardar y extraer ZIP
        with open(zip_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        db_path = None
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(temp_dir)
                for filename in zf.namelist():
                    if filename.endswith(('.sqlite', '.db', '.sqlite3')):
                        db_path = os.path.join(temp_dir, filename)
                        print(f"LOG DB: Base de datos encontrada: {filename}")
                        break
        except zipfile.BadZipFile:
            return {"error": "ZIP inválido"}

        if not db_path: return {"error": "No hay .sqlite en el ZIP"}

        # 3. Conexión y Lógica de Búsqueda
        conn = sqlite3.connect(db_path)
        dfs = [] # Lista para guardar los dataframes parciales

        try:
            # --- DIAGNÓSTICO (IMPORTANTE VER ESTO EN CONSOLA) ---
            cursor = conn.cursor()
            # Verificar nombres de columnas en tabla Articulos
            try:
                info_cols = cursor.execute("PRAGMA table_info(Articulos)").fetchall()
                nombres_cols = [c[1] for c in info_cols]
                print(f"LOG INSPECCION: Columnas en Articulos: {nombres_cols}")
                
                if 'CodigoParticular' not in nombres_cols:
                    print("LOG WARNING: ¡La columna 'CodigoParticular' NO PARECE EXISTIR en la tabla!")
            except Exception as e:
                print(f"LOG ERROR INSPECCION: No se pudo inspeccionar la tabla Articulos. {e}")
            # ----------------------------------------------------

            # BÚSQUEDA A: Por 'Codigo'
            if lista_codigos:
                placeholders = ','.join('?' for _ in lista_codigos)
                query_main = f"SELECT * FROM Articulos WHERE Codigo IN ({placeholders})"
                print("LOG QUERY A: Ejecutando búsqueda por columna 'Codigo'...")
                
                df_main = pd.read_sql_query(query_main, conn, params=lista_codigos)
                print(f"LOG RESULTADO A: {len(df_main)} matches encontrados por Codigo.")
                dfs.append(df_main)

            # BÚSQUEDA B: Por 'CodigoParticular'
            if lista_codigos_prov:
                placeholders_prov = ','.join('?' for _ in lista_codigos_prov)
                query_prov = f"SELECT * FROM Articulos WHERE CodigoParticular IN ({placeholders_prov})"
                print("LOG QUERY B: Ejecutando búsqueda por columna 'CodigoParticular'...")
                
                df_prov = pd.read_sql_query(query_prov, conn, params=lista_codigos_prov)
                print(f"LOG RESULTADO B: {len(df_prov)} matches encontrados por CodigoParticular.")
                dfs.append(df_prov)

            # 4. Unificar y limpiar duplicados
            if dfs:
                # Concatenamos los resultados de ambas búsquedas
                df_final = pd.concat(dfs)
                
                # Eliminamos duplicados (si un articulo se encontró por los dos lados)
                # drop_duplicates() sin argumentos chequea que TODAS las columnas sean iguales
                len_antes = len(df_final)
                df_final = df_final.drop_duplicates()
                len_despues = len(df_final)
                
                if len_antes != len_despues:
                    print(f"LOG LIMPIEZA: Se eliminaron {len_antes - len_despues} duplicados (artículos encontrados por ambas vías).")

                resultado = df_final.to_dict(orient="records")
            else:
                resultado = []

        except Exception as sql_e:
            print(f"LOG ERROR SQL: {str(sql_e)}")
            return {"error": "Error SQL", "detalle": str(sql_e)}
        finally:
            conn.close()

        return {
            "mensaje": "Éxito", 
            "total_encontrados": len(resultado), 
            "datos": resultado
        }
        
    except Exception as e:
        print(f"LOG ERROR SERVIDOR: {str(e)}")
        return {"error": "Error servidor", "detalle": str(e)}
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)