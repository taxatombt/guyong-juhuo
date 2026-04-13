Set-Location 'E:\juhuo'

# 1. Delete empty directories
$empties = @(
    'action_signal',
    'gstack_integration',
    'gstack_virtual_team',
    'hermes_evolution',
    'hermes_integration',
    'skills',
    'templates',
    'test_snapshots'
)
foreach ($d in $empties) {
    if (Test-Path $d) {
        $files = Get-ChildItem $d -File -ErrorAction SilentlyContinue
        if (-not $files) {
            Remove-Item $d -Recurse -Force
            Write-Host "[DEL] $d/"
        }
    }
}

# 2. Move external啃读 files to _legacy/
if (-not (Test-Path '_legacy')) { New-Item -ItemType Directory -Path '_legacy' | Out-Null }

$ext = @(
    'openspace_evolution.py',
    'gstack.zip',
    'gstack-main',
    'verify_gstack.py',
    'test_gstack_import.py',
    'test_gstack_integration.py',
    'verify_hermes.py',
    'test_hermes_integration.py',
    'test_openspace_integration.py',
    'temp_dynamic.txt'
)
foreach ($f in $ext) {
    if (Test-Path $f) {
        Move-Item $f "_legacy/" -Force -ErrorAction SilentlyContinue
        Write-Host "[MOVE] $f"
    }
}
