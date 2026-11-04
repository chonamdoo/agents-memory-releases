# Environment evidence only; never claims agents-memory is installed or verified.
$ErrorActionPreference = 'Stop'
$amOs = Get-CimInstance Win32_OperatingSystem
$amEvidence = [ordered]@{
    purpose = 'Windows VM test-host inventory only'
    product_verified = $false
    native_windows_artifact_available = $false
    os = $amOs.Caption
    version = $amOs.Version
    build = $amOs.BuildNumber
    architecture = $amOs.OSArchitecture
    powershell = $PSVersionTable.PSVersion.ToString()
    collected_at = [DateTime]::UtcNow.ToString('o')
}
$amDirectory = Join-Path $env:USERPROFILE 'Desktop\agents-memory-test'
$null = New-Item -ItemType Directory -Path $amDirectory -Force
$amEvidence | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $amDirectory 'HOST.json') -Encoding UTF8
