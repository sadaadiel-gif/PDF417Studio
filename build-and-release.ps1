param(
    [string]$CommitMessage = "Auto-build: updated app",
    [string]$Version = "1.0.1"
)

Write-Host "Updating version.txt to $Version ..." -ForegroundColor Cyan
$Version | Out-File -FilePath "version.txt" -Encoding utf8

Write-Host "Building executable with PyInstaller ..." -ForegroundColor Cyan
python -m PyInstaller PDF417Studio.spec --clean --noconfirm

if ($LASTEXITCODE -ne 0) {
    Write-Host "Build failed. Exiting." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "Copying to Desktop ..." -ForegroundColor Cyan
$DesktopPath = [Environment]::GetFolderPath("Desktop")
Copy-Item "dist\PDF417Studio.exe" "$DesktopPath\PDF417Studio.exe" -Force

Write-Host "Staging changes for Git ..." -ForegroundColor Cyan
git add .
git add -f dist/PDF417Studio.exe

Write-Host "Committing with message: '$CommitMessage'" -ForegroundColor Cyan
git commit -m $CommitMessage

Write-Host "Pushing to origin main ..." -ForegroundColor Cyan
git push origin main

Write-Host "Done! The new version is committed and pushed." -ForegroundColor Green
Write-Host "Next: create a GitHub Release with tag v$Version and attach the .exe from dist/." -ForegroundColor Yellow