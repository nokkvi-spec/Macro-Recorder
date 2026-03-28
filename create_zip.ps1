$tempFolder = 'temp_mac_dist'
Remove-Item $tempFolder -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $tempFolder | Out-Null

Copy-Item 'dist\MacroRecorder.exe' $tempFolder
Copy-Item 'feather_icon.ico' $tempFolder
Copy-Item 'Install to Desktop.bat' $tempFolder
Copy-Item 'README.txt' $tempFolder

Compress-Archive -Path $tempFolder -DestinationPath 'dist\MacroRecorder.zip' -Force
Remove-Item $tempFolder -Recurse -Force

Write-Host 'Distribution package created: dist\MacroRecorder.zip'
Write-Host 'Contents: MacroRecorder.exe, feather_icon.ico, Install to Desktop.bat, README.txt'
