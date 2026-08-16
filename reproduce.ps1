[CmdletBinding()]
param(
    [ValidateSet("Quick", "Verify", "Full")]
    [string]$Mode = "Quick",
    [string]$OutputRoot,
    [string]$OekgArchive,
    [int]$PortBase = 3041,
    [switch]$SkipEnvironmentSetup,
    [switch]$ForceLowDisk
)

$ErrorActionPreference = "Stop"
$EkgRoot = $PSScriptRoot
$RepositoryRoot = Split-Path -Parent $EkgRoot
$CliRoot = Join-Path $EkgRoot "ekg-eval-cli"
$FrozenRoot = Join-Path $EkgRoot "final-frozen-evidence-2026-08-07"
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
if (-not $OutputRoot) {
    $OutputRoot = Join-Path $EkgRoot "reproduction-output\$Timestamp-$($Mode.ToLowerInvariant())"
}
$OutputRoot = [System.IO.Path]::GetFullPath($OutputRoot)
$ReportRoot = Join-Path $OutputRoot "report"
New-Item -ItemType Directory -Force -Path $OutputRoot, $ReportRoot | Out-Null

function Write-Step {
    param([string]$Message)
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory)] [string]$Executable,
        [Parameter(Mandatory)] [string[]]$Arguments,
        [string]$WorkingDirectory = $EkgRoot
    )
    Push-Location $WorkingDirectory
    try {
        & $Executable @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "$Executable failed with exit code $LASTEXITCODE"
        }
    }
    finally {
        Pop-Location
    }
}

function Get-FreeDiskGB {
    param([string]$Path)
    $root = [System.IO.Path]::GetPathRoot([System.IO.Path]::GetFullPath($Path))
    $drive = New-Object System.IO.DriveInfo($root)
    return [math]::Round($drive.AvailableFreeSpace / 1GB, 2)
}

function Ensure-ArchiveTool {
    param(
        [Parameter(Mandatory)] [string[]]$CandidateDirectories,
        [Parameter(Mandatory)] [string]$ArchiveName,
        [Parameter(Mandatory)] [string]$DownloadUrl,
        [Parameter(Mandatory)] [string]$ExpectedSha512,
        [Parameter(Mandatory)] [string]$RequiredRelativePath
    )
    foreach ($candidate in $CandidateDirectories) {
        $required = Join-Path $candidate $RequiredRelativePath
        if ((Test-Path -LiteralPath $candidate -PathType Container) -and
            (Test-Path -LiteralPath $required)) {
            return $candidate
        }
    }
    $cache = Join-Path $EkgRoot ".reproduction-cache\tools"
    New-Item -ItemType Directory -Force -Path $cache | Out-Null
    $archive = Join-Path $cache $ArchiveName
    Write-Step "Downloading $ArchiveName from the Apache archive"
    Invoke-WebRequest -UseBasicParsing -Uri $DownloadUrl -OutFile $archive
    $actual = (Get-FileHash -Algorithm SHA512 -LiteralPath $archive).Hash.ToLowerInvariant()
    if ($actual -ne $ExpectedSha512.ToLowerInvariant()) {
        throw "SHA-512 mismatch for $ArchiveName. Expected $ExpectedSha512, found $actual"
    }
    Expand-Archive -LiteralPath $archive -DestinationPath $EkgRoot -Force
    foreach ($candidate in $CandidateDirectories) {
        $required = Join-Path $candidate $RequiredRelativePath
        if ((Test-Path -LiteralPath $candidate -PathType Container) -and
            (Test-Path -LiteralPath $required)) {
            return $candidate
        }
    }
    throw "The verified archive did not create an expected tool directory"
}

