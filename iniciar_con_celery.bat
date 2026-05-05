@echo off
echo.
echo ============================================================
echo   PERSEUS CONTROL v4 — Iniciar con Celery
echo ============================================================
echo.
echo Necesitas 3 terminales abiertas con el venv activo.
echo.
echo TERMINAL 1 — Servidor Django:
echo   python manage.py runserver
echo.
echo TERMINAL 2 — Celery Worker (ejecuta las tareas):
echo   celery -A config worker --loglevel=info --pool=solo
echo   (en Windows se usa --pool=solo en lugar de --concurrency)
echo.
echo TERMINAL 3 — Celery Beat (programa las tareas):
echo   celery -A config beat --loglevel=info
echo.
echo ============================================================
echo   IMPORTANTE: Redis debe estar corriendo primero.
echo   Descargar Redis para Windows:
echo   https://github.com/microsoftarchive/redis/releases
echo   Ejecutar redis-server.exe antes de iniciar Celery.
echo ============================================================
echo.

set /p respuesta="^¿Iniciar Redis ahora? (s/n): "
if /i "%respuesta%"=="s" (
    echo Intentando iniciar Redis...
    start "Redis" redis-server.exe
    timeout /t 2 >nul
)

echo.
echo Iniciando Django en esta terminal...
echo Abre 2 terminales mas y ejecuta los comandos de arriba.
echo.
python manage.py runserver
