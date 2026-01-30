import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator, ConfigDict
from sqlalchemy import Table, Column, Integer, String, Float, UniqueConstraint
from sqlalchemy.dialects.postgresql import insert
from database import engine, metadata, SessionLocal

router = APIRouter()

tabla_stock = Table(
    "stock_items",
    metadata,
    Column("id", Integer, primary_key=True, index=True),
    Column("codigo", String, index=True, unique=True, nullable=False), # Único por sí solo
    Column("articulo", String),
    Column("stock", Float, default=0.0),
    Column("stock_minimo", Float, default=0.0),
    Column("stock_optimo", Float, default=0.0),
    Column("marca", String),
)

metadata.create_all(bind=engine)

class FilaExcel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    codigo: str = Field(alias="Código")
    articulo: Optional[str] = Field(alias="Artículo", default=None)
    stock: float = Field(alias="Stock", default=0.0)
    stock_minimo: float = Field(alias="Stock Mínimo", default=0.0)
    stock_optimo: float = Field(alias="Stock Optimo", default=0.0)
    marca: str = Field(alias="Marca", default="Sin Marca")

    @field_validator('codigo', mode='before')
    @classmethod
    def limpiar_codigo(cls, v):
        if v is None or str(v).strip() == "": raise ValueError("Código vacío")
        return str(v).strip()

def procesar_guardado_postgres(datos: List[FilaExcel]):
    print("\n" + "═"*60)
    print(f"📦 [STOCK] Procesando {len(datos)} filas...")
    
    db = SessionLocal()
    batch_size = 1000
    total_afectados = 0
    
    # ELIMINAR DUPLICADOS EN LA ENTRADA: Usamos el código como llave
    # Si viene el mismo código dos veces en el Excel, queda el último.
    limpios = {f.codigo: f for f in datos}
    datos_lista = list(limpios.values())
    print(f"🧹 [STOCK] Duplicados eliminados. De {len(datos)} a {len(datos_lista)} únicos.")

    try:
        for i in range(0, len(datos_lista), batch_size):
            batch = datos_lista[i : i + batch_size]
            listado_dicts = [fila.model_dump(by_alias=False) for fila in batch]
            
            stmt = insert(tabla_stock).values(listado_dicts)
            statement_upsert = stmt.on_conflict_do_update(
                index_elements=['codigo'], # Conflicto solo en código
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
            print(f"⏳ [STOCK] {min(i + batch_size, len(datos_lista))} / {len(datos_lista)}...")

        return total_afectados
    finally:
        db.close()

@router.post("/upload-sheet")
async def endpoint_stock(filas: List[FilaExcel]):
    total = procesar_guardado_postgres(filas)
    return {"status": "success", "cambios": total}
