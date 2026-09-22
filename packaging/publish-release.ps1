param(
    [Parameter(Mandatory = $true)]
    [int]$ReleaseId
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$projectRoot = Split-Path -Parent $PSScriptRoot
$assetPath = Join-Path $projectRoot "dist\OPERO-Setup.exe"
$logPath = Join-Path $projectRoot "dist\publish-release.log"
$responsePath = Join-Path $env:TEMP "opero-release-asset.json"
$publishResponsePath = Join-Path $env:TEMP "opero-release-published.json"

try {
    $credentialLines = @("protocol=https", "host=github.com", "", "") | git credential fill
    $tokenLine = $credentialLines | Where-Object { $_ -like "password=*" } | Select-Object -First 1
    if (-not $tokenLine) { throw "No GitHub credential is available." }
    $token = $tokenLine.Substring("password=".Length)

    $uploadUri = "https://uploads.github.com/repos/channallikrishnasai/The-Opero/releases/$ReleaseId/assets?name=OPERO-Setup.exe"
    & curl.exe --fail --silent --show-error --request POST --header "Authorization: Bearer $token" --header "Accept: application/vnd.github+json" --header "Content-Type: application/octet-stream" --header "X-GitHub-Api-Version: 2022-11-28" --upload-file $assetPath --output $responsePath $uploadUri
    if ($LASTEXITCODE -ne 0) { throw "GitHub asset upload failed with curl exit code $LASTEXITCODE." }

    $asset = Get-Content -Raw $responsePath | ConvertFrom-Json
    if ($asset.name -ne "OPERO-Setup.exe" -or [int64]$asset.size -ne (Get-Item $assetPath).Length) {
        throw "GitHub reported an unexpected release asset."
    }

    $publishUri = "https://api.github.com/repos/channallikrishnasai/The-Opero/releases/$ReleaseId"
    & curl.exe --fail --silent --show-error --request PATCH --header "Authorization: Bearer $token" --header "Accept: application/vnd.github+json" --header "Content-Type: application/json" --header "X-GitHub-Api-Version: 2022-11-28" --data '{"draft":false}' --output $publishResponsePath $publishUri
    if ($LASTEXITCODE -ne 0) { throw "GitHub release publishing failed with curl exit code $LASTEXITCODE." }

    $release = Get-Content -Raw $publishResponsePath | ConvertFrom-Json
    "SUCCESS release_url=$($release.html_url) asset_url=$($asset.browser_download_url) asset_size=$($asset.size)" | Set-Content -LiteralPath $logPath -Encoding utf8
} catch {
    "ERROR $($_.Exception.Message)" | Set-Content -LiteralPath $logPath -Encoding utf8
    exit 1
}
