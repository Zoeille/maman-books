@echo off
echo ===================================
echo   Maman-Books - Serveur Web
echo ===================================
echo.

REM Vérifier si Python est installé
python --version >nul 2>&1
if errorlevel 1 (
    echo Erreur: Python n'est pas installé ou pas dans le PATH.
    echo Veuillez installer Python depuis https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

REM Vérifier si le fichier .env existe
if not exist ".env" (
    echo Attention: Le fichier .env n'existe pas.
    echo Copiez .env.example vers .env et configurez-le.
    echo.
    pause
    exit /b 1
)

REM Installer les dépendances si nécessaire
if not exist "venv\" (
    echo Installation des dépendances...
    python -m pip install --quiet --upgrade pip
    python -m pip install --quiet -r requirements.txt
    echo.
)

echo Démarrage du serveur web...
echo.
echo Le serveur sera accessible sur: http://localhost:5000
echo.
echo Appuyez sur Ctrl+C pour arrêter le serveur.
echo ===================================
echo.

REM Lancer le serveur web
python web_server.py

pause
