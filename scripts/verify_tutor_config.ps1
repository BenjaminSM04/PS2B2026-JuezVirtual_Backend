param(
    [string]$Image = "oj-backend:local",
    [switch]$FullSuite
)

$ErrorActionPreference = "Stop"
$taskBackendRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$taskSuffix = [Guid]::NewGuid().ToString("N").Substring(0, 10)
$taskNetwork = "tutor-config-test-$taskSuffix"
$taskPostgres = "$taskNetwork-postgres"
$taskRedis = "$taskNetwork-redis"
$taskRunner = "$taskNetwork-runner"
$taskCreatedContainers = @()
$taskNetworkCreated = $false

function Invoke-CheckedDocker {
    param([string[]]$DockerArguments)
    & docker @DockerArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Docker falló con código $LASTEXITCODE."
    }
}

# Todas las bases, sesiones de caché y archivos de prueba son temporales.
$taskBootstrap = @'
from pathlib import Path
import os
import shutil
import subprocess
import time
import django
import psycopg2

for directory in ('config', 'log', 'ssl', 'test_case', 'public/upload', 'public/avatar', 'public/website'):
    Path('/data', directory).mkdir(parents=True, exist_ok=True)
Path('/data/config/secret.key').write_text('isolated-tutor-config-verification-only')
shutil.copyfile('/app/data/public/avatar/default.png', '/data/public/avatar/default.png')
os.environ['DJANGO_SETTINGS_MODULE'] = 'oj.settings'
for attempt in range(80):
    try:
        psycopg2.connect(host=os.environ['POSTGRES_HOST'], dbname=os.environ['POSTGRES_DB'],
                         user=os.environ['POSTGRES_USER'], password=os.environ['POSTGRES_PASSWORD']).close()
        break
    except psycopg2.OperationalError:
        if attempt == 79:
            raise
        time.sleep(0.25)
subprocess.run(['flake8', 'ai_tutor'], check=True)
django.setup()
from django.core.management import call_command
call_command('check')
call_command('makemigrations', 'ai_tutor', check=True, dry_run=True)
modules = [] if os.environ['TUTOR_FULL_SUITE'] == '1' else ['ai_tutor.tests']
call_command('test', *modules, interactive=False, verbosity=2)
'@

try {
    Invoke-CheckedDocker -DockerArguments @("network", "create", "--label", "purpose=tutor-config-verification", $taskNetwork)
    $taskNetworkCreated = $true
    Invoke-CheckedDocker -DockerArguments @(
        "run", "-d", "--rm", "--name", $taskPostgres, "--network", $taskNetwork,
        "--label", "purpose=tutor-config-verification", "--tmpfs", "/var/lib/postgresql/data",
        "-e", "POSTGRES_DB=tutor_config_test", "-e", "POSTGRES_USER=tutor_test", "-e", "POSTGRES_PASSWORD=tutor_test",
        "postgres:10-alpine"
    )
    $taskCreatedContainers += $taskPostgres
    Invoke-CheckedDocker -DockerArguments @(
        "run", "-d", "--rm", "--name", $taskRedis, "--network", $taskNetwork,
        "--label", "purpose=tutor-config-verification", "redis:7-alpine"
    )
    $taskCreatedContainers += $taskRedis
    $taskFull = if ($FullSuite) { "1" } else { "0" }
    $taskCreatedContainers += $taskRunner
    Invoke-CheckedDocker -DockerArguments @(
        "run", "--rm", "--name", $taskRunner, "--network", $taskNetwork,
        "--label", "purpose=tutor-config-verification",
        "--mount", "type=bind,source=$taskBackendRoot,target=/app,readonly", "--tmpfs", "/data",
        "-e", "PYTHONDONTWRITEBYTECODE=1", "-e", "OJ_ENV=production", "-e", "TUTOR_FULL_SUITE=$taskFull",
        "-e", "POSTGRES_DB=tutor_config_test", "-e", "POSTGRES_USER=tutor_test", "-e", "POSTGRES_PASSWORD=tutor_test",
        "-e", "POSTGRES_HOST=$taskPostgres", "-e", "REDIS_HOST=$taskRedis",
        "--entrypoint", "python", $Image, "-c", $taskBootstrap
    )
}
finally {
    foreach ($taskContainer in $taskCreatedContainers) {
        # Puede haber terminado por --rm. Nunca se enumeran ni detienen servicios del deploy.
        $taskExisting = & docker ps -aq --filter "name=^/$taskContainer$"
        if ($taskExisting) {
            & docker rm -f $taskContainer
        }
    }
    if ($taskNetworkCreated) {
        & docker network rm $taskNetwork
    }
}
