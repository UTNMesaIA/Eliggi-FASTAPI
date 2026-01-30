from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel, Field, validator
from sqlalchemy import Table, Column, Integer, String, Float
from database import engine, metadata, SessionLocal

router = APIRouter()

# --- DEFINICIÓN DE TABLA ---
tabla_precios = Table(
    "lista_precios",
    metadata,
    Column("id", Integer, primary_key=True, index=True),
    Column("codigo", String),
    Column("articulo", String),
    Column("proveedor", String),
    Column("precio_final", Float),
    Column("marca", String),
    Column("rubro", String),
    Column("cod_prov", String),
)

metadata.create_all(bind=engine)

# (Tu modelo FilaPrecio se mantiene igual...)
class FilaPrecio(BaseModel):
    codigo: Optional[str] = Field(alias="Código", default=None)
    articulo: Optional[str] = Field(alias="Artículo", default=None)
    proveedor: Optional[str] = Field(alias="Proveedor", default=None)
    precio: Optional[float] = Field(alias="C. Final", default=0.0)
    marca: Optional[str] = Field(alias="Marca", default=None)
    cod_prov: Optional[str] = Field(alias="Cod. Art. P.", default=None)
    rubro: Optional[str] = Field(alias="Rubro", default=None)

    @validator('codigo', 'articulo', 'proveedor', 'marca', pre=True)
    def forzar_texto(cls, v):
        if v is None: return None
        return str(v).replace('.0', '') if isinstance(v, float) and v.is_integer() else str(v)

    @validator('precio', pre=True)
    def limpiar_precio(cls, v):
        if v == "" or v is None: return 0.0
        if isinstance(v, str):
            try:
                limpio = v.replace('.', '').replace(',', '.')
                return float(limpio)
            except: return 0.0
        return v

# --- LÓGICA SÍNCRONA CON CONSOLE LOGS ---
def guardar_precios_db(datos: List[FilaPrecio]):
    print("\n" + "═"*60)
    print(f"💰 [PRECIOS] Iniciando carga masiva: {len(datos)} artículos.")
    
    db = SessionLocal()
    try:
        datos_para_db = []
        for fila in datos:
            datos_para_db.append({
                "codigo": fila.codigo,
                "articulo": fila.articulo,
                "proveedor": fila.proveedor,
                "precio_final": fila.precio,
                "marca": fila.marca,
                "cod_prov": fila.cod_prov,
                "rubro": fila.rubro
            })
        
        print("🗑️ [PRECIOS] Vaciando tabla para reemplazo total...")
        with db.begin():
            db.execute(tabla_precios.delete()) 
            if datos_para_db:
                print(f"📥 [PRECIOS] Insertando nuevos datos...")
                db.execute(tabla_precios.insert(), datos_para_db) 
        
        print(f"✅ [PRECIOS] Éxito: {len(datos_para_db)} filas actualizadas.")
        print("═"*60 + "\n")
        return len(datos_para_db)
    except Exception as e:
        print(f"❌ [PRECIOS] ERROR: {e}")
        raise e
    finally:
        db.close()

# --- ENDPOINT (Síncrono) ---
@router.post("/upload-precios")
async def upload_precios(filas: List[FilaPrecio]):
    print(f"📩 [HTTP] Recibida carga de precios ({len(filas)} filas)")
    
    if not filas:
        raise HTTPException(status_code=400, detail="Lista vacía")
    
    # Aquí el servidor se queda esperando hasta que termine el guardado
    total = guardar_precios_db(filas)
    
    return {
        "status": "success", 
        "mensaje": "Lista de precios reemplazada",
        "total": total
    }
