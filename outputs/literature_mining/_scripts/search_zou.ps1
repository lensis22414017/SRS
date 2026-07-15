$dirs = Get-ChildItem 'G:\' -Directory
foreach ($d in $dirs) {
    $matches = Get-ChildItem $d.FullName -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -like '*Zouetal*' }
    foreach ($m in $matches) {
        Write-Output $m.FullName
    }
}
