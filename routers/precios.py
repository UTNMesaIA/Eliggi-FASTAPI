import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, validator
from sqlalchemy import Table, Column, Integer, String, Float, UniqueConstraint
from sqlalchemy.dialects.postgresql import insert
from database import engine, metadata, SessionLocal

router = APIRouter()

tabla_precios = Table(
    "lista_precios",
    metadata,
    Column("id", Integer, primary_key=True, index=True),
    Column("codigo", String, nullable=False),
    Column("articulo", String),
    Column("proveedor", String, nullable=False),
    Column("precio_final", Float),
    Column("marca", String),
    Column("rubro", String),
    Column("cod_prov", String),
    # RESTRICCIÓN CLAVE: Único el par proveedor-codigo
    UniqueConstraint('proveedor', 'codigo', name='uix_prov_cod_precios'),
)

metadata.create_all(bind=engine)

class FilaPrecio(BaseModel):
    codigo: str = Field(alias="Código")
    articulo: Optional[str] = Field(alias="Artículo", default=None)
    proveedor: str = Field(alias="Proveedor", default="GENERAL")
    precio: float = Field(alias="C. Final", default=0.0)
    marca: Optional[str] = Field(alias="Marca", default=None)
    cod_prov: Optional[str] = Field(alias="Cod. Art. P.", default=None)
    rubro: Optional[str] = Field(alias="Rubro", default=None)

    @validator('codigo', 'proveedor', pre=True)
    def limpiar_obligatorios(cls, v):
        if v is None: return "S/D"
        return str(v).strip().replace('.0', '') if isinstance(v, (float, int)) else str(v).strip()

    @validator('precio', pre=True)
    def limpiar_precio(cls, v):
        if not v: return 0.0
        if isinstance(v, str):
            return float(v.replace('.', '').replace(',', '.'))
        return float(v)

def guardar_precios_db(datos: List[FilaPrecio]):
    print("\n" + "═"*60)
    print(f"💰 [PRECIOS] Procesando {len(datos)} filas.")
    
    db = SessionLocal()
    batch_size = 1000
    total_afectados = 0
    
    # MANEJO DE DUPLICADOS EN ENTRADA: Clave es (proveedor, codigo)
    limpios = {(f.proveedor, f.codigo): f for f in datos}
    datos_lista = list(limpios.values())
    print(f"🧹 [PRECIOS] De {len(datos)} a {len(datos_lista)} registros únicos por Proveedor-Código.")

    try:
        for i in range(0, len(datos_lista), batch_size):
            batch = datos_lista[i : i + batch_size]
            datos_batch = []
            for f in batch:
                datos_batch.append({
                    "codigo": f.codigo,
                    "articulo": f.articulo,
                    "proveedor": f.proveedor,
                    "precio_final": f.precio,
                    "marca": f.marca,
                    "cod_prov": f.cod_prov,
                    "rubro": f.rubro
                })
            
            stmt = insert(tabla_precios).values(datos_batch)
            statement_upsert = stmt.on_conflict_do_update(
                index_elements=['proveedor', 'codigo'], # El conflicto se busca en este par
                set_={
                    "articulo": stmt.excluded.articulo,
                    "precio_final": stmt.excluded.precio_final,
                    "marca": stmt.excluded.marca,
                    "rubro": stmt.excluded.rubro,
                    "cod_prov": stmt.excluded.cod_prov
                }
            )
            
            with db.begin():
                result = db.execute(statement_upsert)
                total_afectados += result.rowcount
            print(f"⏳ [PRECIOS] {min(i + batch_size, len(datos_lista))} / {len(datos_lista)}...")

        return total_afectados
    finally:
        db.close()

@router.post("/upload-precios")
async def upload_precios(filas: List[FilaPrecio]):
    total = guardar_precios_db(filas)
    return {"status": "success", "cambios_db": total}
