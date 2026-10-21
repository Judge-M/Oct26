param(
    [string]$IntroVideo = (Join-Path $PSScriptRoot "..\docs\event-day-deck\media\introbrief.mp4"),
    [string]$OutroVideo = (Join-Path $PSScriptRoot "..\docs\event-day-deck\media\outrobrief.mp4"),
    [string]$OutputDirectory = (Join-Path $PSScriptRoot "..\docs\event-day-deck"),
    [string]$LandingPage = "https://ctfd.cyberexperts.org/silent-ridge/register",
    [switch]$SkipLibreOffice
)

$ErrorActionPreference = "Stop"

function Resolve-RequiredFile {
    param([string]$Path, [string]$Label)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Label not found: $Path"
    }
    return (Resolve-Path -LiteralPath $Path).Path
}

function Get-Color {
    param([int]$Red, [int]$Green, [int]$Blue)
    return [System.Drawing.ColorTranslator]::ToOle(
        [System.Drawing.Color]::FromArgb($Red, $Green, $Blue))
}

$introVideoPath = Resolve-RequiredFile -Path $IntroVideo -Label "Intro video"
$outroVideoPath = Resolve-RequiredFile -Path $OutroVideo -Label "Outro video"
$outputPath = [System.IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Path $outputPath -Force | Out-Null

$openingPptx = Join-Path $outputPath "opening-brief.pptx"
$closingPptx = Join-Path $outputPath "closing-brief.pptx"

$deep = Get-Color 22 33 30
$paper = Get-Color 245 242 234
$ink = Get-Color 26 30 36
$slate = Get-Color 39 64 59
$amber = Get-Color 199 125 31
$muted = Get-Color 107 110 106
$line = Get-Color 216 210 196
$paleGreen = Get-Color 228 233 226
$light = Get-Color 245 242 234
$softLight = Get-Color 201 207 199
$ring = Get-Color 58 82 75

$msoFalse = 0
$msoTrue = -1
$blankLayout = 12
$horizontalText = 1
$powerPoint = $null

function Add-TextBox {
    param(
        $Slide, [string]$Text, [double]$Left, [double]$Top,
        [double]$Width, [double]$Height, [double]$Size, [int]$Color,
        [bool]$Bold = $false, [string]$Font = "Aptos",
        [int]$Alignment = 1, [double]$Margin = 0
    )
    $shape = $Slide.Shapes.AddTextbox($horizontalText, $Left, $Top, $Width, $Height)
    $shape.TextFrame.MarginLeft = $Margin
    $shape.TextFrame.MarginRight = $Margin
    $shape.TextFrame.MarginTop = $Margin
    $shape.TextFrame.MarginBottom = $Margin
    $shape.TextFrame.WordWrap = $msoTrue
    $range = $shape.TextFrame.TextRange
    $range.Text = $Text
    $range.Font.Name = $Font
    $range.Font.Size = $Size
    $range.Font.Color.RGB = $Color
    $range.Font.Bold = $(if ($Bold) { $msoTrue } else { $msoFalse })
    $range.ParagraphFormat.Alignment = $Alignment
    return $shape
}

function Add-BaseSlide {
    param($Presentation, [bool]$Dark = $false)
    $slide = $Presentation.Slides.Add($Presentation.Slides.Count + 1, $blankLayout)
    $background = $slide.Shapes.AddShape(1, 0, 0, 960, 540)
    $background.Fill.Solid()
    $background.Fill.ForeColor.RGB = $(if ($Dark) { $deep } else { $paper })
    $background.Line.Visible = $msoFalse
    return $slide
}

function Add-DarkRings {
    param($Slide)
    foreach ($spec in @(
        @(620, 72, 390, 390, 34),
        @(680, 132, 270, 270, 27),
        @(740, 192, 150, 150, 18)
    )) {
        $oval = $Slide.Shapes.AddShape(9, $spec[0], $spec[1], $spec[2], $spec[3])
        $oval.Fill.Visible = $msoFalse
        $oval.Line.ForeColor.RGB = $ring
        $oval.Line.Weight = $spec[4]
        $oval.Line.Transparency = 0.35
    }
    $dot = $Slide.Shapes.AddShape(9, 852, 164, 16, 16)
    $dot.Fill.Solid()
    $dot.Fill.ForeColor.RGB = $amber
    $dot.Line.Visible = $msoFalse
}

function Add-LightHeader {
    param($Slide, [string]$Tag, [string]$Title)
    Add-TextBox $Slide $Tag 64 36 500 24 13 $amber $true | Out-Null
    Add-TextBox $Slide $Title 64 66 832 52 29 $ink $true | Out-Null
    $rule = $Slide.Shapes.AddShape(1, 64, 121, 832, 2)
    $rule.Fill.Solid()
    $rule.Fill.ForeColor.RGB = $line
    $rule.Line.Visible = $msoFalse
}

function Add-Footer {
    param($Slide, [string]$Text = "OPERATION SILENT RIDGE")
    Add-TextBox $Slide $Text 64 505 700 18 11 $muted | Out-Null
}

function Add-VideoSlide {
    param($Presentation, [string]$VideoPath, [string]$AlternativeText)
    $slide = Add-BaseSlide $Presentation $true
    $media = $slide.Shapes.AddMediaObject2($VideoPath, $msoFalse, $msoTrue, 210, 0, 540, 540)
    $media.Name = $AlternativeText
    $media.AlternativeText = "$AlternativeText. Embedded MP4 for room-wide playback."
    $media.AnimationSettings.PlaySettings.PlayOnEntry = $msoTrue
    $media.AnimationSettings.PlaySettings.HideWhileNotPlaying = $msoFalse
}

function Add-OpeningDeck {
    param($Presentation)

    $slide = Add-BaseSlide $Presentation $true
    Add-DarkRings $slide
    Add-TextBox $slide "OPERATION BRIEF" 64 110 480 24 13 $amber $true | Out-Null
    Add-TextBox $slide "Operation`nSilent Ridge" 64 150 540 128 50 $light $true | Out-Null
    $rule = $slide.Shapes.AddShape(1, 64, 296, 120, 3)
    $rule.Fill.Solid(); $rule.Fill.ForeColor.RGB = $amber; $rule.Line.Visible = $msoFalse
    Add-TextBox $slide "A patrol's movement details may have leaked.`nYour team will establish what happened and support every finding with evidence." 64 316 510 88 17 $softLight | Out-Null
    Add-TextBox $slide "PATROL LANTERN" 708 400 200 24 13 $softLight $false "Aptos" 2 | Out-Null

    $slide = Add-BaseSlide $Presentation
    Add-LightHeader $slide "THE SITUATION" "The outgoing shift hands you an unresolved incident"
    Add-TextBox $slide "Patrol LANTERN is already in the field. The outgoing shift suspects that an older movement brief left the protected enclave before a newer route replaced it." 64 145 832 66 19 $ink | Out-Null
    Add-TextBox $slide "What the records suggest" 64 236 250 28 17 $slate $true | Out-Null
    Add-TextBox $slide "A document request, an outbound transfer, identity activity, and persistence records overlap around WS-17." 64 274 250 126 16 $ink | Out-Null
    Add-TextBox $slide "What remains unknown" 355 236 250 28 17 $amber $true | Out-Null
    Add-TextBox $slide "What information left, who controlled the access, and which systems still require attention." 355 274 250 126 16 $ink | Out-Null
    Add-TextBox $slide "Your mission" 646 236 250 28 17 $slate $true | Out-Null
    Add-TextBox $slide "Build a defensible shared assessment. Separate what the evidence proves from what it only suggests." 646 274 250 126 16 $ink | Out-Null
    Add-Footer $slide

    $slide = Add-BaseSlide $Presentation
    Add-LightHeader $slide "YOUR WORK" "Claim, investigate, answer, share"
    $steps = @(
        @("1", "CLAIM", "Choose an available lead in the IRIS incident queue."),
        @("2", "INVESTIGATE", "Use the named tool on the released evidence. Keep the work read-only."),
        @("3", "ANSWER", "Submit the requested value in CTFd and use help when you need it."),
        @("4", "SHARE", "A verified finding publishes back to the shared incident picture.")
    )
    for ($index = 0; $index -lt $steps.Count; $index++) {
        $left = 64 + ($index * 211)
        $box = $slide.Shapes.AddShape(1, $left, 168, 184, 228)
        $box.Fill.Solid(); $box.Fill.ForeColor.RGB = $paleGreen
        $box.Line.ForeColor.RGB = $slate; $box.Line.Weight = 1
        Add-TextBox $slide $steps[$index][0] ($left + 16) 184 48 48 34 $amber $true | Out-Null
        Add-TextBox $slide $steps[$index][1] ($left + 16) 242 152 28 16 $slate $true | Out-Null
        Add-TextBox $slide $steps[$index][2] ($left + 16) 280 152 94 14 $ink | Out-Null
    }
    Add-TextBox $slide "The participant landing page contains every login, setup step, scoring rule, and recovery instruction." 64 432 832 34 15 $muted $false "Aptos" 2 | Out-Null
    Add-Footer $slide

    Add-VideoSlide $Presentation $introVideoPath "Opening brief from Faye Maxwell"

    $slide = Add-BaseSlide $Presentation $true
    Add-DarkRings $slide
    Add-TextBox $slide "GET STARTED" 64 92 400 24 13 $amber $true | Out-Null
    Add-TextBox $slide "Open the participant landing page" 64 130 690 54 34 $light $true | Out-Null
    Add-TextBox $slide $LandingPage 64 210 770 42 23 $amber $true | Out-Null
    Add-TextBox $slide "1. One captain registers the team.`n2. Bookmark and save the private team handout.`n3. Follow the five on-screen steps. Keep the handout open." 64 284 600 118 18 $softLight | Out-Null
    Add-TextBox $slide "The landing page is the source of truth for logins, desktops, scoring, help, and troubleshooting." 64 444 700 42 14 $muted | Out-Null
}

function Add-ClosingDeck {
    param($Presentation)

    $slide = Add-BaseSlide $Presentation $true
    Add-DarkRings $slide
    Add-TextBox $slide "OPERATION SILENT RIDGE" 64 116 500 24 13 $amber $true | Out-Null
    Add-TextBox $slide "Final assessment" 64 158 650 64 44 $light $true | Out-Null
    $rule = $slide.Shapes.AddShape(1, 64, 242, 120, 3)
    $rule.Fill.Solid(); $rule.Fill.ForeColor.RGB = $amber; $rule.Line.Visible = $msoFalse
    Add-TextBox $slide "Bring it in. Preserve your notes and complete your handoffs." 64 270 560 72 20 $softLight | Out-Null
    Add-TextBox $slide "Faye Maxwell, SOC supervisor" 64 448 520 28 15 $muted | Out-Null

    Add-VideoSlide $Presentation $outroVideoPath "Closing brief from Faye Maxwell"

    $slide = Add-BaseSlide $Presentation $true
    Add-DarkRings $slide
    Add-TextBox $slide "FINAL SCOREBOARD" 64 92 500 24 13 $amber $true | Out-Null
    Add-TextBox $slide "And the winner is..." 64 138 690 62 40 $light $true | Out-Null
    $rule = $slide.Shapes.AddShape(1, 64, 224, 120, 3)
    $rule.Fill.Solid(); $rule.Fill.ForeColor.RGB = $amber; $rule.Line.Visible = $msoFalse
    Add-TextBox $slide "[TEAM NAME]" 64 272 720 92 46 $amber $true | Out-Null
    Add-TextBox $slide "Replace the placeholder before presenting, or reveal the name live." 64 426 650 34 15 $muted | Out-Null
}

function Save-Deck {
    param([string]$Path, [scriptblock]$Builder)
    $presentation = $powerPoint.Presentations.Add()
    try {
        $presentation.PageSetup.SlideWidth = 960
        $presentation.PageSetup.SlideHeight = 540
        & $Builder $presentation
        if (Test-Path -LiteralPath $Path) {
            Remove-Item -LiteralPath $Path -Force
        }
        $presentation.SaveAs($Path, 24)
    }
    finally {
        $presentation.Close()
    }
}

try {
    $powerPoint = New-Object -ComObject PowerPoint.Application
    $powerPoint.Visible = $msoTrue
    Save-Deck $openingPptx ${function:Add-OpeningDeck}
    Save-Deck $closingPptx ${function:Add-ClosingDeck}
}
finally {
    if ($powerPoint) {
        $powerPoint.Quit()
    }
    [System.GC]::Collect()
    [System.GC]::WaitForPendingFinalizers()
}

if (-not $SkipLibreOffice) {
    $soffice = "C:\Program Files\LibreOffice\program\soffice.exe"
    if (-not (Test-Path -LiteralPath $soffice -PathType Leaf)) {
        throw "LibreOffice was not found at $soffice. Use -SkipLibreOffice to build only PowerPoint files."
    }
    foreach ($deck in @($openingPptx, $closingPptx)) {
        $profileName = ([System.IO.Path]::GetFileNameWithoutExtension($deck) +
                        "-lo-profile-" + [guid]::NewGuid().ToString("N"))
        $profilePath = Join-Path ([System.IO.Path]::GetTempPath()) $profileName
        $profileUri = ([System.Uri]$profilePath).AbsoluteUri
        $odp = [System.IO.Path]::ChangeExtension($deck, ".odp")
        if (Test-Path -LiteralPath $odp) {
            Remove-Item -LiteralPath $odp -Force
        }
        & $soffice --headless --invisible --nodefault --nolockcheck --nologo --nofirststartwizard "-env:UserInstallation=$profileUri" --convert-to odp --outdir $outputPath $deck
        for ($wait = 0; $wait -lt 60 -and -not (Test-Path -LiteralPath $odp -PathType Leaf); $wait++) {
            Start-Sleep -Seconds 1
        }
        if (-not (Test-Path -LiteralPath $odp -PathType Leaf) -or
            (Get-Item -LiteralPath $odp).Length -eq 0) {
            throw "LibreOffice conversion failed for $deck"
        }
    }
}

Write-Output "Created $openingPptx"
Write-Output "Created $closingPptx"
if (-not $SkipLibreOffice) {
    Write-Output "Created $(Join-Path $outputPath 'opening-brief.odp')"
    Write-Output "Created $(Join-Path $outputPath 'closing-brief.odp')"
}
