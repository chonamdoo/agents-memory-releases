# Windows entrypoint: the selected CLI, MCP, E5 and DB run inside WSL2.
# No Windows-native MCP settings, global Docker context or existing WSL profile is changed.
[CmdletBinding()]
param(
    [ValidateSet('claude', 'codex', 'omp')]
    [string[]]$Client = @('claude', 'codex', 'omp'),
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]*$')]
    [string]$Distro = 'Ubuntu-24.04',
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^/[^\r\n]+$')]
    [string]$Project
)

$ErrorActionPreference = 'Stop'
$amVersion = '1.0.8'
$amInstallerSha = '7d24c417c62a603a4cd97602c05df2bbe6569f19c91e3c172535ba77862a3e1d'

function Install-AgentsMemoryWsl {
    if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
        throw 'WSL2 is required. In an Administrator PowerShell run: wsl --install -d Ubuntu-24.04 . Restart if requested, open Ubuntu once, create your Linux user, then rerun this installer.'
    }
    $amKernel = & wsl.exe --distribution $Distro --exec uname -r 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "WSL distribution '$Distro' is not ready. Run: wsl --install -d $Distro . Open it once and create your Linux user, then retry. No memory settings were changed."
    }
    if (($amKernel -join '').ToLowerInvariant() -notlike '*microsoft-standard-wsl2*') {
        throw "WSL2 is required. Run: wsl --set-version $Distro 2 . No memory settings were changed."
    }
    $amArch = & wsl.exe --distribution $Distro --exec uname -m
    if ($LASTEXITCODE -ne 0 -or ($amArch -join '').Trim() -ne 'x86_64') {
        throw 'This release supports Windows x64 with WSL2. Windows ARM64 is not supported yet.'
    }

    # Arguments are positional data, never substituted into shell source. A temporary
    # script avoids multiline command quoting differences in Windows PowerShell 5.1.
    # stdin stays attached to the real terminal for hidden-key input.
    $amScript = @'
set -euo pipefail
umask 077
version=$1
expected=$2
# Windows PowerShell 5.1's native argument binder strips literal double quotes.
# Decode UTF-8 data here instead of passing a raw Linux path through that binder.
project=$(printf '%s' "$3" | base64 --decode)
shift 3
[[ $(id -u) != 0 ]] || { echo 'Open Ubuntu once and create a normal Linux user; do not install as root.' >&2; exit 2; }
[[ -d "$project" && $(realpath "$project") != "$HOME" && $(realpath "$project") != / ]] || { echo 'Choose an existing project folder inside WSL, not your home or the filesystem root.' >&2; exit 2; }
project=$(realpath "$project")
case "$project" in /mnt/*) echo 'Use a project in the WSL Linux filesystem, e.g. /home/your-user/projects/app. /mnt/c projects are not supported by this installer.' >&2; exit 2 ;; esac
command -v curl >/dev/null || { echo 'In Ubuntu run: sudo apt-get update && sudo apt-get install -y curl ca-certificates' >&2; exit 2; }
work=$(mktemp -d /tmp/agents-memory-wsl.XXXXXXXX)
trap 'rm -rf -- "$work"' EXIT
curl --fail --silent --show-error --location --retry 2 --connect-timeout 20 --max-time 120 --proto '=https' --proto-redir '=https' --tlsv1.2 "https://raw.githubusercontent.com/chonamdoo/agents-memory-releases/v${version}/distribution/mcp-local/install.sh" -o "$work/install.sh"
actual=$(sha256sum "$work/install.sh")
[[ ${actual%% *} == "$expected" ]] || { echo 'Installer integrity check failed; no installer was executed.' >&2; exit 65; }
args=(--project "$project")
for client in "$@"; do args+=(--client "$client"); done
bash "$work/install.sh" "${args[@]}"
'@
    Write-Host "Preparing agents-memory $amVersion in WSL2 '$Distro' for $($Client -join ', ')..."
    $amTemporaryScript = Join-Path ([System.IO.Path]::GetTempPath()) ('agents-memory-wsl-' + [guid]::NewGuid().ToString('N') + '.sh')
    try {
        [System.IO.File]::WriteAllText($amTemporaryScript, $amScript.Replace("`r`n", "`n"), (New-Object System.Text.UTF8Encoding($false)))
        $amLinuxScript = & wsl.exe --distribution $Distro --exec wslpath -u $amTemporaryScript
        if ($LASTEXITCODE -ne 0 -or -not ($amLinuxScript -join '').StartsWith('/')) {
            throw 'Could not map the temporary installer into WSL. Check Windows drive mounting in this distribution.'
        }
        $amProjectPayload = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($Project))
        & wsl.exe --distribution $Distro --exec bash -l ($amLinuxScript -join '').Trim() $amVersion $amInstallerSha $amProjectPayload @Client
        if ($LASTEXITCODE -ne 0) {
            throw "WSL installer failed (exit $LASTEXITCODE). Read the preceding stage; existing keys and memory data are preserved."
        }
    }
    finally {
        Remove-Item -LiteralPath $amTemporaryScript -Force -ErrorAction SilentlyContinue
    }
    Write-Host 'Installed. Start Claude, Codex or OMP inside this WSL distribution/project, then reconnect MCP. Use setup_status to check readiness.'
}

Install-AgentsMemoryWsl
