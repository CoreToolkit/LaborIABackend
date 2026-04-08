import subprocess
import sys
import shutil
from pathlib import Path


def run_command(command, step_name):
    print(f"\n--- {step_name} ---")

    result = subprocess.run(command, check=False)

    if result.returncode != 0:
        print(f"\n❌ Error en: {step_name}")
        sys.exit(result.returncode)

    print(f"✅ {step_name} completado")


def install():
    run_command(
        [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
        "Instalando dependencias"
    )


def test():
    run_command(
        [sys.executable, "-m", "pytest"],
        "Ejecutando tests"
    )


def coverage():
    run_command(
        [
            sys.executable,
            "-m",
            "pytest",
            "--cov",
            "--cov-branch",
            "--cov-report=term-missing",
            "--cov-report=html",
            "--cov-fail-under=80",
        ],
        "Calculando coverage"
    )


def run():
    run_command(
        [sys.executable, "-m", "uvicorn", "main:app", "--reload"],
        "Levantando API"
    )


def clean():
    print("\n--- Limpiando proyecto ---")

    folders = ["__pycache__", ".pytest_cache", "htmlcov"]
    files = [".coverage", "test.db"]

    for folder in folders:
        path = Path(folder)
        if path.exists():
            shutil.rmtree(path)
            print(f"🧹 Eliminado {folder}")

    for file in files:
        path = Path(file)
        if path.exists():
            path.unlink()
            print(f"🧹 Eliminado {file}")

    print("✅ Limpieza completada")


def all():
    install()
    test()
    coverage()
    run()


commands = {
    "install": install,
    "test": test,
    "coverage": coverage,
    "run": run,
    "clean": clean,
    "all": all
}


def main():
    if len(sys.argv) < 2:
        print("\nComandos disponibles:")
        for cmd in commands:
            print(f"  python run.py {cmd}")
        sys.exit(1)

    command = sys.argv[1]

    if command not in commands:
        print(f"\n❌ Comando desconocido: {command}")
        sys.exit(1)

    commands[command]()


if __name__ == "__main__":
    main()
