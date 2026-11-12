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
$SteamAppId = '2589500'
$TestedGameVersion = '1.3.0.6'
$TestedSteamBuild = '26070739'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Tsv = Join-Path $Here 'ru.tsv'

# Share of Cyrillic strings in the game's English column. The untouched game has ~0.03%, a translated one ~99%.
$PatchedAbove = 0.05     # more than this => the file is already translated
$PoisonedAbove = 0.01    # a backup with more than this is not an original

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
            # Steam writes this file as UTF-8 (library paths may contain Cyrillic)
            foreach ($m in [regex]::Matches((Get-Content -LiteralPath $vdf -Raw -Encoding UTF8), '"path"\s+"([^"]+)"')) {
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

# Cyrillic share of a game file (throws if the file cannot be read as the game's resource file)
function Get-Cyr($p) { return [WotHPatcher]::CyrillicShare($p) }

# Replace $asset with $backup safely: copy next to it, verify, then swap in one move
function Restore-FromBackup($backup, $asset) {
    $script:tmp = "$asset.rus-tmp"
    Copy-Item -LiteralPath $backup -Destination $script:tmp -Force
    if ((Get-Hash $script:tmp) -ne (Get-Hash $backup)) { throw 'Не удалось сделать точную копию резервного файла (проверьте свободное место на диске).' }
    Move-Item -LiteralPath $script:tmp -Destination $asset -Force
    $script:replaced = $true
}

$createdBackup = $false
$replaced = $false
$tmp = $null
$backup = $null

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

    # Compare the installed Steam build with the one the translation was made for (Steam installs only)
    if ($Mode -eq 'install') {
        $manifest = $null
        $common = Split-Path -Parent $GamePath
        $steamapps = if ($common) { Split-Path -Parent $common } else { $null }
        if ($steamapps) { $manifest = Join-Path $steamapps "appmanifest_$SteamAppId.acf" }
        if ($manifest -and (Test-Path -LiteralPath $manifest)) {
            $m = [regex]::Match((Get-Content -LiteralPath $manifest -Raw), '"buildid"\s+"(\d+)"')
            if ($m.Success -and $m.Groups[1].Value -ne $TestedSteamBuild) {
                Say "Внимание: перевод делался для версии игры $TestedGameVersion (сборка Steam $TestedSteamBuild)," 'Yellow'
                Say "а у вас установлена сборка $($m.Groups[1].Value). Перевод, скорее всего, встанет нормально," 'Yellow'
                Say 'но новые строки из обновления останутся на английском. Проверьте, нет ли новой версии перевода.' 'Yellow'
            }
        }
    }

    if (Get-Process -Name $GameFolderName -ErrorAction SilentlyContinue) {
        throw 'Игра запущена. Закройте её и запустите установщик снова.'
    }
    if (-not (Test-Path -LiteralPath $Tsv)) { throw 'Рядом с установщиком нет файла ru.tsv. Распакуйте архив целиком.' }

    $data = Join-Path $GamePath $DataFolderName
    $asset = Join-Path $data $AssetName
    $backup = Join-Path $data $BackupName
    $marker = Join-Path $data $MarkerName

    Say 'Подготавливаю установщик...'
    # the C# compiler writes into %TEMP%; a path with exotic letters can break it
    if ($env:TEMP -match '[^\u0000-\u007F]') {
        try {
            $safe = Join-Path $env:PUBLIC 'rus-installer-temp'
            New-Item -ItemType Directory -Force $safe | Out-Null
            $env:TEMP = $safe; $env:TMP = $safe
        } catch {}
    }
    $cs = Get-Content -LiteralPath (Join-Path $Here 'Patcher.cs') -Raw -Encoding UTF8
    Add-Type -TypeDefinition $cs -Language CSharp

    # the marker holds the hash of the file we produced; treat it as untrusted (may be empty or stale)
    $savedHash = ''
    if (Test-Path -LiteralPath $marker) { $savedHash = "$(Get-Content -LiteralPath $marker -Raw)".Trim() }
    $isPatched = ($savedHash -ne '') -and ($savedHash -eq (Get-Hash $asset))
    $hasBackup = Test-Path -LiteralPath $backup

    if ($Mode -eq 'uninstall') {
        $fileState = 'clean'
        if ($isPatched) { $fileState = 'patched' }
        else {
            try { if ((Get-Cyr $asset) -gt $PatchedAbove) { $fileState = 'patched' } }
            catch { $fileState = 'unreadable'; $readError = $_.Exception }
        }

        if ($fileState -eq 'unreadable') {
            $e = $readError; while ($e.InnerException) { $e = $e.InnerException }
            throw ("Файл игры не читается как ресурсы Unity: $($e.Message)`nРезервная копия (если была) сохранена: $backup`nПроверьте целостность файлов в Steam: ПКМ по игре -> Свойства -> Установленные файлы.")
        }
        if ($fileState -eq 'patched') {
            if (-not $hasBackup) { throw 'Перевод установлен, но резервной копии нет. Проверьте целостность файлов в Steam: ПКМ по игре -> Свойства -> Установленные файлы.' }
            if ((Get-Cyr $backup) -gt $PoisonedAbove) {
                throw 'Резервная копия сама содержит перевод, восстанавливать из неё нечего. Проверьте целостность файлов в Steam: ПКМ по игре -> Свойства -> Установленные файлы.'
            }
            Restore-FromBackup $backup $asset
            Remove-Item -LiteralPath $backup, $marker -Force -ErrorAction SilentlyContinue
            Say 'Готово: оригинальные файлы игры восстановлены.' 'Green'
        } else {
            # the game file is original (e.g. Steam updated it): an old backup must NOT be restored over it
            Remove-Item -LiteralPath $backup, $marker -Force -ErrorAction SilentlyContinue
            Say 'Перевод сейчас не установлен (возможно, Steam уже обновил игру). Если игра ведёт себя странно —' 'Yellow'
            Say 'Steam -> ПКМ по игре -> Свойства -> Установленные файлы -> Проверить целостность файлов.' 'Yellow'
        }
        return
    }

    # install / reinstall
    $share = Get-Cyr $asset
    if ($isPatched -or ($share -gt $PatchedAbove)) {
        # the file already holds a translation: the original must come from the backup
        if (-not $hasBackup) {
            throw 'Файл игры уже содержит перевод, но резервной копии нет. Проверьте целостность файлов в Steam (Свойства -> Установленные файлы) и запустите установку заново.'
        }
        if ((Get-Cyr $backup) -gt $PoisonedAbove) {
            throw 'Резервная копия сама содержит перевод. Проверьте целостность файлов в Steam (Свойства -> Установленные файлы) и запустите установку заново.'
        }
        if ($isPatched) { Say 'Перевод уже был установлен — обновляю его.' }
        else { Say 'Перевод уже установлен — обновляю его (резервная копия на месте).' }
        $source = $backup
    } else {
        Say 'Создаю резервную копию оригинального файла...'
        $createdBackup = $true
        Copy-Item -LiteralPath $asset -Destination $backup -Force
        if ((Get-Hash $backup) -ne (Get-Hash $asset)) { throw 'Не удалось сделать точную резервную копию (проверьте свободное место на диске).' }
        $source = $backup
    }

    Say 'Устанавливаю перевод (это может занять до минуты)...'
    $tmp = "$asset.rus-tmp"
    $result = [WotHPatcher]::Patch($source, $Tsv, $tmp)
    Move-Item -LiteralPath $tmp -Destination $asset -Force
    $replaced = $true
    Set-Content -LiteralPath $marker -Value (Get-Hash $asset) -Encoding ASCII

    Say ''
    Say "Готово! $result." 'Green'
    Say 'Запустите игру. Если в ней выбран другой язык — в настройках выберите English: вместо английского теперь русский.' 'Green'
}
catch {
    $e = $_.Exception
    while ($e.InnerException) { $e = $e.InnerException }   # unwrap .NET call wrappers
    Say ''
    Say ('ОШИБКА: ' + $e.Message) 'Red'
    if ($replaced) {
        Say 'Файл игры уже заменён, но завершить служебные действия не удалось. Если что-то не так — проверьте целостность файлов в Steam.' 'Red'
    } else {
        Say 'Файл игры не изменён.' 'Red'
        if ($createdBackup -and $backup) { Remove-Item -LiteralPath $backup -Force -ErrorAction SilentlyContinue }
    }
    if ($tmp -and (Test-Path -LiteralPath $tmp)) { Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue }
    exit 1
}
