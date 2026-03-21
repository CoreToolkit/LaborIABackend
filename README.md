# LaborIABackend

## Ejecución del Proyecto

Crear virtual environment: python -m venv venv
Activar venv: .\venv\Scripts\Activate.ps1

#### Ejecucion luego de tener el ambiente listo

Instalar dependencias
`python run.py install`

Ejecutar pruebas unitarias
`python run.py test`

Generar reporte de cobertura de codigo, este comando genera un archivo HTML en htmlcov/index.html donde se puede ver la cobertura real del codigo.
`python run.py coverage`

Ejecutar la API
`python run.py run`

Ejecutar la API teniendo en cuenta todos los pasos anteriores para asi tener mayor control a la hora de ejecutar la API teniendo en cuenta que los test esten funcionando como deben ser y pasando la cobertura de 80%
`python run.py all`

Limpiar archivos generados en cache
`python run.py clean`

## Carga inicial de roles, tecnologias y role_skills

Se agrego un script para poblar las tablas `job_roles`, `technologies` y `role_skills` a partir de un catalogo JSON.

1. Asegura migraciones aplicadas (para tener las tablas creadas):
`alembic upgrade head`

2. Ejecuta primero en modo simulacion (recomendado):
`python scripts/seed_roles_from_catalog.py --dry-run`

3. Ejecuta la carga real:
`python scripts/seed_roles_from_catalog.py`

4. Si el archivo tiene otro nombre o ruta:
`python scripts/seed_roles_from_catalog.py --file .\\ruta\\mi_catalogo.json`

Notas importantes:
- Si existe `roles_dialog.json`, el script lo usa por prioridad; si no, usa `roles_catalog.json`.
- El proceso es idempotente por nombre de rol: crea roles nuevos y actualiza existentes.
- Para cada rol, reemplaza sus `role_skills` en cada ejecucion para mantener consistencia con el JSON.
- Tecnologias existentes no se duplican; se reutilizan por nombre.

Luego de ejecutar el respectivo comando para iniciar la API
Prueba en navegador: http://localhost:8000/
Ver docs automáticas: http://localhost:8000/docs
