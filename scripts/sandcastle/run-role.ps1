param(
    [Parameter(Mandatory = $false)]
    [string]$Role = $env:SOFTWARE_FACTORY_ROLE
)

if ([string]::IsNullOrWhiteSpace($Role)) {
    throw "Usage: ./scripts/sandcastle/run-role.ps1 -Role <planner|developer|reviewer|merger>"
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..\..")
Set-Location $repoRoot
$env:SOFTWARE_FACTORY_ROLE = $Role

npx --yes --package @ai-hero/sandcastle@latest --package tsx@latest tsx .sandcastle/main.ts $Role
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

