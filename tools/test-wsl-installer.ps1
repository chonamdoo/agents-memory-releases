# Run with pwsh. The real PowerShell parser runs on Linux; wsl.exe is a deliberate
# process-boundary double. This does not establish physical Windows/WSL execution.
$ErrorActionPreference = 'Stop'
$amTarget = Join-Path $PSScriptRoot '../distribution/mcp-local/install-wsl.ps1'
$amTokens = $null
$amErrors = $null
$null = [System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path $amTarget), [ref]$amTokens, [ref]$amErrors)
if ($amErrors.Count -ne 0) { throw ($amErrors | Out-String) }

$global:amTestKernel = '6.6.87.2-microsoft-standard-WSL2'
$global:amTestArch = 'x86_64'
$global:amTestMissing = $false
$global:amTestInstallerFailure = $false
$global:amTestRuns = @()
function wsl.exe {
    $global:amTestCalls++
    $global:LASTEXITCODE = 0
    if ($global:amTestMissing) { $global:LASTEXITCODE = 1; return }
    switch ($args[3]) {
        'uname' {
            if ($args[4] -eq '-r') { return $global:amTestKernel }
            if ($args[4] -eq '-m') { return $global:amTestArch }
            throw 'Unexpected uname invocation'
        }
        'wslpath' { return $args[5] }
        'bash' {
            if ($args[4] -ne '-l') { throw 'Login shell expected for the installed CLI PATH' }
            $amPath = $args[5]
            if (-not (Test-Path -LiteralPath $amPath)) { throw 'Temporary script missing' }
            $amSource = [System.IO.File]::ReadAllText($amPath)
            if ($amSource.Contains($global:amTestProject)) { throw 'Project was interpolated into shell code' }
            $global:amTestRuns += ,@($args)
            $global:amTestTemp = $amPath
            if ($global:amTestInstallerFailure) { $global:LASTEXITCODE = 65 }
            return
        }
        default { throw ('Unexpected WSL invocation: ' + ($args -join ' ')) }
    }
}
function Assert-Refused([string]$Expected) {
    $amBefore = $global:amTestRuns.Count
    try {
        & $amTarget -Client codex -Project '/home/test/project'
        throw 'Installer unexpectedly succeeded'
    }
    catch {
        if ($_.Exception.Message -notlike "*$Expected*") { throw }
    }
    if ($global:amTestRuns.Count -ne $amBefore) { throw 'Unsupported environment executed the installer' }
}

$global:amTestCalls = 0
$global:amTestProject = '/home/test/project with space ''quotes'' $(touch SHOULD_NOT_RUN) 한글'
& $amTarget -Client claude,codex,omp -Distro 'Ubuntu-24.04' -Project $global:amTestProject
if ($global:amTestRuns.Count -ne 1) { throw 'Expected one multi-client installation' }
$amInvocation = $global:amTestRuns[0]
if ($amInvocation[8] -ne $global:amTestProject -or ($amInvocation[9..11] -join ',') -ne 'claude,codex,omp') {
    throw ('Argument boundaries were not preserved: ' + ($amInvocation | ConvertTo-Json -Compress))
}
if (Test-Path -LiteralPath $global:amTestTemp) { throw 'Temporary script was not removed' }

$global:amTestMissing = $true
Assert-Refused 'not ready'
$global:amTestMissing = $false
$global:amTestKernel = '4.4.0-19041-Microsoft'
Assert-Refused 'WSL2 is required'
$global:amTestKernel = '6.6.87.2-microsoft-standard-WSL2'
$global:amTestArch = 'aarch64'
Assert-Refused 'ARM64 is not supported'
$global:amTestArch = 'x86_64'
$global:amTestInstallerFailure = $true
try {
    & $amTarget -Client omp -Project '/home/test/project'
    throw 'Failed child installer was reported as successful'
}
catch {
    if ($_.Exception.Message -notlike '*exit 65*') { throw }
}
if (Test-Path -LiteralPath $global:amTestTemp) { throw 'Failed installation leaked its temporary script' }
Write-Output 'PASS: PowerShell syntax, 3 client arguments, path quoting, WSL1/ARM64/missing distro refusal, child failure and cleanup (mock WSL boundary).'
