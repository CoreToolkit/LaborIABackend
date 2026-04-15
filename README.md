# LaborIABackend

Backend FastAPI de LaborIA con SQLAlchemy, Alembic, pruebas unitarias y gate de seguridad con Sentinel en CI.

## Requisitos

- Python 3.11
- pip
- Docker (requerido para escaneo de imagen local en Sentinel)
- Git

## Ejecucion del proyecto (local)

1. Crear virtual environment:

```powershell
python -m venv venv
```

2. Activar venv:

```powershell
.\venv\Scripts\Activate.ps1
```

3. Instalar dependencias:

```powershell
python run.py install
```

## Comandos disponibles (`run.py`)

- Instalar dependencias:

```powershell
python run.py install
```

- Ejecutar pruebas unitarias:

```powershell
python run.py test
```

- Generar reporte de cobertura (HTML en `htmlcov/index.html`):

```powershell
python run.py coverage
```

- Ejecutar API:

```powershell
python run.py run
```

- Ejecutar flujo completo (install + test + coverage + run):

```powershell
python run.py all
```

- Limpiar archivos cache y temporales:

```powershell
python run.py clean
```

## API y documentacion

- API local: `http://localhost:8000/`
- Docs automaticas: `http://localhost:8000/docs`

## Migraciones

Antes de poblar catalogos, asegurate de tener migraciones aplicadas:

```powershell
alembic upgrade head
```

## Carga inicial de roles, tecnologias y role_skills

Se incluye un script para poblar tablas `job_roles`, `technologies` y `role_skills` desde catalogo JSON.

- Simulacion (recomendado):

```powershell
python scripts/seed_roles_from_catalog.py --dry-run
```

- Carga real:

```powershell
python scripts/seed_roles_from_catalog.py
```

- Archivo personalizado:

```powershell
python scripts/seed_roles_from_catalog.py --file .\ruta\mi_catalogo.json
```

Notas importantes:

- Si existe `roles_dialog.json`, el script lo usa primero; si no, usa `roles_catalog.json`.
- El proceso es idempotente por nombre de rol: crea roles nuevos y actualiza existentes.
- Para cada rol, reemplaza sus `role_skills` en cada ejecucion para mantener consistencia con el JSON.
- Tecnologias existentes no se duplican; se reutilizan por nombre.

## CI/CD (pipeline unico)

El repositorio usa un solo workflow: `.github/workflows/ci.yml`.

### Job `test`

- Corre en todo `push` y `pull_request`.
- Ejecuta pruebas con cobertura minima del 80%.
- Usa variables CI para pruebas:
  - `DATABASE_URL=sqlite:///./test.db`
  - `JWT_SECRET=ci-secret`

### Job `sentinel`

- Corre despues de `test`.
- Corre solo para:
  - `push` a `main` o `develop`
  - `pull_request` cuya rama base sea `main` o `develop`
- Flujo:
  1. Checkout del backend.
  2. Checkout de Sentinel desde `JuanDiegoRV/Sentinel-AI-CD` (`feature/Laboria_compatibility`).
  3. Build de imagen Docker del backend (`laboria-backend:${GITHUB_SHA}`).
  4. Escaneo Trivy (`reports/trivy-image.json`).
  5. Levanta Sentinel local en el runner (`127.0.0.1:8000`).
  6. Envia reporte via `pipeline/trivy_to_gate.py`.
  7. Publica resumen del gate en `GITHUB_STEP_SUMMARY` y sube artifacts.

Decision del gate:

- `ALLOW` / `PASS`: continua CI.
- `WARNING`: continua CI con riesgo reportado.
- `BLOCK` o exit code distinto de 0: falla CI.

Artifacts generados:

- `reports/trivy-image.json`
- `reports/sentinel.log`
- `reports/sentinel-gate.log`

### Job `deploy`

- Corre solo en `push` a `main`.
- Requiere que `test` y `sentinel` pasen.
- Dispara deploy hook de Render.

## Nota sobre `GATE_URL`

En CI se usa `GATE_URL=http://127.0.0.1:8000` porque Sentinel se ejecuta dentro del mismo runner de GitHub Actions. No es una URL externa.

Si en logs aparece una linea inicial como:

```text
curl: (7) Failed to connect to 127.0.0.1 port 8000
```

generalmente es un intento temprano mientras el servicio arranca. Si luego aparece `GATE DECISION` y respuestas `200` del gate, la evaluacion si ocurrio correctamente.

## Ejecucion local de Sentinel (opcional)

Para replicar el gate localmente con dos repos separados:

1. Tener ambos repos en paralelo:
   - `...\LaborIABackend`
   - `...\Sentinel-AI-CD`

2. En Sentinel, iniciar API del gate:

```powershell
cd ..\Sentinel-AI-CD
$env:AI_DISABLED="true"
python -m uvicorn --app-dir app main:app --host 127.0.0.1 --port 8000
```

3. En backend, construir imagen y generar reporte Trivy:

```powershell
cd ..\LaborIABackend
docker build -t laboria-backend:local .
trivy image --format json --output reports/trivy-image.json laboria-backend:local
```

4. Enviar reporte al gate:

```powershell
python ..\Sentinel-AI-CD\pipeline\trivy_to_gate.py `
  --report reports/trivy-image.json `
  --image laboria-backend:local `
  --gate http://127.0.0.1:8000 `
  --dockerfile .\Dockerfile
```

## Dockerfile actual

`Dockerfile` usa `python:3.11-slim`, instala dependencias desde `requirements.txt`, copia el proyecto y ejecuta `uvicorn main:app` en puerto `8000`.
