# Project-local uv/Python bootstrap; does not modify the machine's PATH.
$ErrorActionPreference = 'Stop'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $PSScriptRoot '.tools\python'
$env:UV_PYTHON_DOWNLOADS = 'automatic'
$env:UV_PYTHON_BIN_DIR = Join-Path $PSScriptRoot '.tools\bin'
if (-not $env:UV_CACHE_DIR) { $env:UV_CACHE_DIR = Join-Path $PSScriptRoot '.tools\cache' }
$env:PYTHONUTF8 = '1'
$ownvoiceUv = Join-Path $PSScriptRoot '.tools\uv\uv.exe'
if (-not (Test-Path $ownvoiceUv)) {
    $env:UV_UNMANAGED_INSTALL = Join-Path $PSScriptRoot '.tools\uv'
    $env:UV_NO_MODIFY_PATH = '1'
    $ownvoiceInstaller = Join-Path ([IO.Path]::GetTempPath()) ([IO.Path]::GetRandomFileName() + '.ps1')
    try {
        Invoke-WebRequest -Uri 'https://astral.sh/uv/0.10.6/install.ps1' -OutFile $ownvoiceInstaller
        & $ownvoiceInstaller
        if (-not (Test-Path $ownvoiceUv)) { throw 'uv installation failed.' }
    } finally { Remove-Item $ownvoiceInstaller -ErrorAction SilentlyContinue }
}
& $ownvoiceUv @args
exit $LASTEXITCODE
