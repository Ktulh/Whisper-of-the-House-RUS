param(
    [Parameter(Mandatory = $true)] [string]$Variants,   # dir made by tools/make_test_variants.py
    [Parameter(Mandatory = $true)] [string]$Original,   # pristine resources.assets
    [Parameter(Mandatory = $true)] [string]$Work        # scratch dir
)
# Tests for installer/Patcher.cs and installer/install.ps1 on copies of the game file.
# Never touches the real game. Exit code 1 if anything fails.
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Inst = Join-Path $Root 'installer'
$Tsv = Join-Path $Inst 'ru.tsv'
Add-Type -TypeDefinition (Get-Content -LiteralPath (Join-Path $Inst 'Patcher.cs') -Raw -Encoding UTF8) -Language CSharp
New-Item -ItemType Directory -Force $Work | Out-Null

$script:fail = 0
function Check($name, $ok, $detail = '') {
    if ($ok) { Write-Host "PASS  $name" -ForegroundColor Green }
    else { Write-Host "FAIL  $name  $detail" -ForegroundColor Red; $script:fail++ }
}
function Try-Patch($src, $tsv, $out) {
    try { $r = [WotHPatcher]::Patch($src, $tsv, $out); return @{ ok = $true; msg = $r } }
    catch { $e = $_.Exception; while ($e.InnerException) { $e = $e.InnerException }; return @{ ok = $false; msg = $e.Message } }
}
function Sha($p) { (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash }
function Utf8NoBom { New-Object Text.UTF8Encoding($false) }

$out = Join-Path $Work 'out.assets'

# ---------------------------------------------------------------- patcher unit tests
Remove-Item $out -ErrorAction SilentlyContinue
$r = Try-Patch $Original $Tsv $out
Check 'good file patches' $r.ok $r.msg
Check 'output file exists' (Test-Path $out)
$good = Sha $out

Check 'patched file reads as translated (>90% Cyrillic)' (([WotHPatcher]::CyrillicShare($out)) -gt 0.9)
Check 'original reads as untranslated (<1% Cyrillic)' (([WotHPatcher]::CyrillicShare($Original)) -lt 0.01)

foreach ($v in 'lang_code_changed', 'lang_count_changed', 'dup_object', 'truncated', 'garbage') {
    Remove-Item $out -ErrorAction SilentlyContinue
    $r = Try-Patch (Join-Path $Variants "$v.assets") $Tsv $out
    Check "refuses $v" ((-not $r.ok) -and (-not (Test-Path $out))) "ok=$($r.ok) msg=$($r.msg)"
    Write-Host "      -> $($r.msg)" -ForegroundColor DarkGray
}

$lines = Get-Content -LiteralPath $Tsv -Encoding UTF8
$tsvLines = @($lines | Where-Object { $_ -and -not $_.StartsWith('#') })
function Mangle($pct) {
    $i = 0
    $res = foreach ($l in $tsvLines) { $i++; if (($i % 100) -lt $pct) { 'NO_SUCH_KEY_' + $l } else { $l } }
    $p = Join-Path $Work "mangled$pct.tsv"
    [IO.File]::WriteAllLines($p, [string[]]$res, (Utf8NoBom))
    return $p
}
Remove-Item $out -ErrorAction SilentlyContinue
$r = Try-Patch $Original (Mangle 20) $out
Check 'refuses tsv with 80% coverage' ((-not $r.ok) -and (-not (Test-Path $out))) $r.msg
Write-Host "      -> $($r.msg)" -ForegroundColor DarkGray
$r = Try-Patch $Original (Mangle 5) $out
Check 'accepts tsv with 95% coverage' $r.ok $r.msg
Remove-Item $out -ErrorAction SilentlyContinue
$empty = Join-Path $Work 'empty.tsv'; [IO.File]::WriteAllText($empty, "# nothing`n")
$r = Try-Patch $Original $empty $out
Check 'refuses empty tsv' ((-not $r.ok) -and (-not (Test-Path $out))) $r.msg

# tsv in the wrong encoding (cp1251) must be refused, not turned into '?'
$cp = Join-Path $Work 'cp1251.tsv'
[IO.File]::WriteAllText($cp, ($tsvLines -join "`n") + "`n", [Text.Encoding]::GetEncoding(1251))
Remove-Item $out -ErrorAction SilentlyContinue
$r = Try-Patch $Original $cp $out
Check 'refuses tsv that is not UTF-8' ((-not $r.ok) -and (-not (Test-Path $out))) $r.msg
Write-Host "      -> $($r.msg)" -ForegroundColor DarkGray

# a row with an empty translation must not blank the game's text: it is simply skipped
$one = ($tsvLines | Select-Object -First 3) -join "`n"
$blank = Join-Path $Work 'blank.tsv'
[IO.File]::WriteAllText($blank, $one + "`n" + (($tsvLines | Select-Object -Skip 3 | Select-Object -First 1) -split "`t")[0] + "`t`n" + (($tsvLines | Select-Object -Skip 4) -join "`n") + "`n", (Utf8NoBom))
$r = Try-Patch $Original $blank $out
$expectN = $tsvLines.Count - 1
Check 'empty-translation row is skipped (the rest still applied)' ($r.ok -and $r.msg -match "$expectN\D+$expectN") $r.msg
Remove-Item $out -ErrorAction SilentlyContinue

# ---------------------------------------------------------------- installer end-to-end on a fake game folder
$game = Join-Path $Work 'steamapps\common\Whisper of the House'
$gdata = Join-Path $game 'Whisper of the House_Data'
Remove-Item (Join-Path $Work 'steamapps') -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $gdata | Out-Null
$asset = Join-Path $gdata 'resources.assets'
$backupFile = Join-Path $gdata 'resources.assets.rus-backup'
$markerFile = Join-Path $gdata 'rus-patch.sha256'
Copy-Item $Original $asset
$origHash = Sha $Original
$ps = Join-Path $Inst 'install.ps1'
function Run-Installer($mode, $path = $game) {
    $prev = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $ps -Mode $mode -GamePath $path 2>&1 | ForEach-Object { Write-Host "$_" }
    $ErrorActionPreference = $prev
    return $LASTEXITCODE
}
function Reset-Game($content = $Original) {
    Copy-Item $content $asset -Force
    Remove-Item $backupFile, $markerFile, "$asset.rus-tmp" -Force -ErrorAction SilentlyContinue
}

Write-Host '--- install' -ForegroundColor Cyan
$code = Run-Installer 'install'
Check 'install exit code 0' ($code -eq 0)
Check 'installed file == direct patch output' ((Sha $asset) -eq $good)
Check 'backup equals original' ((Sha $backupFile) -eq $origHash)

Write-Host '--- reinstall' -ForegroundColor Cyan
$code = Run-Installer 'install'
Check 'reinstall exit code 0' ($code -eq 0)
Check 'reinstall gives identical file' ((Sha $asset) -eq $good)
Check 'backup still original after reinstall' ((Sha $backupFile) -eq $origHash)

Write-Host '--- marker lost, backup kept: reinstall must reuse the backup' -ForegroundColor Cyan
Remove-Item $markerFile
$code = Run-Installer 'install'
Check 'exit 0 with lost marker' ($code -eq 0)
Check 'backup still original (not overwritten by patched file)' ((Sha $backupFile) -eq $origHash)
Check 'file patched again' ((Sha $asset) -eq $good)

Write-Host '--- empty marker file must not lock the installer' -ForegroundColor Cyan
[IO.File]::WriteAllText($markerFile, '')
$code = Run-Installer 'install'
Check 'install works with empty marker' ($code -eq 0)
[IO.File]::WriteAllText($markerFile, '')
$code = Run-Installer 'uninstall'
Check 'uninstall works with empty marker' (($code -eq 0) -and ((Sha $asset) -eq $origHash))

Write-Host '--- file patched by an OLDER translation (30% of lines), marker lost: backup must not be overwritten' -ForegroundColor Cyan
$part = Join-Path $Work 'part30.tsv'
$keep = [int]($tsvLines.Count * 0.3)
[IO.File]::WriteAllLines($part, [string[]]($tsvLines | Select-Object -First $keep), (Utf8NoBom))
$old = Join-Path $Work 'old_patched.assets'
$r = Try-Patch $Original $part $old
Check 'built an old-style partially patched file' $r.ok $r.msg
Reset-Game $old
Copy-Item $Original $backupFile                       # the real original is in the backup
$code = Run-Installer 'install'
Check 'exit 0' ($code -eq 0)
Check 'backup is still the pristine original' ((Sha $backupFile) -eq $origHash)
Check 'game file fully patched now' ((Sha $asset) -eq $good)

Write-Host '--- marker lost AND backup lost: must refuse' -ForegroundColor Cyan
Remove-Item $markerFile, $backupFile
$code = Run-Installer 'install'
Check 'refuses (exit 1)' ($code -eq 1)
Check 'file untouched by refused run' ((Sha $asset) -eq $good)
Check 'no backup of patched file was created' (-not (Test-Path $backupFile))

Write-Host '--- uninstall: translation present but backup missing -> refuse, keep everything' -ForegroundColor Cyan
Set-Content $markerFile (Sha $asset) -Encoding ASCII
$code = Run-Installer 'uninstall'
Check 'refuses (exit 1)' ($code -eq 1)
Check 'file untouched' ((Sha $asset) -eq $good)
Check 'marker kept' (Test-Path $markerFile)

Write-Host '--- uninstall after a normal install' -ForegroundColor Cyan
Reset-Game
Run-Installer 'install' | Out-Null
$code = Run-Installer 'uninstall'
Check 'uninstall exit 0' ($code -eq 0)
Check 'uninstall restores the original byte-for-byte' ((Sha $asset) -eq $origHash)
Check 'uninstall removes backup, marker and temp' (-not (Test-Path $backupFile) -and -not (Test-Path $markerFile) -and -not (Test-Path "$asset.rus-tmp"))

Write-Host '--- uninstall with lost marker' -ForegroundColor Cyan
Run-Installer 'install' | Out-Null
Remove-Item $markerFile
$code = Run-Installer 'uninstall'
Check 'uninstall with lost marker restores original' ((Sha $asset) -eq $origHash)

Write-Host '--- stale backup after a "Steam update" must not be restored over the new file' -ForegroundColor Cyan
Run-Installer 'install' | Out-Null
Copy-Item $Original $asset -Force              # Steam put a fresh (pretend-new) original in place
$freshHash = Sha $asset
$code = Run-Installer 'uninstall'
Check 'new game file left alone' ((Sha $asset) -eq $freshHash)
Check 'stale backup removed' (-not (Test-Path $backupFile))

Write-Host '--- damaged game file during uninstall: refuse, keep the backup' -ForegroundColor Cyan
Reset-Game
Run-Installer 'install' | Out-Null
Copy-Item (Join-Path $Variants 'truncated.assets') $asset -Force       # e.g. an interrupted copy
$code = Run-Installer 'uninstall'
Check 'refuses (exit 1)' ($code -eq 1)
Check 'backup kept for recovery' ((Test-Path $backupFile) -and ((Sha $backupFile) -eq $origHash))

Write-Host '--- broken game file: installer refuses and cleans up' -ForegroundColor Cyan
Reset-Game (Join-Path $Variants 'lang_code_changed.assets')
$brokenHash = Sha $asset
$code = Run-Installer 'install'
Check 'refuses broken file (exit 1)' ($code -eq 1)
Check 'broken file untouched' ((Sha $asset) -eq $brokenHash)
Check 'no leftover backup/tmp' (-not (Get-ChildItem $gdata -Filter '*.rus-*'))

Write-Host '--- game folder directly in a drive root (no steamapps parent)' -ForegroundColor Cyan
$letter = $null
foreach ($c in 'R', 'S', 'T', 'U', 'V') { if (-not (Test-Path "$($c):\")) { $letter = $c; break } }
if ($letter) {
    $rootDir = Join-Path $Work 'driveroot'
    Remove-Item $rootDir -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force (Join-Path $rootDir 'Whisper of the House\Whisper of the House_Data') | Out-Null
    Copy-Item $Original (Join-Path $rootDir 'Whisper of the House\Whisper of the House_Data\resources.assets')
    & subst.exe "$($letter):" $rootDir
    try {
        $code = Run-Installer 'install' "$($letter):\Whisper of the House"
        Check 'installs from a drive root' ($code -eq 0)
        $code = Run-Installer 'uninstall' "$($letter):\Whisper of the House"
        Check 'uninstalls from a drive root' (($code -eq 0) -and ((Sha (Join-Path $rootDir 'Whisper of the House\Whisper of the House_Data\resources.assets')) -eq $origHash))
    } finally { & subst.exe "$($letter):" /d }
} else { Write-Host 'SKIP  no free drive letter for subst' -ForegroundColor Yellow }

Write-Host ''
if ($script:fail -eq 0) { Write-Host 'ALL TESTS PASSED' -ForegroundColor Green; exit 0 }
else { Write-Host "$script:fail TEST(S) FAILED" -ForegroundColor Red; exit 1 }
