# Pre-imports a repository into PARTHA so the demo starts with data ready.
# The backend must already be running (see start-backend.ps1).
# Usage (from repo root):
#   powershell -ExecutionPolicy Bypass -File scripts/seed-demo.ps1
#   powershell -ExecutionPolicy Bypass -File scripts/seed-demo.ps1 -Url https://github.com/owner/repo
param(
    [string]$Url = "https://github.com/parthrohit22/PARTHA",
    [string]$Api = "http://localhost:8000",
    [string]$Branch = ""
)
$ErrorActionPreference = "Stop"

$body = @{ url = $Url }
if ($Branch -ne "") { $body.branch = $Branch }
$json = $body | ConvertTo-Json

Write-Host "Importing $Url into PARTHA ($Api) ..."
try {
    $resp = Invoke-RestMethod -Method Post -Uri "$Api/repositories/github" -ContentType "application/json" -Body $json
    Write-Host ("Done. Repository id: {0}  ({1} files, {2})" -f $resp.id, $resp.fileCount, $resp.meta.framework)
} catch {
    Write-Error "Import failed. Is the backend running at $Api ? $_"
    exit 1
}
