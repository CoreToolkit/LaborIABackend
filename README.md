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

Luego de ejecutar el respectivo comando para iniciar la API
Prueba en navegador: http://localhost:8000/
Ver docs automáticas: http://localhost:8000/docs
