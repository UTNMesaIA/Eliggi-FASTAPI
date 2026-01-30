# routers/stock.py
import logging
from typing import List, Optional # <--- IMPORTANTE: List debe estar aquí
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator, ConfigDict
from sqlalchemy import Table, Column, Integer, String, Float, UniqueConstraint
from sqlalchemy.dialects.postgresql import insert
from database import engine, metadata, SessionLocal

router = APIRouter()

# --- TABLA ---
tabla_stock = Table(
    "stock_items",
    metadata,
    Column("id", Integer, primary_key=True, index=True),
    Column("codigo", String, index=True, nullable=False), 
    Column("articulo", String),
    Column("stock", Float, default=0.0),
    Column("stock_minimo", Float, default=0.0),
    Column("stock_optimo", Float, default=0.0),
    Column("marca", String, index=True, nullable=False),
    UniqueConstraint('codigo', 'marca', name='uix_codigo_marca'),
)

metadata.create_all(bind=engine)

# --- MODELO ---
class FilaExcel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    codigo: str = Field(alias="Código")
    articulo: Optional[str] = Field(alias="Artículo", default=None)
    stock: float = Field(alias="Stock", default=0.0)
    stock_minimo: float = Field(alias="Stock Mínimo", default=0.0)
    stock_optimo: float = Field(alias="Stock Optimo", default=0.0)
    marca: str = Field(alias="Marca", default="Sin Marca")

    @field_validator('codigo', 'marca', mode='before')
    @classmethod
    def limpiar_texto(cls, v):
        if v is None or str(v).strip() == "": return "S/D"
        return str(v).strip()

def procesar_guardado_postgres(datos: List[FilaExcel]):
    print("\n" + "═"*60)
    print(f"📦 PROCESANDO STOCK: {len(datos)} artículos recibidos.")
    print("═"*60)
    
    db = SessionLocal()
    try:
        # 1. Preparación de datos
        print("🔍 Validando y transformando datos...")
        listado_dicts = [fila.model_dump(by_alias=False) for fila in datos]
        
        if not listado_dicts:
            print("⚠️ Archivo vacío o datos inválidos.")
            return 0

        # 2. Definición del Upsert (Update on Conflict)
        stmt = insert(tabla_stock).values(listado_dicts)
        
        # Seleccionamos qué columnas queremos que se actualicen si hay conflicto
        statement_final = stmt.on_conflict_do_update(
            index_elements=['codigo', 'marca'], # La clave de comparación
            set_={
                "articulo": stmt.excluded.articulo,
                "stock": stmt.excluded.stock,
                "stock_minimo": stmt.excluded.stock_minimo,
                "stock_optimo": stmt.excluded.stock_optimo,
            }
        )

        # 3. Ejecución
        print("💾 Sincronizando con PostgreSQL (Insertando nuevos o Actualizando existentes)...")
        with db.begin():
            result = db.execute(statement_final)
            filas_afectadas = result.rowcount
        
        print(f"✅ PROCESO FINALIZADO: {filas_afectadas} filas operadas en total.")
        print("═"*60 + "\n")
        
        return filas_afectadas

    except Exception as e:
        print(f"❌ ERROR EN BASE DE DATOS: {e}")
        raise e
    finally:
        print("🔌 Conexión cerrada.")
        db.close()

# --- ENDPOINT (ESPERA A QUE TERMINE) ---

@router.post("/upload-sheet")
async def endpoint_stock(filas: List[FilaExcel]):
    print(f"\n[HTTP POST] Recibida carga de stock")
    
    if not filas: 
        raise HTTPException(status_code=400, detail="No se recibieron datos")
    
    # La ejecución es directa (síncrona), el cliente espera aquí
    total_operaciones = procesar_guardado_postgres(filas)
    
    return {
        "status": "success",
        "message": "Sincronización completa",
        "detalle": {
            "total_enviados": len(filas),
            "filas_afectadas_db": total_operaciones,
            "metodo": "UPSERT (Update on Conflict)"
        }
    }
