# Build the Windows installer. Run in PowerShell from the repo root on Windows.
# Needs Inno Setup 6 (choco install innosetup).
$ErrorActionPreference = "Stop"
$version = (Get-Content VERSION).Trim()
python -m pip install -r requirements.txt pyinstaller
pyinstaller packaging/hsc_companion.spec --noconfirm --clean
$p = Start-Process -FilePath "dist\HSC Companion\HSC Companion.exe" -ArgumentList "--self-test" -Wait -PassThru
if ($p.ExitCode -ne 0) { throw "Self-test failed ($($p.ExitCode))" }
& "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" "/DMyAppVersion=$version" packaging\windows\installer.iss
Write-Host "Built dist\HSC-Companion-$version-Windows-Setup.exe"
