from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from routers import stock, archivos, precios # Importamos tus dos archivos nuevos
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


app = FastAPI()
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Esto imprime el error detallado en tu terminal
    print(f"❌ ERROR DE VALIDACIÓN 422: {exc.errors()}")
    # Y esto le devuelve el detalle a Google Sheets (o al navegador)
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": exc.body},
    )
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Agregamos los routers
# 1. Rutas de Stock (Eliggi) -> Queda en /upload-sheet
app.include_router(stock.router)

# 2. Rutas de Archivos (Utilidades) -> Queda en /leer-excel, /extract, etc.
app.include_router(archivos.router)

# 3. Rutas de Precios (Eliggi) -> Queda en /upload-precios
app.include_router(precios.router)
@app.get("/")
def home():
    return {"mensaje": "API Eliggi + Utilidades funcionando 🚀"}