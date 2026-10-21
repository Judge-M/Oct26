param(
    [Parameter(Mandatory = $true)]
    [string]$IntroVideo,

    [Parameter(Mandatory = $true)]
    [string]$OutroVideo,

    [string]$SourcePdf = (Join-Path $PSScriptRoot "..\docs\event-day-deck\event-day-deck.pdf"),

    [string]$OutputPptx = (Join-Path $PSScriptRoot "..\docs\event-day-deck\event-day-deck.pptx"),

    [string]$BuildDirectory = (Join-Path $PSScriptRoot "..\work\event-day-deck-build")
)

$ErrorActionPreference = "Stop"

function Resolve-RequiredFile {
    param([string]$Path, [string]$Label)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Label not found: $Path"
    }

    return (Resolve-Path -LiteralPath $Path).Path
}

function Get-PdfRenderer {
    $command = Get-Command pdftoppm -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $bundled = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin\pdftoppm.exe"
    if (Test-Path -LiteralPath $bundled -PathType Leaf) {
        return $bundled
    }

    throw "pdftoppm was not found. Install Poppler or run this from the Codex desktop workspace runtime."
}

$sourcePdfPath = Resolve-RequiredFile -Path $SourcePdf -Label "Source PDF"
$introVideoPath = Resolve-RequiredFile -Path $IntroVideo -Label "Intro video"
$outroVideoPath = Resolve-RequiredFile -Path $OutroVideo -Label "Outro video"
$outputPath = [System.IO.Path]::GetFullPath($OutputPptx)
$buildPath = [System.IO.Path]::GetFullPath($BuildDirectory)
$slideImageDirectory = Join-Path $buildPath "slides"
$pdftoppm = Get-PdfRenderer

New-Item -ItemType Directory -Path $slideImageDirectory -Force | Out-Null
New-Item -ItemType Directory -Path ([System.IO.Path]::GetDirectoryName($outputPath)) -Force | Out-Null

Get-ChildItem -LiteralPath $slideImageDirectory -Filter "slide-*.png" -File -ErrorAction SilentlyContinue |
    Remove-Item -Force

& $pdftoppm -png -r 144 $sourcePdfPath (Join-Path $slideImageDirectory "slide")
if ($LASTEXITCODE -ne 0) {
    throw "PDF rendering failed with exit code $LASTEXITCODE"
}

$slideImages = @(Get-ChildItem -LiteralPath $slideImageDirectory -Filter "slide-*.png" -File | Sort-Object Name)
if ($slideImages.Count -ne 13) {
    throw "Expected 13 rendered source slides, found $($slideImages.Count)."
}

$powerPoint = $null
$presentation = $null

try {
    $powerPoint = New-Object -ComObject PowerPoint.Application
    $powerPoint.Visible = -1
    $presentation = $powerPoint.Presentations.Add()
    $presentation.PageSetup.SlideWidth = 960
    $presentation.PageSetup.SlideHeight = 540

    $blankLayout = 12
    $msoFalse = 0
    $msoTrue = -1

    function Add-ImageSlide {
        param([string]$ImagePath)

        $slide = $presentation.Slides.Add($presentation.Slides.Count + 1, $blankLayout)
        $null = $slide.Shapes.AddPicture($ImagePath, $msoFalse, $msoTrue, 0, 0, 960, 540)
    }

    function Add-VideoSlide {
        param([string]$VideoPath, [string]$ShapeName)

        $slide = $presentation.Slides.Add($presentation.Slides.Count + 1, $blankLayout)
        $background = $slide.Shapes.AddShape(1, 0, 0, 960, 540)
        $background.Fill.Solid()
        $background.Fill.ForeColor.RGB = [System.Drawing.ColorTranslator]::ToOle(
            [System.Drawing.Color]::FromArgb(22, 33, 30)
        )
        $background.Line.Visible = $msoFalse

        # The accepted briefs are square. Keep their native aspect ratio and
        # center them on the 16:9 deck instead of stretching the speaker.
        $media = $slide.Shapes.AddMediaObject2($VideoPath, $msoFalse, $msoTrue, 210, 0, 540, 540)
        $media.Name = $ShapeName
        $media.AlternativeText = "$ShapeName. Embedded MP4 for room-wide facilitator playback."
        $media.AnimationSettings.PlaySettings.PlayOnEntry = $msoTrue
        $media.AnimationSettings.PlaySettings.HideWhileNotPlaying = $msoFalse
    }

    Add-ImageSlide -ImagePath $slideImages[0].FullName
    Add-VideoSlide -VideoPath $introVideoPath -ShapeName "Intro Brief"

    foreach ($image in $slideImages[1..12]) {
        Add-ImageSlide -ImagePath $image.FullName
    }

    Add-VideoSlide -VideoPath $outroVideoPath -ShapeName "Outro Brief"

    if (Test-Path -LiteralPath $outputPath) {
        Remove-Item -LiteralPath $outputPath -Force
    }

    $presentation.SaveAs($outputPath, 24)
    $presentation.Close()
    $presentation = $null
}
finally {
    if ($presentation) {
        $presentation.Close()
    }
    if ($powerPoint) {
        $powerPoint.Quit()
    }
    [System.GC]::Collect()
    [System.GC]::WaitForPendingFinalizers()
}

Write-Output "Created $outputPath"
