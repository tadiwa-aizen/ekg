param(
    [switch]$SkipOekg
)

$ErrorActionPreference = "Stop"
$EkgRoot = $PSScriptRoot
$CliRoot = Join-Path $EkgRoot "ekg-eval-cli"
$EvidenceRoot = Join-Path $EkgRoot "final-frozen-evidence-2026-08-07"
$JenaHome = Join-Path $EkgRoot "apache-jena-5.6.0-full"
$FusekiHome = Join-Path $EkgRoot "apache-jena-fuseki-5.6.0"
$env:PYTHONPATH = $CliRoot

function Invoke-EkgEvaluation {
    param(
        [Parameter(Mandatory)] [string]$InputFolder,
        [Parameter(Mandatory)] [string]$OutputFolder,
        [Parameter(Mandatory)] [int]$Port,
        [string[]]$ExtraArguments = @()
    )

    New-Item -ItemType Directory -Force -Path $OutputFolder | Out-Null
    $arguments = @(
        "-m", "ekg_eval_cli.cli", $InputFolder,
        "--verbose",
        "--output-dir", $OutputFolder,
        "--jena-home", $JenaHome,
        "--fuseki-home", $FusekiHome,
        "--port", $Port
    ) + $ExtraArguments
    & python @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Evaluation failed for $InputFolder with exit code $LASTEXITCODE"
    }
}

Push-Location $CliRoot
try {
    Invoke-EkgEvaluation (Join-Path $EkgRoot "synthetic-event-kg") (Join-Path $EvidenceRoot "dataset1") 3031
    Invoke-EkgEvaluation (Join-Path $EkgRoot "synthetic-event-kg-2") (Join-Path $EvidenceRoot "dataset2") 3032
    Invoke-EkgEvaluation (Join-Path $EkgRoot "synthetic-event-kg-3") (Join-Path $EvidenceRoot "dataset3") 3033

    $chronoRoot = Join-Path $EkgRoot "chronographer-evaluation\nt_utf8"
    Invoke-EkgEvaluation (Join-Path $chronoRoot "eventkg_ng") (Join-Path $EvidenceRoot "chronographer\eventkg_ng") 3034
    Invoke-EkgEvaluation (Join-Path $chronoRoot "search_ng") (Join-Path $EvidenceRoot "chronographer\search_ng") 3035
    Invoke-EkgEvaluation (Join-Path $chronoRoot "generation_ng") (Join-Path $EvidenceRoot "chronographer\generation_ng") 3036

    if (-not $SkipOekg) {
        $oekgWork = Join-Path $EkgRoot "real-oekg-evaluation\large-graph-work-oekg"
        Invoke-EkgEvaluation `
            (Join-Path $EkgRoot "real-oekg-evaluation\oekg-event-layer-clean") `
            (Join-Path $EvidenceRoot "oekg") `
            3030 `
            @(
                "--large-graph-mode",
                "--large-graph-work-dir", $oekgWork,
                "--duckdb-memory-limit", "8GB",
                "--duckdb-temp-dir", (Join-Path $oekgWork "duckdb-temp")
            )
    }
}
finally {
    Pop-Location
}

& python (Join-Path $EkgRoot "build_quality_radar_chart.py")
if ($LASTEXITCODE -ne 0) { throw "Radar generation failed" }
& python (Join-Path $EkgRoot "build_final_evidence_bundle.py")
if ($LASTEXITCODE -ne 0) { throw "Evidence-bundle generation failed" }
