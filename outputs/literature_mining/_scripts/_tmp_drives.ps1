$stem = '2008_Yuan'
$results = @()
foreach ($d in @('C','E','F','G')) {
    $root = $d + ':\'
    Write-Output ("=== Searching " + $root + " ===")
    Get-ChildItem -Path $root -Recurse -Directory -Filter '*2008_Yuan*' -ErrorAction SilentlyContinue -Depth 4 | Select-Object -First 10 -ExpandProperty FullName
}
