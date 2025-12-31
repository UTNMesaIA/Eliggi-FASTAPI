# 🚀 API de Automatización y Sincronización - Eliggi

Este proyecto es una **API Backend de alto rendimiento** construida con **FastAPI** (Python). Su función principal es actuar como puente inteligente entre datos estáticos (Google Sheets, archivos Excel, ZIPs) y una base de datos relacional robusta (**PostgreSQL** en Railway).

El sistema permite la sincronización masiva de stock y precios, limpieza de datos en tiempo real y utilidades avanzadas para la extracción de información de archivos de proveedores.

---

## 📋 Tabla de Contenidos

1. [Arquitectura del Proyecto](#-arquitectura-del-proyecto)
2. [Características Principales](#-características-principales)
3. [Requisitos Previos](#-requisitos-previos)
4. [Instalación y Configuración Local](#-instalación-y-configuración-local)
5. [Variables de Entorno](#-variables-de-entorno)
6. [Ejecución del Servidor](#-ejecución-del-servidor)
7. [Documentación de Endpoints](#-documentación-de-endpoints)
8. [Solución de Problemas Comunes](#-solución-de-problemas-comunes)

---

## 🏗 Arquitectura del Proyecto

El proyecto ha sido refactorizado para seguir una arquitectura modular usando `APIRouter`. Esto permite escalar fácilmente sin crear "código espagueti".

/Eliggi-FASTAPI
│
├── .env                    # (NO SUBIR) Variables de entorno y credenciales
├── .gitignore              # Archivos ignorados por Git
├── requirements.txt        # Dependencias del proyecto
├── main.py                 # Punto de entrada (Entry Point). Conecta los routers.
├── database.py             # Configuración Singleton de la conexión a PostgreSQL via SQLAlchemy.
│
├── routers/                # 📂 Módulos de lógica separada
│   ├── stock.py            # Lógica de sincronización de Stock (Sheets -> DB)
│   ├── precios.py          # Lógica de listas de precios (Proveedor -> DB)
│   └── archivos.py         # Utilidades (Lectura de Excel con colores, extracción de ZIP/SQLite)
│
└── ngrok.exe               # (Solo local) Túnel para exponer la API a Internet


---

## ⭐ Características Principales

### 1. Sincronización Inteligente de Stock (`/upload-sheet`)

* Recibe JSON desde Google Sheets.
* **Validación Pydantic:** Convierte automáticamente datos "sucios" (ej: stocks vacíos, códigos numéricos interpretados como texto).
* **Tipado Fuerte:** Garantiza que en PostgreSQL los números sean `FLOAT` (Double Precision) y los textos `VARCHAR`.
* **Bulk Insert:** Borra la tabla anterior y regenera los datos en milisegundos.

### 2. Gestión de Listas de Precios (`/upload-precios`)

* Procesa columnas críticas como "C. Final".
* **Limpieza de Moneda:** Maneja formatos europeos/latinos (puntos de mil y comas decimales) transformándolos a `FLOAT` estandarizados para la base de datos.

### 3. Procesamiento de Archivos Proveedores (`/leer-excel` y `/extract`)

* **Detección de Colores:** Analiza el color de fondo de las celdas de Excel (Rojo, Amarillo, Verde) para determinar disponibilidad de stock visualmente.
* **Minería de ZIPs:** Descomprime archivos ZIP al vuelo, busca bases de datos SQLite incrustadas y extrae información de artículos específicos mediante SQL dinámico.

---

## 🛠 Requisitos Previos

Antes de comenzar, asegúrate de tener instalado:

1. **Python 3.10 o superior**: [Descargar aquí](https://www.python.org/downloads/).
2. **Git**: Para control de versiones.
3. **VS Code**: Editor recomendado.
4. **Ngrok**: Necesario para conectar Google Sheets con tu PC local.

---

## 💻 Instalación y Configuración Local

Sigue estos pasos rigurosamente para levantar el entorno de desarrollo.

### 1. Clonar o Descargar

Descarga el código fuente y ábrelo con VS Code.

### 2. Crear Entorno Virtual (Recomendado)

Para no mezclar librerías con tu sistema principal:

# En terminal (Windows):
python -m venv venv
.\venv\Scripts\activate

### 3. Instalar Dependencias

Instala todas las librerías necesarias (FastAPI, SQLAlchemy, Pandas, OpenPyXL, etc.):

pip install -r requirements.txt

*(Si no tienes el archivo `requirements.txt`, genéralo con `pip freeze > requirements.txt` después de instalar todo).*

---

## 🔐 Variables de Entorno

Crea un archivo llamado `.env` en la raíz del proyecto (junto a `main.py`).
**IMPORTANTE:** Este archivo contiene contraseñas, **nunca** lo subas a GitHub.

Contenido del `.env`:

# Credenciales de Railway (PostgreSQL)
# Copiar tal cual aparecen en Railway -> Variables
PGPASSWORD=TuPasswordLargoYSecretoDeRailway

*Nota: El Host, Usuario y Puerto están configurados por defecto en `database.py` para Railway, pero pueden parametrizarse aquí si se desea.*

---

## ▶ Ejecución del Servidor

Para que el sistema funcione completo (API + Conexión con Google Sheets), necesitas **dos terminales** abiertas.

### Terminal 1: El Servidor Python

Inicia la API con recarga automática (hot-reload):

powershell:
python -m uvicorn main:app --reload


* Si ves `Application startup complete`, la API está viva en `http://127.0.0.1:8000`.

### Terminal 2: El Túnel Ngrok

Para que Google Sheets pueda "ver" tu servidor local:

powershell:
.\ngrok http 8000

* Copia la dirección HTTPS que genera (ej: `https://a1b2-c3d4.ngrok-free.app`).
* **Pega esa dirección** en tu script de Google Apps Script.

---

## 📚 Documentación de Endpoints

FastAPI genera documentación automática e interactiva.

1. Abre tu navegador.
2. Ve a: **[http://127.0.0.1:8000/docs](https://www.google.com/search?q=http://127.0.0.1:8000/docs)** (Swagger UI).
3. Verás todos los endpoints disponibles organizados por módulos.

### Endpoints Clave


| `POST` | `/upload-sheet` | Stock | Recibe JSON de la hoja "Articulos", limpia tipos y guarda en DB `stock_items`. |
| `POST` | `/upload-precios` | Precios | Recibe JSON de la hoja "Precios", formatea decimales y guarda en DB `lista_precios`. |
| `POST` | `/leer-excel` | Archivos | Sube un `.xlsx`, detecta colores de celdas (Verde/Rojo) y devuelve JSON con estados. |
| `POST` | `/procesar-zip-sqlite` | Archivos | Sube un `.zip`, extrae un SQLite interno y busca códigos específicos. |


## 🔧 Solución de Problemas Comunes

### 🔴 Error: `ModuleNotFoundError: No module named 'routers'`

* **Causa:** Python no encuentra la carpeta nueva.
* **Solución:** Asegúrate de estar ejecutando el comando `python` desde la carpeta raíz (`Eliggi-FASTAPI`), no desde una subcarpeta.

### 🔴 Error: `Authentication failed for user "postgres"`

* **Causa:** La contraseña en `.env` es incorrecta o `load_dotenv` no encuentra el archivo.
* **Solución:**
1. Revisa que el archivo se llame exactamente `.env` (no `.env.txt`).
2. Verifica que `PGPASSWORD` no tenga espacios al inicio o final.
3. Asegúrate de que Railway no haya rotado las credenciales.



### 🔴 Error 422: `Unprocessable Entity`

* **Causa:** Enviaste un dato que no coincide con el modelo Pydantic (ej: Texto en un campo numérico).
* **Solución:** Revisa la consola de Python. Hemos configurado un "Exception Handler" que te dirá exactamente qué fila y columna falló.

---

**Desarrollado para la Mesa de IA - UTN / Eliggi Repuestos**

```

```