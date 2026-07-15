$candidates = @(
    'G:\最后解析',
    'G:\文献整理_最终',
    'G:\文献整理',
    'G:\literature',
    'G:\literature_final',
    'G:\papers',
    'G:\parsed'
)
foreach ($p in $candidates) {
    if (Test-Path $p) {
        Write-Output ("EXISTS: " + $p)
    }
}
Write-Output "=== G:\ top dirs (decoded) ==="
Get-ChildItem -Path 'G:\' -Directory -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name | Out-File -FilePath 'C:\Users\曾鸿\Desktop\SRS\outputs\literature_mining\_scripts\_tmp_gdirs.txt' -Encoding utf8
