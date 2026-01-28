import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field, field_validator, ConfigDict
from sqlalchemy import Table, Column, Integer, String, Float, UniqueConstraint
from sqlalchemy.dialects.postgresql import insert
from database import engine, metadata, SessionLocal

# Configuración de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# --- DEFINICIÓN DE TABLA ---
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
    # Restricción Única Compuesta
    UniqueConstraint('codigo', 'marca', name='uix_codigo_marca'),
)

# Creación segura de tablas
try:
    metadata.create_all(bind=engine)
except Exception as e:
    logger.error(f"Error al sincronizar tablas: {e}")

# --- MODELO PYDANTIC ---
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
    def limpiar_texto_obligatorio(cls, v):
        if v is None or str(v).strip() == "":
            raise ValueError("El campo no puede estar vacío")
        if isinstance(v, float) and v.is_integer():
            return str(int(v))
        return str(v).strip()

    @field_validator('articulo', mode='before')
    @classmethod
    def limpiar_texto_opcional(cls, v):
        if v is None: return None
        return str(v).strip()

    @field_validator('stock', 'stock_minimo', 'stock_optimo', mode='before')
    @classmethod
    def limpiar_numeros(cls, v):
        if v == "" or v is None: return 0.0
        if isinstance(v, str):
            try:
                return float(v.replace(',', '.').strip())
            except ValueError:
                return 0.0
        return v

# --- LÓGICA DE SALTEAR SI EXISTE (ON CONFLICT DO NOTHING) ---
def procesar_guardado_postgres(datos: List[FilaExcel]):
    """
    Inserta datos. Si la combinación codigo+marca ya existe, se saltea la fila.
    """
    db = SessionLocal()
    try:
        listado_dicts = [fila.model_dump(by_alias=False) for fila in datos]
        
        if not listado_dicts:
            return

        # Preparamos la inserción masiva
        stmt = insert(tabla_stock).values(listado_dicts)
        
        # CAMBIO CLAVE: .on_conflict_do_nothing()
        # Si hay conflicto en el índice de codigo y marca, no hace nada.
        statement_final = stmt.on_conflict_do_nothing(
            index_elements=['codigo', 'marca']
        )

        with db.begin():
            result = db.execute(statement_final)
            # rowcount indicará cuántas filas fueron REALMENTE insertadas
            logger.info(f"Proceso completado. Nuevas filas insertadas: {result.rowcount}")

    except Exception as e:
        logger.critical(f"Error procesando guardado: {e}", exc_info=True)
    finally:
        db.close()

# --- ENDPOINT ---
@router.post("/upload-sheet")
async def endpoint_stock(filas: List[FilaExcel], background_tasks: BackgroundTasks):
    if not filas: 
        raise HTTPException(status_code=400, detail="No se recibieron datos")
    
    background_tasks.add_task(procesar_guardado_postgres, filas)
    
    return {
        "status": "processing",
        "count": len(filas),
        "detail": "Insertando nuevos registros. Los duplicados por Código y Marca serán ignorados."
    }