import os
from pathlib import Path

# Fuerza uso de SQLite local para todas las pruebas y evita escribir en la DB real
db_path = Path("test.db")
if db_path.exists():
    db_path.unlink()

os.environ.setdefault("DATABASE_URL", f"sqlite:///{db_path}")
os.environ.setdefault("JWT_SECRET", "test-secret")
