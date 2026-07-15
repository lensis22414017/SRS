$path = Join-Path $env:USERPROFILE 'Desktop\SRS\outputs\literature_mining\manual_extract\hm_op\P11362.csv'
$content = Get-Content $path -Raw -Encoding UTF8
$utf8sig = New-Object System.Text.UTF8Encoding($true)
[System.IO.File]::WriteAllText($path, $content, $utf8sig)
$bytes = [System.IO.File]::ReadAllBytes($path)
$bom = '{0:X2} {1:X2} {2:X2}' -f $bytes[0], $bytes[1], $bytes[2]
Write-Output "BOM: $bom"
$lines = (Get-Content $path).Count
Write-Output "Lines: $lines"
