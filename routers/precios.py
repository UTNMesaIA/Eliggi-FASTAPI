# routers/precios.py
from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Optional
from pydantic import BaseModel, Field, validator
from sqlalchemy import Table, Column, Integer, String, Float
from database import engine, metadata, SessionLocal

router = APIRouter()

# --- DEFINICIÓN DE LA NUEVA TABLA EN POSTGRES ---
tabla_precios = Table(
    "lista_precios",
    metadata,
    Column("id", Integer, primary_key=True, index=True),
    Column("codigo", String),
    Column("articulo", String),
    Column("proveedor", String),
    Column("precio_final", Float), # Aquí guardaremos el "C. Final" como número
    Column("marca", String),
    Column("rubro", String),
    Column("cod_prov", String),
)

# Crear la tabla si no existe
metadata.create_all(bind=engine)

# --- MODELO DE DATOS (PYDANTIC) ---
class FilaPrecio(BaseModel):
    # Alias exactos como vienen del Excel
    codigo: Optional[str] = Field(alias="Código", default=None)
    articulo: Optional[str] = Field(alias="Artículo", default=None)
    proveedor: Optional[str] = Field(alias="Proveedor", default=None)
    
    # "C. Final" suele venir con coma (ej: "1.200,50")
    precio: Optional[float] = Field(alias="C. Final", default=0.0)
    
    marca: Optional[str] = Field(alias="Marca", default=None)

    cod_prov: Optional[str] = Field(alias="Cod. Art. P.", default=None)

    rubro: Optional[str] = Field(alias="Rubro", default=None)
    
    # VALIDADOR 1: Forzar Código a Texto (por si es numérico en Excel)
    @validator('codigo', 'articulo', 'proveedor', 'marca', pre=True)
    def forzar_texto(cls, v):
        if v is None: return None
        # Si es un número (ej: 41021.0), lo hacemos string "41021"
        return str(v).replace('.0', '') if isinstance(v, float) and v.is_integer() else str(v)

    # VALIDADOR 2: Limpiar el Precio (Manejo de coma decimal)
    @validator('precio', pre=True)
    def limpiar_precio(cls, v):
        if v == "" or v is None:
            return 0.0
        if isinstance(v, str):
            try:
                # Quitamos el punto de miles si existe y cambiamos coma por punto
                # Ej: "1.500,50" -> "1500.50"
                # OJO: Si tu excel usa punto para miles y coma para decimales:
                limpio = v.replace('.', '').replace(',', '.')
                return float(limpio)
            except ValueError:
                # Intento simple si no tenía puntos de miles
                try:
                    return float(v.replace(',', '.'))
                except:
                    return 0.0
        return v

    class Config:
        populate_by_name = True

# --- LÓGICA DE GUARDADO ---
def guardar_precios_db(datos: List[FilaPrecio]):
    db = SessionLocal()
    try:
        datos_para_db = []
        for fila in datos:
            datos_para_db.append({
                "codigo": fila.codigo,
                "articulo": fila.articulo,
                "proveedor": fila.proveedor,
                "precio_final": fila.precio, # Mapeamos al nombre de columna DB
                "marca": fila.marca,
                "cod_prov": fila.cod_prov,
                "rubro": fila.rubro
            })
        
        with db.begin():
            # Borrón y cuenta nueva (Reemplazo total)
            db.execute(tabla_precios.delete()) 
            if datos_para_db:
                db.execute(tabla_precios.insert(), datos_para_db) 
                
        print(f"--- ÉXITO PRECIOS: Se guardaron {len(datos_para_db)} filas ---")
    except Exception as e:
        print(f"!!! ERROR EN PRECIOS: {e}")
    finally:
        db.close()

# --- ENDPOINT ---
@router.post("/upload-precios")
async def upload_precios(filas: List[FilaPrecio], background_tasks: BackgroundTasks):
    if not filas:
        raise HTTPException(status_code=400, detail="Lista vacía")
    
    background_tasks.add_task(guardar_precios_db, filas)
    return {"message": "Recibido. Procesando precios en segundo plano."}
