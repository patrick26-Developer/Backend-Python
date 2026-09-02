# Équivalent PowerShell du Makefile, pour Windows sans `make`.
# Usage :  .\tasks.ps1 <cible>      ex:  .\tasks.ps1 check
param(
    [Parameter(Position = 0)]
    [ValidateSet("install", "lint", "format", "type", "test", "cov", "check", "run", "clean", "help")]
    [string]$Task = "help"
)

$ErrorActionPreference = "Stop"

function Invoke-Install {
    python -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -U pip
    .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
}
function Invoke-Lint   { ruff check .; ruff format --check . }
function Invoke-Format { ruff format .; ruff check --fix . }
function Invoke-Type   { mypy taskman }
function Invoke-Test   { pytest }
function Invoke-Cov    { pytest --cov=taskman --cov-report=term-missing }
function Invoke-Check  { Invoke-Lint; Invoke-Type; Invoke-Test }
function Invoke-Run    { fastapi dev taskman/main.py }
function Invoke-Clean  {
    "@('.ruff_cache','.mypy_cache','.pytest_cache','htmlcov','.coverage')" | Out-Null
    foreach ($p in '.ruff_cache', '.mypy_cache', '.pytest_cache', 'htmlcov', '.coverage') {
        if (Test-Path $p) { Remove-Item -Recurse -Force $p }
    }
}
function Invoke-Help {
    @"
Cibles disponibles :
  install   Crée le venv + installe les dépendances (dev)
  lint      ruff check + ruff format --check
  format    ruff format + ruff check --fix
  type      mypy --strict
  test      pytest
  cov       pytest + couverture
  check     lint + type + test (comme la CI)
  run       serveur de dev FastAPI
  clean     supprime les caches
"@
}

switch ($Task) {
    "install" { Invoke-Install }
    "lint"    { Invoke-Lint }
    "format"  { Invoke-Format }
    "type"    { Invoke-Type }
    "test"    { Invoke-Test }
    "cov"     { Invoke-Cov }
    "check"   { Invoke-Check }
    "run"     { Invoke-Run }
    "clean"   { Invoke-Clean }
    default   { Invoke-Help }
}
