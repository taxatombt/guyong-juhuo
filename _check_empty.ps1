Set-Location 'E:\juhuo'
foreach ($d in @('action_signal','gstack_integration','gstack_virtual_team','hermes_evolution','hermes_integration','templates','test_snapshots')) {
    if (Test-Path $d) {
        $count = (Get-ChildItem $d -Recurse -ErrorAction SilentlyContinue | Measure-Object).Count
        Write-Host "$d : $count items"
    }
}
