# --- LÓGICA DE GUARDADO CON LOGS DETALLADOS ---

def guardar_precios_db(datos: List[FilaPrecio]):
    print("\n" + "="*50)
    print(f"🚀 INICIANDO PROCESAMIENTO: {len(datos)} filas recibidas.")
    print("="*50)
    
    db = SessionLocal()
    try:
        # 1. Preparación de datos
        print("🛠️  Mapeando datos a formato de base de datos...")
        datos_para_db = []
        for i, fila in enumerate(datos):
            datos_para_db.append({
                "codigo": fila.codigo,
                "articulo": fila.articulo,
                "proveedor": fila.proveedor,
                "precio_final": fila.precio,
                "marca": fila.marca,
                "cod_prov": fila.cod_prov,
                "rubro": fila.rubro
            })
            # Log opcional cada 500 filas para no saturar la consola
            if (i + 1) % 500 == 0:
                print(f"   > Procesadas {i + 1} filas...")

        # 2. Operación en Base de Datos
        print("📂 Conectando a la base de datos para transaccionar...")
        with db.begin():
            print("🗑️  Borrando registros antiguos de 'lista_precios'...")
            resultado_delete = db.execute(tabla_precios.delete())
            
            print(f"📥 Insertando {len(datos_para_db)} nuevos registros...")
            if datos_para_db:
                db.execute(tabla_precios.insert(), datos_para_db)
        
        print("✅ TRANSACCIÓN EXITOSA: Datos guardados y confirmados (commit).")
        print("="*50 + "\n")
        return len(datos_para_db)

    except Exception as e:
        print(f"❌ ERROR CRÍTICO EN EL PROCESO: {str(e)}")
        # Aquí la transacción hace rollback automáticamente gracias al 'with db.begin()'
        raise e
    finally:
        print("🔌 Cerrando conexión a la base de datos.")
        db.close()

# --- ENDPOINT ---

@router.post("/upload-precios")
async def upload_precios(filas: List[FilaPrecio]):
    print(f"\n[HTTP POST] Solicitud recibida en /upload-precios")
    
    if not filas:
        print("⚠️  Advertencia: Se recibió una lista vacía.")
        raise HTTPException(status_code=400, detail="La lista enviada está vacía")
    
    try:
        # El proceso es síncrono, el código se detiene aquí hasta que guardar_precios_db termine
        total = guardar_precios_db(filas)
        
        print(f"✨ Respuesta enviada al cliente: {total} filas procesadas.")
        return {
            "status": "success",
            "message": f"Base de datos actualizada con éxito.",
            "detalle": {
                "registros_insertados": total,
                "tabla": "lista_precios"
            }
        }
    except Exception as e:
        # El error ya se printeó en la función anterior, aquí solo respondemos al cliente
        raise HTTPException(
            status_code=500, 
            detail=f"Error interno del servidor: {str(e)}"
        )