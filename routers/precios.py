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

from sqlalchemy import text # IMPORTANTE: Asegúrate de tener esta importación arriba

def guardar_precios_db(datos: List[FilaPrecio]):
    print("\n" + "═"*60)
    print(f"💰 [PRECIOS] Procesando {len(datos)} filas.")
    
    db = SessionLocal()
    total_afectados = 0
    
    # --- 🛠️ ESTO ES LO QUE DEBES AGREGAR / MODIFICAR ---
    try:
        # 1. Borramos duplicados existentes para permitir la creación del índice
        sql_limpieza = text("""
            DELETE FROM lista_precios 
            WHERE id NOT IN (
                SELECT MAX(id) 
                FROM lista_precios 
                GROUP BY proveedor, codigo
            );
        """)
        db.execute(sql_limpieza)
        
        # 2. Creamos el índice único que PostgreSQL necesita para el ON CONFLICT
        db.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uix_prov_cod_precios ON lista_precios (proveedor, codigo);"))
        db.commit()
        print("✅ Base de datos limpiada e índice verificado.")
    except Exception as e:
        db.rollback()
        print(f"⚠️ Nota en mantenimiento: {e}")
    # --------------------------------------------------

    # MANEJO DE DUPLICADOS EN LA ENTRADA (Memoria)
    limpios = {(f.proveedor, f.codigo): f for f in datos}
    datos_lista = list(limpios.values())
    batch_size = 1000

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
            
            # Upsert (Insertar o Actualizar)
            stmt = insert(tabla_precios).values(datos_batch)
            statement_upsert = stmt.on_conflict_do_update(
                index_elements=['proveedor', 'codigo'],
                set_={
                    "articulo": stmt.excluded.articulo,
                    "precio_final": stmt.excluded.precio_final,
                    "marca": stmt.excluded.marca,
                    "rubro": stmt.excluded.rubro,
                    "cod_prov": stmt.excluded.cod_prov
                }
            )
            
            result = db.execute(statement_upsert)
            db.commit() # Confirmar cada lote
            
            total_afectados += (result.rowcount if result.rowcount > 0 else 0)
            print(f"⏳ [PRECIOS] {min(i + batch_size, len(datos_lista))} / {len(datos_lista)}...")

        return total_afectados
    except Exception as e:
        db.rollback()
        print(f"❌ ERROR EN GUARDADO: {e}")
        raise e
    finally:
        db.close()

@router.post("/upload-precios")
async def upload_precios(filas: List[FilaPrecio]):
    try:
        total = guardar_precios_db(filas)
        return {"status": "success", "cambios_db": total}
    except Exception as e:
        # Esto te dirá el error real en Postman
        raise HTTPException(status_code=500, detail=str(e))

# ... (tus imports y código anterior)

@router.get("/precios")
async def obtener_todos_los_precios(limit: int = 100, skip: int = 0):
    """
    Retorna la lista de precios con paginación.
    Uso: /precios?limit=50&skip=0
    """
    db = SessionLocal()
    try:
        # Construimos la consulta seleccionando todos los campos de la tabla
        query = select(tabla_precios).offset(skip).limit(limit)
        result = db.execute(query).mappings().all()
        
        return {
            "total_enviados": len(result),
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener precios: {str(e)}")
    finally:
        db.close()

@router.get("/precios/{codigo}")
async def obtener_precio_por_codigo(codigo: str, proveedor: Optional[str] = None):
    """
    Busca un código específico. 
    Opcionalmente puedes filtrar por proveedor: /precios/VTH123?proveedor=ZERBINI
    """
    db = SessionLocal()
    try:
        # Limpiamos el código por si viene con espacios desde la URL
        codigo_limpio = codigo.strip()
        
        query = select(tabla_precios).where(tabla_precios.c.codigo == codigo_limpio)
        
        # Si pasan el proveedor por parámetro, filtramos también por él
        if proveedor:
            query = query.where(tabla_precios.c.proveedor == proveedor)
            
        result = db.execute(query).mappings().all()

        if not result:
            raise HTTPException(status_code=404, detail=f"Código '{codigo_limpio}' no encontrado")

        return {
            "busqueda": codigo_limpio,
            "resultados": result
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en la búsqueda: {str(e)}")
    finally:
        db.close()

@router.get("/debug-columnas")
async def debug_columnas():
    from sqlalchemy import inspect
    inspector = inspect(engine)
    columnas = inspector.get_columns("lista_precios")
    indices = inspector.get_indexes("lista_precios")
    return {
        "columnas_reales_en_db": [c['name'] for c in columnas],
        "indices_detectados": indices
    }