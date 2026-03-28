Write-Host "MacroRecorder Executable Builder" -ForegroundColor Cyan
Write-Host ""

Write-Host "Checking PyInstaller..." -ForegroundColor Yellow
$check = pip show pyinstaller 2>$null
if ($null -eq $check) {
    pip install pyinstaller
}

Write-Host "Building executable with feather icon..." -ForegroundColor Yellow

python -m PyInstaller --onefile --windowed --icon=feather_icon.ico --name MacroRecorder Input_Recorder.py

if (Test-Path ".\dist\MacroRecorder.exe") {
    Write-Host "Success! Building zip file..." -ForegroundColor Green
    
    $temp = ".\dist\temp"
    if (Test-Path $temp) { Remove-Item $temp -Recurse -Force }
    mkdir $temp | Out-Null
    
    Copy-Item ".\dist\MacroRecorder.exe" "$temp\MacroRecorder.exe"
    Copy-Item ".\feather_icon.ico" "$temp\feather_icon.ico"
    
    if (Test-Path ".\dist\MacroRecorder.zip") {
        Remove-Item ".\dist\MacroRecorder.zip" -Force
    }
    
    Compress-Archive -Path "$temp\*" -DestinationPath ".\dist\MacroRecorder.zip" -Force
    Remove-Item $temp -Recurse -Force
    
    Write-Host "DONE!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Your app is ready:" -ForegroundColor Green
    Write-Host "  ./dist/MacroRecorder.zip" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Share this with friends:" -ForegroundColor Green
    Write-Host "  They extract and run MacroRecorder.exe" -ForegroundColor Gray
} else {
    Write-Host "Build failed" -ForegroundColor Red
}
