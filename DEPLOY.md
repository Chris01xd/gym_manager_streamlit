# Despliegue de *gym_manager_streamlit*

Este proyecto es una app de Streamlit con estructura:

```
gym_manager_streamlit/
├─ app/
│  ├─ Home.py                # Entry point (selección de páginas/landing)
│  ├─ pages/                 # Páginas 1..10_*.py
│  ├─ lib/                   # utilidades (db, auth, ui, sp_wrappers)
│  └─ .streamlit/            # config opcional
└─ requirements.txt
```

## 1) Arreglar imports para producción

Actualmente los módulos usan `from lib import ...` o `import db`.
Cuando la app se ejecuta con `app/Home.py` como entrada, **Python no encuentra** `lib/` ni `db` al estar dentro de `app/`.

**Soluciones (elige una):**

### Opción A (recomendada): usar imports con el paquete `app`
1. Añade un archivo vacío `app/__init__.py` (para que `app` sea un paquete).
2. Cambia imports en todo el código así:
   - `from lib.db import ...` → `from app.lib.db import ...`
   - `from lib.auth import ...` → `from app.lib.auth import ...`
   - `import db` → `from app.lib import db`
   - `import lib` → `from app import lib`

### Opción B: mover `lib/` al raíz del repo
- Mueve `app/lib/` a `lib/` (al mismo nivel que `app/`) y deja los imports como `from lib.db import ...`.
- Mantén `entrypoint` como `app/Home.py`.

> Cualquiera de las dos evita `ModuleNotFoundError: No module named 'lib'` o `No module named 'db'`.

## 2) Variables de entorno (PostgreSQL y otros)
La conexión (en `app/lib/db.py`) usa variables `.env` tipo:
```
PGHOST=...
PGPORT=...
PGDATABASE=...
PGUSER=...
PGPASSWORD=...
```
En local puedes crear un archivo `.env` en el raíz del repo.
En Streamlit Cloud NO uses `.env`: guarda estas claves en **Secrets**.

### Secrets (Streamlit Cloud)
Crea en *Settings → Secrets* un TOML equivalente:
```toml
PGHOST="tu_host"
PGPORT="5432"
PGDATABASE="tu_db"
PGUSER="tu_usuario"
PGPASSWORD="tu_password"
```
Y **lee** con `os.getenv(...)` como ya hace tu `db.py` (no necesitas cambios).

## 3) Requisitos y versión de Python
Usa el `requirements.txt` incluido (fijado a tus versiones):  
```
streamlit==1.36.0
psycopg[binary]==3.2.9
pandas==2.2.2
python-dotenv==1.0.1
plotly==5.22.0
```
Opcionalmente puedes añadir un archivo `runtime.txt` con la versión de Python, por ejemplo:
```
3.12
```

## 4) Ejecutar en local
```bash
pip install -r requirements.txt
streamlit run app/Home.py
```
Si usas `.env`, colócalo en el raíz del repo y verifica que cargue (`python-dotenv`).

## 5) Desplegar en Streamlit Community Cloud
1. Sube este folder a un repositorio en GitHub (p. ej. `keni/gym_manager_streamlit`).
2. En **Streamlit Cloud → New app** selecciona el repo y rama.
3. **Entrypoint:** `app/Home.py`  
4. **Advanced settings → Secrets:** pega el bloque TOML con tus credenciales.
5. (Opcional) **Python version:** 3.12 (o la que prefieras).
6. Pulsa **Deploy**.

## 6) Problemas comunes
- **`ModuleNotFoundError: No module named 'lib'`**  
  Falta `app/__init__.py` y/o los imports no usan `app.lib`. Aplica la Opción A o B de la sección 1.
- **`No module named 'dotenv'` / `psycopg`**  
  No se instaló `requirements.txt`. Reinstala.
- **Error de conexión a DB**  
  Revisa Secrets o `.env` y que el host/puerto sean accesibles desde la nube.
- **Páginas no aparecen**  
  Asegúrate que la carpeta `pages/` está al lado de `Home.py` y que los archivos se nombran `N_Titulo.py`.

---

> Tip: si prefieres, puedes mover `Home.py` al raíz del repo y dejar `pages/` y `lib/` también en el raíz. En ese caso el entrypoint sería `Home.py`.
