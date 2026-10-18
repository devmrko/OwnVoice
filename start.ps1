param([switch]$SetupOnly, [switch]$Cuda, [int]$Port = 8765)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$env:PYTHONUTF8 = '1'
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Host 'Install FFmpeg: winget install --id Gyan.FFmpeg --exact'
    Write-Host 'Open a new terminal after installation, then run start.cmd again.'
    exit 1
}
& powershell -NoProfile -ExecutionPolicy Bypass -File "$PSScriptRoot\uvw.ps1" sync --locked --extra tts --python 3.12
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
# PyPI Windows wheels can be CPU-only. Select a driver-compatible CUDA wheel explicitly.
if ($Cuda) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File "$PSScriptRoot\uvw.ps1" pip install --python '.venv\Scripts\python.exe' --torch-backend=auto --upgrade torch torchaudio
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $env:OWNVOICE_DEVICE = 'cuda'
    & '.\.venv\Scripts\python.exe' -c 'import torch; assert torch.cuda.is_available(), "CUDA unavailable: check the NVIDIA driver and PyTorch wheel"'
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
if ($SetupOnly) { exit 0 }
& '.\.venv\Scripts\ownvoice.exe' start --port $Port
exit $LASTEXITCODE
