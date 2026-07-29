# Wrapper de démarrage pour app.py (bot Lutessia) — pensé pour un lancement au boot
# du VPS via le Planificateur de tâches Windows, sans surveillance humaine.
#
# Ce que ça corrige : sur ce VPS, un redémarrage sur deux échoue à relancer le bot
# proprement (voir historique de la conversation) — le plus souvent parce que
# app.py est lancé "à la main", donc rien ne le relance si le réseau/MT5 ne sont
# pas encore prêts au moment exact du lancement, ou si le process crash plus tard.
#
# Deux protections, indépendantes :
#   1. Attente active du réseau avant le tout premier lancement (le boot du VPS ne
#      garantit pas que la connexion soit déjà montée).
#   2. Boucle de relance : si python app.py se termine (crash ou sortie normale),
#      on le relance après un court délai, indéfiniment.

$ErrorActionPreference = "Continue"

# Toujours travailler depuis le dossier du script, quel que soit le contexte
# d'appel (Planificateur de tâches, double-clic, etc.) — app.py utilise des
# chemins relatifs (.env, historique_lutessia.csv, correlation_matrix.csv...).
Set-Location -Path $PSScriptRoot

$LogPath = Join-Path $PSScriptRoot "bot_wrapper.log"

function Write-WrapperLog {
    param([string]$Message)
    $line = "{0} | {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -Path $LogPath -Value $line -Encoding utf8
    Write-Host $line
}

function Wait-ForNetwork {
    param([int]$TimeoutSeconds = 300)
    $elapsed = 0
    while ($elapsed -lt $TimeoutSeconds) {
        if (Test-Connection -ComputerName "8.8.8.8" -Count 1 -Quiet -ErrorAction SilentlyContinue) {
            Write-WrapperLog "Réseau disponible."
            return $true
        }
        Write-WrapperLog "Réseau indisponible, nouvelle tentative dans 5s..."
        Start-Sleep -Seconds 5
        $elapsed += 5
    }
    Write-WrapperLog "Réseau toujours indisponible après ${TimeoutSeconds}s — on tente de démarrer quand même."
    return $false
}

Write-WrapperLog "=== Démarrage du wrapper start_bot.ps1 ==="
Wait-ForNetwork | Out-Null

while ($true) {
    Write-WrapperLog "Lancement de python app.py..."
    python app.py
    $exitCode = $LASTEXITCODE
    Write-WrapperLog "app.py s'est arrêté (code de sortie : $exitCode). Relance dans 10s..."
    Start-Sleep -Seconds 10
}
