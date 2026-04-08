# LaborIABackend

Backend FastAPI de LaborIA con pruebas unitarias, migraciones Alembic y gate de seguridad usando el proyecto real `Sentinel-AI-CD`.

## Estado actual

- Stack: Python 3.11 + FastAPI + SQLAlchemy + Alembic.
- Deploy productivo actual: Render por deploy hook de código fuente.
- Artefacto de seguridad para CI: imagen Docker del backend.
- Gate de seguridad: servicio externo `Sentinel-AI-CD`, consumido como proyecto separado.
- Fuente actual del gate en CI: fork `JuanDiegoRV/Sentinel-AI-CD`, rama `feature/Laboria_compatibility`.

## Ejecución local de la API

1. Crear el entorno virtual:
   `python -m venv venv`
2. Activarlo:
   `.\venv\Scripts\Activate.ps1`
3. Instalar dependencias:
   `python run.py install`
4. Crear `.env` a partir de `.env.example`
5. Ejecutar pruebas:
   `python run.py test`
6. Levantar la API:
   `python run.py run`

## Flujo real de seguridad

`LaborIABackend` no embebe Sentinel. El pipeline hace:

1. Ejecuta pruebas del backend
2. Construye la imagen Docker del backend
3. Escanea la imagen con `trivy image`
4. Levanta `Sentinel-AI-CD`
5. Envía el reporte mediante el adaptador oficial `pipeline/trivy_to_gate.py`
6. Bloquea deploy solo si la respuesta es `REJECTED`
7. Continúa si la decisión es `WARNING` o `APPROVED`

El workflow toma Sentinel desde:

- repositorio: `JuanDiegoRV/Sentinel-AI-CD`
- rama: `feature/Laboria_compatibility`
- ramas del backend habilitadas para validar el gate: `main`, `develop`, `sentinel-test-branch`
- en `sentinel-test-branch` los tests se omiten temporalmente para validar solo la integración del gate

## Prueba local con dos repos separados

Supón esta estructura local:

- `C:\Users\strik\Downloads\LaborIABackend`
- `C:\Users\strik\Downloads\Sentinel-AI-CD`

### Terminal 1: Sentinel real

Desde `Sentinel-AI-CD\app`:

```powershell
$env:AI_DISABLED="true"
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Verifica salud:

```powershell
curl.exe http://127.0.0.1:8000/health
```

### Terminal 2: backend + imagen + Trivy + gate

Desde `LaborIABackend`:

```powershell
docker build -t laboria-backend:local .
trivy image --format json --output reports/trivy-image.json laboria-backend:local
python ..\Sentinel-AI-CD\pipeline\trivy_to_gate.py `
  --report reports/trivy-image.json `
  --image laboria-backend:local `
  --gate http://127.0.0.1:8000 `
  --dockerfile .\Dockerfile
```

Interpretación esperada:

- exit `0`: `APPROVED`
- exit `1`: `REJECTED`
- exit `2`: `WARNING`
- exit `3`: fallo técnico del gate

## Docker del backend

El `Dockerfile` del backend existe solo para:

- construir una imagen escaneable en CI
- permitir pruebas locales con `trivy image`
- alimentar el Sentinel original sin cambiar todavía el deploy real

No cambia el despliegue productivo de Render en esta fase.

## Archivos relevantes

- `Dockerfile`
- `.dockerignore`
- `.github/workflows/ci.yml`
- `.github/workflows/tests.yml`

## Notas

- Las variables sensibles se inyectan en runtime; no se usan como parte del build.
- `test.db` y `reports/` están excluidos del repositorio.

hola :)
