# Initialize the current PowerShell process for Tauri's Windows MSVC build.
# Invoke directly to keep the environment in the current shell, or pass -Mode
# dev/build to initialize and run Tauri in this same PowerShell process.

param(
    [ValidateSet('dev', 'build')]
    [string]$Mode
)

$vswhereCandidates = @()
if (${env:ProgramFiles(x86)}) {
    $vswhereCandidates += Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
}
if ($env:ProgramFiles) {
    $vswhereCandidates += Join-Path $env:ProgramFiles 'Microsoft Visual Studio\Installer\vswhere.exe'
}
$vswhere = $vswhereCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $vswhere) {
    throw 'Visual Studio Installer / vswhere.exe was not found. Install Visual Studio C++ Build Tools.'
}

$installationPath = (& $vswhere -latest -products '*' `
    -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 `
    -property installationPath | Select-Object -First 1)
if ($LASTEXITCODE -ne 0 -or -not $installationPath) {
    throw 'No Visual Studio installation with the MSVC x64/x86 C++ toolchain was found.'
}
$installationPath = $installationPath.Trim()

$vcvars = Join-Path $installationPath 'VC\Auxiliary\Build\vcvars64.bat'
if (-not (Test-Path -LiteralPath $vcvars)) {
    throw "MSVC environment script was not found: $vcvars"
}

$cmdExe = if ($env:ComSpec) { $env:ComSpec } else { 'cmd.exe' }
$command = 'call "{0}" >nul && set' -f $vcvars
$environmentLines = & $cmdExe /d /s /c $command
if ($LASTEXITCODE -ne 0) {
    throw 'vcvars64.bat failed to initialize the MSVC environment.'
}

foreach ($line in $environmentLines) {
    $separator = $line.IndexOf('=')
    if ($separator -le 0) { continue }
    $name = $line.Substring(0, $separator)
    $value = $line.Substring($separator + 1)
    if ($name -match '^[A-Za-z_][A-Za-z0-9_()]*$') {
        [Environment]::SetEnvironmentVariable($name, $value, 'Process')
    }
}

$env:PATH = "$env:USERPROFILE\.cargo\bin;$env:PATH"
if (-not (Get-Command cl.exe -ErrorAction SilentlyContinue)) {
    throw 'MSVC environment was loaded, but cl.exe is still unavailable.'
}
if (-not (Get-Command link.exe -ErrorAction SilentlyContinue)) {
    throw 'MSVC environment was loaded, but link.exe is still unavailable.'
}

Write-Host '[setup-env] MSVC x64 environment is ready.' -ForegroundColor Green
Write-Host "  Visual Studio: $installationPath" -ForegroundColor Gray
Write-Host "  Compiler     : $((Get-Command cl.exe).Source)" -ForegroundColor Gray

if ($Mode) {
    $tauriCli = Join-Path $PSScriptRoot 'web\node_modules\.bin\tauri.cmd'
    if (-not (Test-Path -LiteralPath $tauriCli)) {
        throw 'Tauri CLI is missing. Run npm install from tauri-prototype\web first.'
    }
    Push-Location $PSScriptRoot
    try {
        & $tauriCli $Mode
        $tauriExitCode = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    exit $tauriExitCode
}

Write-Host 'Run .\web\node_modules\.bin\tauri.cmd dev or tauri.cmd build in this PowerShell session.' -ForegroundColor Cyan
