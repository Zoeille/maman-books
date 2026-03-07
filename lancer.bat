@echo off
echo.
echo  maman-books
echo  --------------
echo.

:: Verifie que Python est installe
python --version >nul 2>&1
if errorlevel 1 (
    echo  ERREUR : Python n est pas installe ou n est pas dans le PATH.
    echo  Suis l etape 2 du guide LISEZMOI.md pour l installer.
    echo.
    pause
    exit /b 1
)

:: Verifie que le .env existe
if not exist ".env" (
    echo  ERREUR : Le fichier .env est introuvable.
    echo  Suis l etape 5 du guide LISEZMOI.md pour le creer.
    echo.
    pause
    exit /b 1
)

:: Installe les dependances si necessaire
echo  Installation des dependances...
pip install -r requirements.txt --quiet

echo.
echo  Tout est pret. Demarrage du bot...
echo  Ne ferme pas cette fenetre tant que tu veux utiliser le bot.
echo.

python bot.py

echo.
echo  Le bot s est arrete. Appuie sur une touche pour fermer.
pause >nul
