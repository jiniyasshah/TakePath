# Build the installer from an existing PyInstaller onedir bundle.
# Run on Windows after: python -m PyInstaller ... --name TakePath main.py
# Outputs: release/TakePath-windows-x64-setup.exe
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $repoRoot
try {
    if (-not (Test-Path 'dist/TakePath/TakePath.exe')) {
        throw 'Missing dist/TakePath/TakePath.exe. Build the PyInstaller onedir bundle first.'
    }

    $compilerPaths = @(
        (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6/ISCC.exe'),
        (Join-Path $env:ProgramFiles 'Inno Setup 6/ISCC.exe')
    )
    $compiler = $compilerPaths | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $compiler) {
        if ($env:GITHUB_ACTIONS -ne 'true') {
            throw 'Install Inno Setup 6.3+ on Windows before building the setup executable.'
        }
        choco install innosetup --yes --no-progress
        if ($LASTEXITCODE -ne 0) { throw 'Chocolatey could not install Inno Setup.' }
        $compiler = $compilerPaths | Where-Object { Test-Path $_ } | Select-Object -First 1
        if (-not $compiler) { throw 'ISCC.exe was not found after installing Inno Setup.' }
    }

    $version = (python -c "from action_studio import __version__; print(__version__)").Trim()
    if ($LASTEXITCODE -ne 0) { throw 'Could not read TakePath version.' }
    if ($version -notmatch '^(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$') {
        throw "Unsupported installer version: $version"
    }
    $numeric = "$($Matches[1]).$($Matches[2]).$($Matches[3]).0"
    New-Item -ItemType Directory -Force -Path 'release' | Out-Null
    $output = (Resolve-Path 'release').Path

    & $compiler "/DMyAppVersion=$version" "/DMyAppNumericVersion=$numeric" "/O$output" 'installer/takepath.iss'
    if ($LASTEXITCODE -ne 0) { throw 'Inno Setup failed to compile TakePath.' }
    if (-not (Test-Path 'release/TakePath-windows-x64-setup.exe')) {
        throw 'Inno Setup did not create the expected installer artifact.'
    }
    Write-Host "Built release/TakePath-windows-x64-setup.exe for $version"
}
finally {
    Pop-Location
}