function Ensure-PythonEnvironment {
    $venv = Join-Path $EkgRoot ".venv-reproduction"
    $python = Join-Path $venv "Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
        Write-Step "Creating isolated Python environment"
        $null = Invoke-Checked "python" @("-m", "venv", $venv)
    }
    $lock = Join-Path $CliRoot "requirements-lock.txt"
    $reproductionLock = Join-Path $EkgRoot "requirements-reproduction.txt"
    $lockHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $lock).Hash + ":" + `
        (Get-FileHash -Algorithm SHA256 -LiteralPath $reproductionLock).Hash
    $marker = Join-Path $venv ".requirements.sha256"
    $installedHash = if (Test-Path -LiteralPath $marker) {
        (Get-Content -Raw -LiteralPath $marker).Trim()
    } else { "" }
    if ($installedHash -ne $lockHash) {
        Write-Step "Installing the locked evaluator environment"
        $null = Invoke-Checked $python @("-m", "pip", "install", "--disable-pip-version-check", "-r", $lock, "-r", $reproductionLock) $CliRoot
        $null = Invoke-Checked $python @("-m", "pip", "install", "--disable-pip-version-check", "-e", ".", "--no-deps") $CliRoot
        Set-Content -LiteralPath $marker -Value $lockHash -Encoding ascii
    }
    # Setuptools may leave transient metadata in the source tree. It is not
    # evaluator source and must not change the source snapshot recorded by a run.
    $eggInfo = Join-Path $CliRoot "ekg_eval_cli.egg-info"
    if (Test-Path -LiteralPath $eggInfo -PathType Container) {
        $resolvedEggInfo = [System.IO.Path]::GetFullPath($eggInfo)
        $resolvedCliRoot = [System.IO.Path]::GetFullPath($CliRoot)
        if (-not $resolvedEggInfo.StartsWith($resolvedCliRoot + [System.IO.Path]::DirectorySeparatorChar)) {
            throw "Refusing to remove packaging metadata outside the CLI source folder"
        }
        Remove-Item -LiteralPath $resolvedEggInfo -Recurse -Force
    }
    return $python
}

function Copy-NTriplesInput {
    param([string]$Source, [string]$Destination)
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    $files = Get-ChildItem -LiteralPath $Source -Filter "*.nt" -File
    if (-not $files) {
        throw "No N-Triples files found in $Source"
    }
    foreach ($file in $files) {
        Copy-Item -LiteralPath $file.FullName -Destination (Join-Path $Destination $file.Name) -Force
    }
}

function Invoke-EkgEvaluation {
    param(
        [Parameter(Mandatory)] [string]$Python,
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
        "--jena-home", $script:JenaHome,
        "--fuseki-home", $script:FusekiHome,
        "--port", "$Port"
    ) + $ExtraArguments
    Invoke-Checked $Python $arguments $CliRoot
}

function Prepare-OekgInput {
    param([string]$Python)
    $prepared = Join-Path $EkgRoot "real-oekg-evaluation\oekg-event-layer-clean"
    if (Test-Path -LiteralPath (Join-Path $prepared "events.nt") -PathType Leaf) {
        Write-Host "Using the existing cleaned OEKG event layer: $prepared"
        return $prepared
    }

    $free = Get-FreeDiskGB $OutputRoot
    if ($free -lt 80 -and -not $ForceLowDisk) {
        throw "Full OEKG preparation needs at least 80GB free; only ${free}GB is available. Use -ForceLowDisk only if equivalent prepared files or external storage are available."
    }
    $raw = Join-Path $EkgRoot ".reproduction-cache\oekg"
    New-Item -ItemType Directory -Force -Path $raw | Out-Null
    if (-not $OekgArchive) {
        $OekgArchive = Join-Path $raw "event_kg.tar.gz"
    }
    if (-not (Test-Path -LiteralPath $OekgArchive -PathType Leaf)) {
        Write-Step "Downloading OEKG V2.0 event_kg.tar.gz from Zenodo"
        Invoke-WebRequest -UseBasicParsing `
            -Uri "https://zenodo.org/api/records/4503163/files/event_kg/event_kg.tar.gz/content" `
            -OutFile $OekgArchive
    }
    $expected = "392d6eeb69d074130166fb626d4db7279c2b16b45be50213480de1864ce4aa4a"
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $OekgArchive).Hash.ToLowerInvariant()
    if ($actual -ne $expected) {
        throw "OEKG archive SHA-256 mismatch. Expected $expected, found $actual"
    }

    $extractRoot = Join-Path $OutputRoot "oekg-source"
    New-Item -ItemType Directory -Force -Path $extractRoot | Out-Null
    Write-Step "Extracting the verified OEKG archive"
    Invoke-Checked "tar" @("-xzf", $OekgArchive, "-C", $extractRoot)
    $eventsFile = Get-ChildItem -LiteralPath $extractRoot -Recurse -Filter "events.nt" -File |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.DirectoryName "relations_events_literals.nt") } |
        Select-Object -First 1
    if (-not $eventsFile) {
        throw "Could not locate the OEKG event-layer directory after extraction"
    }
    $clean = Join-Path $OutputRoot "inputs\oekg-event-layer-clean"
    Write-Step "Applying the documented parse-recovery cleaning"
    Invoke-Checked $Python @(
        (Join-Path $EkgRoot "real-oekg-evaluation\clean_oekg_literals.py"),
        "--source-dir", $eventsFile.DirectoryName,
        "--clean-dir", $clean
    )
    return $clean
}

if ($Mode -eq "Verify") {
    Write-Step "Verifying the frozen evidence bundle without rerunning evaluations"
    Invoke-Checked "python" @(
        (Join-Path $EkgRoot "verify_reproduction.py"),
        "--output-dir", $ReportRoot
    )
    Write-Host "`nVerification complete: $(Join-Path $ReportRoot 'reproduction-report.html')" -ForegroundColor Green
    exit 0
}

if (-not (Get-Command java -ErrorAction SilentlyContinue)) {
    throw "Java is required for Apache Jena and Fuseki but was not found on PATH"
}

if ($SkipEnvironmentSetup) {
    $Python = "python"
} else {
    $Python = Ensure-PythonEnvironment
}

