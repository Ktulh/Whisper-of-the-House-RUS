param(
    [ValidateSet('install', 'uninstall')] [string]$Mode = 'install',
    [string]$GamePath = ''
)
$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}

$GameFolderName = 'Whisper of the House'
$DataFolderName = 'Whisper of the House_Data'
$AssetName = 'resources.assets'
$BackupName = 'resources.assets.rus-backup'
$MarkerName = 'rus-patch.sha256'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path

function Say($text, $color = 'Gray') { Write-Host $text -ForegroundColor $color }

function Test-GameFolder($p) {
    return $p -and (Test-Path -LiteralPath (Join-Path $p "$DataFolderName\$AssetName"))
}

function Find-Game {
    $candidates = New-Object System.Collections.Generic.List[string]
    # 1) the installer was unpacked right into the game folder
    $candidates.Add($Here); $candidates.Add((Split-Path -Parent $Here))
    # 2) Steam libraries
    $steamRoots = @()
    foreach ($key in 'HKCU:\Software\Valve\Steam', 'HKLM:\SOFTWARE\WOW6432Node\Valve\Steam', 'HKLM:\SOFTWARE\Valve\Steam') {
        try {
            $k = Get-ItemProperty -Path $key -ErrorAction Stop
            if ($k.SteamPath) { $steamRoots += $k.SteamPath }
            if ($k.InstallPath) { $steamRoots += $k.InstallPath }
        } catch {}
    }
    foreach ($root in ($steamRoots | Select-Object -Unique)) {
        $root = $root -replace '/', '\'
        $candidates.Add((Join-Path $root "steamapps\common\$GameFolderName"))
        $vdf = Join-Path $root 'steamapps\libraryfolders.vdf'
        if (Test-Path -LiteralPath $vdf) {
            foreach ($m in [regex]::Matches((Get-Content -LiteralPath $vdf -Raw), '"path"\s+"([^"]+)"')) {
                $lib = $m.Groups[1].Value -replace '\\\\', '\'
                $candidates.Add((Join-Path $lib "steamapps\common\$GameFolderName"))
            }
        }
    }
    foreach ($c in $candidates) { if (Test-GameFolder $c) { return (Resolve-Path -LiteralPath $c).Path } }
    return $null
}

function Ask-GameFolder {
    Add-Type -AssemblyName System.Windows.Forms
    $dlg = New-Object System.Windows.Forms.FolderBrowserDialog
    $dlg.Description = "Укажите папку игры $GameFolderName (в ней лежит '$GameFolderName.exe')"
    if ($dlg.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { return $dlg.SelectedPath }
    return $null
}

function Get-Hash($p) { return (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash }

try {
    Say ''
    Say '=== Русификатор Whisper of the House ===' 'Cyan'
    Say ''

    if (-not (Test-GameFolder $GamePath)) { $GamePath = Find-Game }
    if (-not $GamePath) {
        Say 'Не удалось найти игру автоматически. Выберите папку игры в открывшемся окне...' 'Yellow'
        $GamePath = Ask-GameFolder
    }
    if (-not (Test-GameFolder $GamePath)) { throw "В выбранной папке нет игры (не найден $DataFolderName\$AssetName)." }
    Say "Папка игры: $GamePath"

    if (Get-Process -Name $GameFolderName -ErrorAction SilentlyContinue) {
        throw 'Игра запущена. Закройте её и запустите установщик снова.'
    }

    $data = Join-Path $GamePath $DataFolderName
    $asset = Join-Path $data $AssetName
    $backup = Join-Path $data $BackupName
    $marker = Join-Path $data $MarkerName

    $isPatched = (Test-Path -LiteralPath $marker) -and ((Get-Content -LiteralPath $marker -Raw).Trim() -eq (Get-Hash $asset))

    if ($Mode -eq 'uninstall') {
        if ($isPatched -and (Test-Path -LiteralPath $backup)) {
            Copy-Item -LiteralPath $backup -Destination $asset -Force
            Remove-Item -LiteralPath $backup, $marker -Force
            Say 'Готово: оригинальные файлы игры восстановлены.' 'Green'
        } else {
            Remove-Item -LiteralPath $backup, $marker -Force -ErrorAction SilentlyContinue
            Say 'Перевод сейчас не установлен (возможно, Steam уже обновил игру). Если игра ведёт себя странно —' 'Yellow'
            Say 'Steam -> ПКМ по игре -> Свойства -> Установленные файлы -> Проверить целостность файлов.' 'Yellow'
        }
        return
    }

    # install / reinstall
    if ($isPatched) {
        if (-not (Test-Path -LiteralPath $backup)) { throw 'Перевод уже установлен, но резервная копия пропала. Проверьте целостность файлов в Steam и запустите установку заново.' }
        Say 'Перевод уже был установлен — обновляю его.'
        $source = $backup
    } else {
        Say 'Создаю резервную копию оригинального файла...'
        Copy-Item -LiteralPath $asset -Destination $backup -Force
        $source = $backup
    }

    Say 'Подготавливаю установщик...'
    $cs = Get-Content -LiteralPath (Join-Path $Here 'Patcher.cs') -Raw -Encoding UTF8
    Add-Type -TypeDefinition $cs -Language CSharp

    Say 'Устанавливаю перевод (это может занять до минуты)...'
    $tmp = "$asset.rus-tmp"
    $result = [WotHPatcher]::Patch($source, (Join-Path $Here 'ru.tsv'), $tmp)
    Move-Item -LiteralPath $tmp -Destination $asset -Force
    Set-Content -LiteralPath $marker -Value (Get-Hash $asset) -Encoding ASCII

    Say ''
    Say "Готово! $result." 'Green'
    Say 'Запустите игру. Если в ней выбран другой язык — в настройках выберите English: вместо английского теперь русский.' 'Green'
}
catch {
    Say ''
    Say ('ОШИБКА: ' + $_.Exception.Message) 'Red'
    Say 'Файлы игры не изменены (или восстановлены из резервной копии).' 'Red'
    if ($tmp -and (Test-Path -LiteralPath $tmp)) { Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue }
    exit 1
}
