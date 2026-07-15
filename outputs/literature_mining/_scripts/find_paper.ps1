$dir = Get-ChildItem 'G:\最后解析' -Directory | Where-Object { $_.Name -like '*2005_Hu*' }
foreach ($d in $dir) {
    Write-Output $d.FullName
    $parsed = Join-Path $d.FullName 'parsed\paper.md'
    if (Test-Path $parsed) {
        Write-Output "  paper.md found"
    } else {
        Write-Output "  paper.md NOT found, listing contents:"
        Get-ChildItem $d.FullName -Recurse | ForEach-Object { Write-Output "    $($_.FullName)" }
    }
}
