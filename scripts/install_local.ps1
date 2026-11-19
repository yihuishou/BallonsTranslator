$ErrorActionPreference = "Stop"
$PythonVersion = "3.12.10"

# Local-source variant of install.ps1.
# It only re-creates the bundled Python runtime for an existing checkout.
# No source code is ever downloaded; the checkout must already contain the app.

$ProjectRoot = ""

if ($PSScriptRoot) {
    $ParentDir = Split-Path $PSScriptRoot -Parent
    if (Test-Path (Join-Path $ParentDir "ballontranslator")) {
        $ProjectRoot = $ParentDir
    }
}

if (-not $ProjectRoot) {
    throw "install_local.ps1 must be run from inside a BallonsTranslator checkout (scripts/ next to ballontranslator/). No source code will be downloaded."
}

Write-Host "=== BallonsTranslator Local-Only Installer ==="
Write-Host "Using local source at $ProjectRoot ..."

$PyLibsDir = Join-Path $ProjectRoot "ballontrans_pylibs_win"
$BuildDir = Join-Path $ProjectRoot "install_temp"

New-Item -ItemType Directory -Force -Path $BuildDir | Out-Null

if (Test-Path $PyLibsDir) {
    Write-Host "Moving existing ballontrans_pylibs_win to Recycle Bin..."
    Add-Type -AssemblyName Microsoft.VisualBasic
    [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory(
        $PyLibsDir,
        [Microsoft.VisualBasic.FileIO.UIOption]::OnlyErrorDialogs,
        [Microsoft.VisualBasic.FileIO.RecycleOption]::SendToRecycleBin
    )
}
New-Item -ItemType Directory -Force -Path $PyLibsDir | Out-Null

# Step 1: Download and Extract Python Embeddable
$PythonZipName = "python-$PythonVersion-embed-amd64.zip"
$PythonUrl = "https://www.python.org/ftp/python/$PythonVersion/$PythonZipName"
$PythonZipPath = Join-Path $BuildDir $PythonZipName

Write-Host "Downloading Python $PythonVersion embeddable..."
Invoke-WebRequest -Uri $PythonUrl -OutFile $PythonZipPath

Write-Host "Extracting Python..."
Expand-Archive -Path $PythonZipPath -DestinationPath $PyLibsDir
Remove-Item $PythonZipPath

# Step 2: Modify python._pth to enable site-packages and project root path
$VersionParts = $PythonVersion.Split('.')
$MajorMinor = $VersionParts[0] + $VersionParts[1]
$PthFile = Join-Path $PyLibsDir "python$MajorMinor._pth"

if (-not (Test-Path $PthFile)) {
    throw "Could not find path file: $PthFile"
}

Write-Host "Modifying $PthFile to enable site-packages and project root path..."
$PthContent = Get-Content -Path $PthFile
$UpdatedContent = @()
foreach ($line in $PthContent) {
    if ($line.Trim() -eq "#import site") {
        $UpdatedContent += "import site"
    } elseif ($line.Trim() -eq ".") {
        $UpdatedContent += "."
        $UpdatedContent += ".."
    } else {
        $UpdatedContent += $line
    }
}
$UpdatedContent | Set-Content -Path $PthFile

# Step 3: Install pip
Write-Host "Downloading get-pip.py..."
$GetPipUrl = "https://bootstrap.pypa.io/get-pip.py"
$GetPipPath = Join-Path $BuildDir "get-pip.py"
Invoke-WebRequest -Uri $GetPipUrl -OutFile $GetPipPath

Write-Host "Installing pip..."
$PythonExe = Join-Path $PyLibsDir "python.exe"
Start-Process -FilePath $PythonExe -ArgumentList "$GetPipPath --no-warn-script-location" -Wait -NoNewWindow
Remove-Item $GetPipPath

# Step 4: Download and extract uv
$UvUrl = "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip"
$UvZipPath = Join-Path $BuildDir "uv.zip"

Write-Host "Downloading uv..."
Invoke-WebRequest -Uri $UvUrl -OutFile $UvZipPath

Write-Host "Extracting uv..."
$UvTempDir = Join-Path $BuildDir "uv_temp"
Expand-Archive -Path $UvZipPath -DestinationPath $UvTempDir
Remove-Item $UvZipPath

$UvExe = Get-ChildItem -Path $UvTempDir -Filter "uv.exe" -Recurse | Select-Object -First 1
if (-not $UvExe) {
    throw "Could not find uv.exe in the downloaded archive"
}
Copy-Item -Path $UvExe.FullName -Destination $PyLibsDir -Force
Remove-Item -Recurse -Force $UvTempDir

# Clean up temp folder
Remove-Item -Recurse -Force $BuildDir

Write-Host "=== Installation Completed Successfully! ==="
Write-Host "You can now run launch_win.bat to start BallonsTranslator."

# Step 5: Automatically launch launch_win.bat
$LaunchBat = Join-Path $ProjectRoot "launch_win.bat"
if (Test-Path $LaunchBat) {
    Write-Host "Launching BallonsTranslator..."
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c `"$LaunchBat`"" -WorkingDirectory $ProjectRoot
}
