from sqlalchemy.dialects.postgresql import insert

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