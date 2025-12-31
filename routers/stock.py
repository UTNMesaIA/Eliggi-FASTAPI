from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Optional, Any
from pydantic import BaseModel, Field, validator
from sqlalchemy import Table, Column, Integer, String, Float
from database import engine, metadata, SessionLocal

router = APIRouter()

# --- DEFINICIÓN DE TABLA ---
tabla_stock = Table(
    "stock_items",
    metadata,
    Column("id", Integer, primary_key=True, index=True),
    Column("codigo", String),
    Column("articulo", String),
    Column("stock", Float),         
    Column("stock_minimo", Float),
    Column("stock_optimo", Float),
    Column("marca", String),
)

# Borrar y recrear tabla al iniciar (Opcional, útil en desarrollo)
try:
    metadata.drop_all(bind=engine)
    metadata.create_all(bind=engine)
except Exception as e:
    print(f"Error reiniciando tabla: {e}")

# --- MODELO PYDANTIC ---
# En routers/stock.py

class FilaExcel(BaseModel):
    # Definimos los campos con sus alias de Excel
    codigo: Optional[str] = Field(alias="Código", default=None)
    articulo: Optional[str] = Field(alias="Artículo", default=None)
    
    stock: Optional[float] = Field(alias="Stock", default=0.0)
    stock_minimo: Optional[float] = Field(alias="Stock Mínimo", default=0.0)
    stock_optimo: Optional[float] = Field(alias="Stock Optimo", default=0.0)
    
    marca: Optional[str] = Field(alias="Marca", default=None)

    # --- SOLUCIÓN PARA LOS CÓDIGOS NUMÉRICOS ---
    # pre=True significa: "Ejecutate ANTES de validar los tipos"
    @validator('codigo', 'articulo', 'marca', pre=True)
    def convertir_a_texto(cls, v):
        if v is None:
            return None
        # Si llega 41021 (int) o 41021.0 (float), lo vuelve string "41021"
        return str(v).replace('.0', '') if isinstance(v, float) and v.is_integer() else str(v)

    # --- SOLUCIÓN PARA STOCKS (LIMPIEZA) ---
    @validator('stock', 'stock_minimo', 'stock_optimo', pre=True)
    def convertir_a_numero(cls, v):
        if v == "" or v is None:
            return 0.0
        if isinstance(v, str):
            try:
                # Arregla comas de Excel español (ej: "1,5" -> 1.5)
                return float(v.replace(',', '.').strip())
            except ValueError:
                return 0.0 # Si dice "Sin Stock", devuelve 0
        return v

    class Config:
        populate_by_name = True

# --- LÓGICA DE GUARDADO ---
def procesar_guardado_postgres(datos: List[FilaExcel]):
    db = SessionLocal()
    try:
        datos_para_db = []
        for fila in datos:
            datos_para_db.append(fila.dict(by_alias=False)) # Usamos los nombres internos (python)
        
        with db.begin():
            db.execute(tabla_stock.delete()) 
            if datos_para_db:
                db.execute(tabla_stock.insert(), datos_para_db) 
        print(f"--- ÉXITO: {len(datos_para_db)} filas guardadas en Postgres ---")
    except Exception as e:
        print(f"!!! ERROR CRÍTICO: {e}")
    finally:
        db.close()

# --- ENDPOINT ---
@router.post("/upload-sheet")
async def endpoint_stock(filas: List[FilaExcel], background_tasks: BackgroundTasks):
    if not filas: raise HTTPException(status_code=400, detail="Vacio")
    background_tasks.add_task(procesar_guardado_postgres, filas)
    return {"message": "Procesando stock en segundo plano"}