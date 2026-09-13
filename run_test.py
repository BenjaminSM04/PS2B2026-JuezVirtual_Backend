"""Ejecuta las comprobaciones y propaga cualquier error al CI."""
import argparse
import subprocess
import sys

parser = argparse.ArgumentParser()
parser.add_argument("-c", "--coverage", action="store_true")
parser.add_argument("-m", "--module", default="")
args = parser.parse_args()

commands = [
    [sys.executable, "-m", "flake8", "--statistics", "."],
    [sys.executable, "manage.py", "check"],
    [sys.executable, "manage.py", "makemigrations", "--check", "--dry-run"],
    [sys.executable, "-m", "coverage", "run", "--source=.", "manage.py", "test"],
]
if args.module:
    commands[-1].append(args.module)
for command in commands:
    result = subprocess.run(command, check=False)
    if result.returncode:
        sys.exit(result.returncode)
sys.exit(subprocess.run([sys.executable, "-m", "coverage", "report"], check=False).returncode)
