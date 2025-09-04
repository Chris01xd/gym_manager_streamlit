# Gym Manager (Streamlit + PostgreSQL)

Aplicación web (y móvil por UI responsive + PWA) para gestión de gimnasios:
- **Frontend**: Streamlit (Python)
- **Base de datos**: PostgreSQL con **procedimientos almacenados**
- **Análisis/ML**: Notebook para Google Colab
- **Móvil**: usa "Añadir a pantalla de inicio" (PWA) o encapsula en WebView

## Inicio rápido

1) **Arranca PostgreSQL** (opción A o B):
- **A. Docker Compose** (recomendado):
  ```bash
  cd docker
  docker compose up -d
  ```
  Base se crea con: DB=`gymdb`, user=`gym`, pass=`gympass`, puerto `5432`.
  Ingresa a Adminer en http://localhost:8080 (System: PostgreSQL).

- **B. PostgreSQL local**: crea una BD vacía `gymdb` y un usuario `gym` con contraseña `gympass` o ajusta `.env`.

2) **Crear esquema, SPs y datos semilla**:
   ```bash
   psql -h localhost -p 5432 -U gym -d gymdb -f db/schema.sql
   psql -h localhost -p 5432 -U gym -d gymdb -f db/procedures.sql
   psql -h localhost -p 5432 -U gym -d gymdb -f db/seed.sql
   ```

3) **Configura variables**: copia `.env.example` a `.env` y ajusta si hace falta.
   ```bash
   cp .env.example .env
   ```

4) **Instala dependencias** y **lanza Streamlit**:
   ```bash
   pip install -r requirements.txt
   streamlit run app/Home.py
   ```

5) **Login** (semilla): email `admin@gym.local` / clave `admin123`.

6) **Modo "App" en móvil**:
   - Abre la URL de Streamlit desde el navegador del teléfono.
   - Menú → “Añadir a pantalla de inicio” (usa archivos `manifest.json` y `service_worker.js`).

## Estructura
```
app/
  Home.py
  pages/
  lib/
  .streamlit/
db/
  schema.sql
  procedures.sql
  seed.sql
notebooks/
  churn_eda_colab.ipynb
docker/
  docker-compose.yml
```

## Notas
- Este proyecto es un MVP funcional enfocado en: Socios, Membresías, Clases/Reservas, Accesos/Aforo y KPIs básicos.
- Amplía módulos y SPs según tus reglas de negocio.