$script:JenaHome = Ensure-ArchiveTool `
    @((Join-Path $EkgRoot "apache-jena-5.6.0-full"), (Join-Path $EkgRoot "apache-jena-5.6.0")) `
    "apache-jena-5.6.0.zip" `
    "https://archive.apache.org/dist/jena/binaries/apache-jena-5.6.0.zip" `
    "62eee6ad2a27647bca15bc7fd8a49bb9f105b4969ccec2b2550563da37a1e51df4b90bca59fcb50925b0b23161365959e4ca3c62008aaf6f998ed6854d8bf8a6" `
    "lib"
$script:FusekiHome = Ensure-ArchiveTool `
    @((Join-Path $EkgRoot "apache-jena-fuseki-5.6.0")) `
    "apache-jena-fuseki-5.6.0.zip" `
    "https://archive.apache.org/dist/jena/binaries/apache-jena-fuseki-5.6.0.zip" `
    "19bfa2eafc6d349f6d98129c587e545656c15659d116c727770f1d65092938767e7b0ed3976355f47ac753560b37fc4872e6e4e53437c3cc2330edef3d56cf46" `
    "fuseki-server.jar"

Write-Step "Running the 24-test regression suite"
$testLog = Join-Path $OutputRoot "test-suite.log"
Push-Location $CliRoot
try {
    & $Python -m compileall -q ekg_eval_cli tests
    if ($LASTEXITCODE -ne 0) { throw "Python compilation failed" }
    $testOutput = @(& $Python -m pytest -q 2>&1)
    Write-Host ($testOutput -join "`n")
    $testOutput | Out-File -FilePath $testLog -Encoding utf8
    if ($LASTEXITCODE -ne 0) { throw "Regression tests failed" }
}
finally {
    Pop-Location
}

Write-Step "Generating fresh deterministic D1-D3 inputs"
$inputRoot = Join-Path $OutputRoot "inputs"
Invoke-Checked $Python @(
    (Join-Path $EkgRoot "create_tiered_synthetic_eventkgs.py"),
    "--output-root", $inputRoot
)

$resultsRoot = Join-Path $OutputRoot "results"
Write-Step "Evaluating D1 high-quality profile"
Invoke-EkgEvaluation $Python (Join-Path $inputRoot "synthetic-event-kg") (Join-Path $resultsRoot "dataset1") $PortBase
Write-Step "Evaluating D2 mixed-quality profile"
Invoke-EkgEvaluation $Python (Join-Path $inputRoot "synthetic-event-kg-2") (Join-Path $resultsRoot "dataset2") ($PortBase + 1)
Write-Step "Evaluating D3 low-quality profile"
Invoke-EkgEvaluation $Python (Join-Path $inputRoot "synthetic-event-kg-3") (Join-Path $resultsRoot "dataset3") ($PortBase + 2)

$verifyArguments = @(
    (Join-Path $EkgRoot "verify_reproduction.py"),
    "--output-dir", $ReportRoot,
    "--results-root", $resultsRoot,
    "--test-log", $testLog
)

if ($Mode -eq "Full") {
    Write-Step "Preparing and evaluating the three ChronoGrapher RDF artefacts"
    $chronoSource = Join-Path $EkgRoot "chronographer-evaluation\nt_utf8"
    $chronoInput = Join-Path $inputRoot "chronographer"
    foreach ($name in @("eventkg_ng", "search_ng", "generation_ng")) {
        Copy-NTriplesInput (Join-Path $chronoSource $name) (Join-Path $chronoInput $name)
    }
    Invoke-EkgEvaluation $Python (Join-Path $chronoInput "eventkg_ng") (Join-Path $resultsRoot "chronographer\eventkg_ng") ($PortBase + 3)
    Invoke-EkgEvaluation $Python (Join-Path $chronoInput "search_ng") (Join-Path $resultsRoot "chronographer\search_ng") ($PortBase + 4)
    Invoke-EkgEvaluation $Python (Join-Path $chronoInput "generation_ng") (Join-Path $resultsRoot "chronographer\generation_ng") ($PortBase + 5)

    $oekgInput = Prepare-OekgInput $Python
    $oekgWork = Join-Path $OutputRoot "work\oekg"
    Write-Step "Evaluating the complete cleaned OEKG event layer"
    Invoke-EkgEvaluation $Python $oekgInput (Join-Path $resultsRoot "oekg") ($PortBase + 6) @(
        "--large-graph-mode",
        "--large-graph-work-dir", $oekgWork,
        "--duckdb-memory-limit", "8GB",
        "--duckdb-temp-dir", (Join-Path $oekgWork "duckdb-temp")
    )
    $verifyArguments += @("--include-chrono", "--include-oekg")
}

Write-Step "Comparing all reproduced core outputs with the frozen evidence"
Invoke-Checked $Python $verifyArguments
Write-Host "`nReproduction complete." -ForegroundColor Green
Write-Host "HTML report: $(Join-Path $ReportRoot 'reproduction-report.html')"
Write-Host "Machine-readable verification: $(Join-Path $ReportRoot 'verification.json')"
