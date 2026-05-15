"""
Configuración centralizada para las pruebas de carga de LaborIA.
Contiene: credenciales de prueba, pool de usuarios, datos de muestra.
"""

# ── Auth ──────────────────────────────────────────────────────────────────────
JWT_SECRET = "sdfhoasdfujioasjfoiscj34253425jk34h43jh25gh2fyd2389hd2893"
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24

# ── Entorno ───────────────────────────────────────────────────────────────────
BASE_URL_LOCAL = "http://localhost:8000"
BASE_URL_STAGING = "https://laboriabackend-1.onrender.com"

# ── Pool de usuarios con perfil real en DB ────────────────────────────────────
# Solo usuarios que tienen perfil creado en Supabase (verificado 2026-05-15)
TEST_USERS = [
    {"id": 2,  "email": "david.sarria.a@gmail.com",             "name": "David Sarria"},
    {"id": 3,  "email": "business.911d@gmail.com",              "name": "business 911"},
    {"id": 4,  "email": "arciladiana191@gmail.com",             "name": "diana arcila"},
    {"id": 5,  "email": "strikeescarabajo@gmail.com",           "name": "Juan Diego Rodriguez"},
    {"id": 11, "email": "sebastian.albarracin0709@gmail.com",   "name": "Sebastian Albarracin"},
    {"id": 12, "email": "dani520.2005@gmail.com",               "name": "daniel alejandro rodriguez baracaldo"},
    {"id": 13, "email": "jeisson11sanchez@gmail.com",           "name": "Jeisson Sanchez"},
    {"id": 14, "email": "jd.rvelasquezp@gmail.com",            "name": "Juan Diego Rodriguez Velasquez"},
]

# ── Roles UUID disponibles en DB ──────────────────────────────────────────────
ROLE_IDS = [
    "00274e63-cff8-49fa-a038-e181e0e60cf9",  # Consultor Dynamics 365
    "007a4475-d745-4b4d-a906-9215d2ab67f2",  # Administrador de Redes
    "077e2b1e-faaf-46e8-a518-ba995e411cee",  # Site Reliability Engineer
    "096aa0f3-7080-43ee-a722-b4b5f6dcd653",  # Especialista RPA
]

# ── Datos de muestra para crear preguntas ─────────────────────────────────────
SAMPLE_QUESTIONS = [
    {
        "text": "¿Cómo garantizarías la calidad del código en un proyecto de software colaborativo?",
        "category": "Software Engineering",
        "difficulty": "medium",
        "expected_topics": ["code review", "testing", "CI/CD", "linting", "pair programming"],
    },
    {
        "text": "¿Cuáles son las diferencias entre SQL y NoSQL y cuándo usarías cada uno?",
        "category": "Databases",
        "difficulty": "medium",
        "expected_topics": ["ACID", "escalabilidad", "esquema flexible", "consistencia"],
    },
    {
        "text": "Explica el concepto de microservicios y sus ventajas frente a la arquitectura monolítica.",
        "category": "Architecture",
        "difficulty": "medium",
        "expected_topics": ["escalabilidad independiente", "despliegue", "comunicación", "resiliencia"],
    },
    {
        "text": "¿Cómo abordarías la optimización de una consulta SQL lenta en producción?",
        "category": "Databases",
        "difficulty": "hard",
        "expected_topics": ["EXPLAIN", "índices", "query plan", "particionamiento"],
    },
    {
        "text": "¿Qué estrategias utilizarías para manejar errores en una API REST?",
        "category": "Backend",
        "difficulty": "easy",
        "expected_topics": ["HTTP status codes", "logging", "retry", "validación", "mensajes de error"],
    },
]

# ── Respuestas de muestra para evaluación AI ──────────────────────────────────
SAMPLE_ANSWERS = [
    (
        "Para garantizar la calidad del código implementaría un pipeline de CI/CD con pruebas unitarias "
        "e integración. Usaría herramientas como SonarQube para análisis estático, revisiones de código "
        "obligatorias antes de mergear, y convenciones de estilo con linters. También promovería el TDD "
        "y la documentación del código para facilitar el mantenimiento."
    ),
    (
        "SQL es ideal para datos estructurados con relaciones claras y donde se necesita ACID. "
        "NoSQL es mejor cuando los datos son semiestructurados o varían mucho en esquema, y cuando "
        "se necesita escalabilidad horizontal masiva. Elegiría PostgreSQL para finanzas y MongoDB "
        "para catálogos de productos donde el esquema puede cambiar frecuentemente."
    ),
    (
        "Los microservicios permiten que cada componente escale de forma independiente y se despliegue "
        "sin afectar al resto del sistema. La principal ventaja es la resiliencia: si un servicio falla, "
        "no tumba toda la aplicación. Sin embargo, introducen complejidad en la comunicación entre servicios "
        "y requieren una buena estrategia de observabilidad con logging distribuido y trazabilidad."
    ),
    (
        "Primero ejecutaría EXPLAIN ANALYZE para entender el plan de ejecución. Luego revisaría si faltan "
        "índices en las columnas del WHERE y JOIN. Si la consulta es compleja, consideraría materialized views "
        "o particionamiento. También revisaría si hay N+1 queries o joins innecesarios que puedan simplificarse."
    ),
    (
        "En una API REST manejaría errores usando códigos HTTP semánticos: 400 para errores de cliente, "
        "404 para recursos no encontrados, 500 para errores internos. Implementaría un middleware global "
        "de manejo de excepciones para evitar repetición. Agregaría logging estructurado con correlation IDs "
        "para trazabilidad, y respuestas de error consistentes con el formato {detail: string}."
    ),
]

# ── Límites para el escenario AI ──────────────────────────────────────────────
# Máximo de reintentos al hacer polling de evaluación
AI_POLL_MAX_RETRIES = 12
AI_POLL_INTERVAL_SECONDS = 2
