import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator, ConfigDict
from sqlalchemy import Table, Column, Integer, String, Float, UniqueConstraint
from sqlalchemy.dialects.postgresql import insert
from database import engine, metadata, SessionLocal

router = APIRouter()

# --- DEFINICIÓN DE TABLA CORREGIDA ---
tabla_stock = Table(
    "stock_items",
    metadata,
    Column("id", Integer, primary_key=True, index=True),
    # AGREGAMOS unique=True AQUÍ PARA QUE EL UPSERT FUNCIONE
    Column("codigo", String, index=True, unique=True, nullable=False), 
    Column("articulo", String),
    Column("stock", Float, default=0.0),
    Column("stock_minimo", Float, default=0.0),
    Column("stock_optimo", Float, default=0.0),
    Column("marca", String),
)

# Esto intenta crear la tabla con la restricción UNIQUE si no existe
metadata.create_all(bind=engine)

class FilaExcel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    codigo: str = Field(alias="Código")
    articulo: Optional[str] = Field(alias="Artículo", default=None)
    stock: float = Field(alias="Stock", default=0.0)
    stock_minimo: float = Field(alias="Stock Mínimo", default=0.0)
    stock_optimo: float = Field(alias="Stock Optimo", default=0.0)
    # Cambiamos a Any temporalmente en el input para validarlo nosotros
    marca: Optional[str] = Field(alias="Marca", default="Sin Marca")

    @field_validator('codigo', 'marca', mode='before')
    @classmethod
    def forzar_string(cls, v):
        """Convierte números (como 555) en texto ('555') para evitar el error 422"""
        if v is None: return "Sin Marca"
        # Si es un número, lo pasamos a string limpio
        if isinstance(v, (int, float)):
            return str(int(v)) if isinstance(v, float) and v.is_integer() else str(v)
        return str(v).strip()

# --- LÓGICA DE BATCHES ---
def procesar_guardado_postgres(datos: List[FilaExcel]):
    print("\n" + "═"*60)
    # Limpiar duplicados que vengan en el mismo Excel antes de mandar a DB
    diccionario_limpio = {f.codigo: f for f in datos}
    datos_unicos = list(diccionario_limpio.values())
    
    print(f"📦 [STOCK] {len(datos)} recibidos -> {len(datos_unicos)} tras limpiar duplicados.")
    
    db = SessionLocal()
    batch_size = 1000
    total_afectados = 0
    
    try:
        for i in range(0, len(datos_unicos), batch_size):
            batch = datos_unicos[i : i + batch_size]
            listado_dicts = [fila.model_dump(by_alias=False) for fila in batch]
            
            stmt = insert(tabla_stock).values(listado_dicts)
            statement_upsert = stmt.on_conflict_do_update(
                index_elements=['codigo'], # Ahora sí funcionará porque la columna es UNIQUE
                set_={
                    "articulo": stmt.excluded.articulo,
                    "stock": stmt.excluded.stock,
                    "stock_minimo": stmt.excluded.stock_minimo,
                    "stock_optimo": stmt.excluded.stock_optimo,
                    "marca": stmt.excluded.marca
                }
            )
            
            with db.begin():
                result = db.execute(statement_upsert)
                total_afectados += result.rowcount
            print(f"⏳ [STOCK] Progreso: {min(i + batch_size, len(datos_unicos))}...")

        return total_afectados
    finally:
        db.close()

@router.post("/upload-sheet")
async def endpoint_stock(filas: List[FilaExcel]):
    try:
        total = procesar_guardado_postgres(filas)
        return {"status": "success", "cambios": total}
    except Exception as e:
        print(f"❌ ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))
