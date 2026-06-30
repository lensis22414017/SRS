$vi = (Get-Item 'C:\Users\曾鸿\Desktop\SRS\dist\SRS\SRS.exe').VersionInfo
Write-Output ("CompanyName=" + $vi.CompanyName)
Write-Output ("ProductName=" + $vi.ProductName)
Write-Output ("ProductVersion=" + $vi.ProductVersion)
Write-Output ("LegalCopyright=" + $vi.LegalCopyright)
Write-Output ("FileDescription=" + $vi.FileDescription)
Write-Output ("FileVersion=" + $vi.FileVersion)
