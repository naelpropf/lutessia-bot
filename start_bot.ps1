# Wrapper de démarrage pour app.py ET monitor.py (bot Lutessia) — pensé pour un
# lancement au boot du VPS via le Planificateur de tâches Windows, sans surveillance
# humaine.
#
# Ce que ça corrige : sur ce VPS, un redémarrage sur deux échoue à relancer le bot
# proprement (voir historique de la conversation) — le plus souvent parce que
# app.py/monitor.py sont lancés "à la main", donc rien ne les relance si le
# réseau/MT5 ne sont pas encore prêts au moment exact du lancement, ou si l'un des
# deux process crash plus tard (constaté le 18/08 : silence de plus de 5h sans
# aucune trace d'erreur, cause du crash jamais identifiée avec certitude -- d'où
# l'intérêt d'un filet de sécurité qui ne dépend pas de comprendre la cause).
#
# Trois protections, indépendantes :
#   1. Attente active du réseau avant le tout premier lancement (le boot du VPS ne
#      garantit pas que la connexion soit déjà montée).
#   2. Boucle de relance pour app.py (thread principal) : s'il se termine (crash ou
#      sortie normale), on le relance après un court délai, indéfiniment.
#   3. Boucle de relance identique pour monitor.py, en arrière-plan (Start-Job) --
#      les deux process sont surveillés indépendamment, l'un ne bloque pas l'autre.

$ErrorActionPreference = "Continue"

# Sans ça, les print() de app.py/monitor.py restent bufferisés en mémoire tant que
# stdout n'est pas un vrai terminal (cas ici, sous le Planificateur de tâches) --
# app_run.log/monitor_run.log resteraient vides pendant de longues périodes, comme
# constaté le 18/08 lors du premier test de ce wrapper.
$env:PYTHONUNBUFFERED = "1"
$env:PYTHONIOENCODING = "utf-8"

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

# monitor.py surveillé en arrière-plan, dans le même style de boucle -- job séparé
# pour ne jamais être bloqué par (ni bloquer) la boucle app.py ci-dessous.
Start-Job -Name "LutessiaMonitorWatchdog" -ScriptBlock {
    param($WorkDir, $LogPath)
    Set-Location -Path $WorkDir
    function Write-Log($Message) {
        $line = "{0} | {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
        Add-Content -Path $LogPath -Value $line -Encoding utf8
    }
    while ($true) {
        Write-Log "Lancement de python monitor.py..."
        # Redirection via cmd.exe (>>), pas l'opérateur PowerShell *>> : ce dernier
        # capture la sortie comme texte puis la réécrit en UTF-16, ce qui mojibake
        # les accents/emojis de print() (UTF-8) -- constaté le 18/08. cmd.exe fait
        # une redirection de descripteur brute au niveau OS, sans réencodage,
        # équivalent au nohup .. > monitor_run.log 2>&1 utilisé jusqu'ici en manuel.
        cmd /c "python monitor.py >> monitor_run.log 2>&1"
        Write-Log "monitor.py s'est arrêté (code de sortie : $LASTEXITCODE). Relance dans 10s..."
        Start-Sleep -Seconds 10
    }
} -ArgumentList $PSScriptRoot, $LogPath | Out-Null

while ($true) {
    Write-WrapperLog "Lancement de python app.py..."
    # Même raisonnement que monitor.py ci-dessus (cmd.exe, pas *>> -- cf. commentaire
    # dans le job monitor.py) : app.py n'a AUCUN logging fichier interne (tout passe
    # par print()), donc app_run.log est la seule trace de son activité (signaux
    # traités/ignorés, erreurs [risk]/[MT5]...) -- perdre cette redirection rendrait
    # le bot quasiment impossible à diagnostiquer.
    cmd /c "python app.py >> app_run.log 2>&1"
    $exitCode = $LASTEXITCODE
    Write-WrapperLog "app.py s'est arrêté (code de sortie : $exitCode). Relance dans 10s..."
    Start-Sleep -Seconds 10
}
