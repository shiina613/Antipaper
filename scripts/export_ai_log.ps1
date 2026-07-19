param(
    [string]$SessionRoot = "C:\Users\Admin\.codex\sessions",
    [string]$SessionIndex = "C:\Users\Admin\.codex\session_index.jsonl",
    [string]$OutputPath = "docs\AI_LOG_2026-07-18_2026-07-19.md"
)

$ErrorActionPreference = "Stop"

function Convert-ToSafeText {
    param([AllowNull()][string]$Text)

    if ([string]::IsNullOrWhiteSpace($Text)) { return "" }

    # A log committed to the repository must not expose credentials that may have
    # appeared in a prompt or an assistant response.
    $safe = $Text
    $safe = $safe -replace '(?i)(sk-[a-z0-9_-]{12,})', '[REDACTED_OPENAI_KEY]'
    $safe = $safe -replace '(?i)(gh[pousr]_[a-z0-9_]{20,})', '[REDACTED_GITHUB_TOKEN]'
    $safe = $safe -replace '(?i)(Bearer\s+)[^\s`]+', '$1[REDACTED_TOKEN]'
    $safe = $safe -replace '(?im)^(\s*(?:OPENAI_API_KEY|API_KEY|GITHUB_TOKEN|TOKEN)\s*=\s*).+$', '$1[REDACTED]'
    return $safe.Trim()
}

function Get-JsonLines {
    param([string]$Path)

    return @(
        Get-Content -LiteralPath $Path -Encoding utf8 |
            ForEach-Object {
                try { $_ | ConvertFrom-Json } catch { $null }
            } |
            Where-Object { $null -ne $_ }
    )
}

function Get-UserPrompt {
    param($Item)

    if ($Item.type -ne 'response_item' -or $Item.payload.type -ne 'message' -or $Item.payload.role -ne 'user') {
        return @()
    }

    $prompts = @()
    foreach ($content in @($Item.payload.content)) {
        if ($content.type -ne 'input_text' -or [string]::IsNullOrWhiteSpace($content.text)) { continue }
        $text = [string]$content.text

        # Platform/developer context is not a user prompt and is deliberately
        # excluded from the shareable audit log.
        if ($text -match '^<(recommended_plugins|environment_context|collaboration_mode|skills_instructions|apps_instructions|plugins_instructions)>') { continue }
        if ($text -match '^# AGENTS\.md instructions') { continue }
        if ($text -match '^The following is the Codex agent history whose request action you are assessing') { continue }

        # IDE context is retained only insofar as it identifies the actual request.
        if ($text -match '(?s)^# Context from my IDE setup:.*?## My request for Codex:\s*(.+)$') {
            $text = $Matches[1]
        }

        $text = Convert-ToSafeText $text
        if ($text) { $prompts += $text }
    }
    return $prompts
}

$index = @{}
if (Test-Path -LiteralPath $SessionIndex) {
    Get-Content -LiteralPath $SessionIndex -Encoding utf8 | ForEach-Object {
        try {
            $entry = $_ | ConvertFrom-Json
            $index[$entry.id] = $entry.thread_name
        } catch { }
    }
}

$files = Get-ChildItem -LiteralPath $SessionRoot -Recurse -File |
    Where-Object { $_.Name -match '^rollout-2026-07-(18|19)T.*\.jsonl$' } |
    Sort-Object Name

$sessions = @()
$excluded = 0
foreach ($file in $files) {
    $sessionId = [regex]::Match($file.Name, '[0-9a-f]{8}-[0-9a-f-]{27}').Value
    $title = [string]$index[$sessionId]

    # Unnamed files in this interval are policy/reviewer sessions initiated by
    # Codex itself. They are not user-Codex conversations.
    if ([string]::IsNullOrWhiteSpace($title)) {
        $excluded++
        continue
    }

    $items = Get-JsonLines $file.FullName
    $prompts = @($items | ForEach-Object { Get-UserPrompt $_ })
    $answers = @(
        $items |
            Where-Object { $_.type -eq 'event_msg' -and $_.payload.type -eq 'agent_message' -and $_.payload.phase -eq 'final_answer' } |
            ForEach-Object { Convert-ToSafeText ([string]$_.payload.message) } |
            Where-Object { $_ }
    )

    $localTime = [datetime]::ParseExact(
        $file.Name.Substring(8, 19),
        'yyyy-MM-ddTHH-mm-ss',
        [Globalization.CultureInfo]::InvariantCulture
    )

    $sessions += [pscustomobject]@{
        Id = $sessionId
        Title = $title
        LocalTime = $localTime
        Prompts = $prompts
        Answers = $answers
    }
}

$lines = [System.Collections.Generic.List[string]]::new()
$lines.Add('# AI Log — Codex')
$lines.Add('')
$lines.Add('## Phạm vi và phương pháp')
$lines.Add('')
$lines.Add('- Khoảng thời gian: 18/07/2026 04:33 đến 19/07/2026 10:05 (Asia/Bangkok).')
$lines.Add("- Nguồn: $($sessions.Count) session tương tác Codex có tiêu đề; $excluded session kiểm tra/approval nội bộ được loại trừ.")
$lines.Add('- Mỗi mục lưu nguyên văn prompt người dùng và các câu trả lời kết thúc của Codex sau khi loại bỏ system/developer instruction, tool-call/tool-output và thông tin xác thực.')
$lines.Add('- Một số phiên không có câu trả lời kết thúc vì người dùng chuyển sang một session khác hoặc phiên bị ngắt; mục đó được ghi rõ là không có kết luận cuối.')
$lines.Add('- Đây là nhật ký truy vết, không phải bằng chứng thay thế cho Git history, kiểm thử hoặc trạng thái deployment.')

foreach ($session in $sessions) {
    $lines.Add('')
    $lines.Add("## $($session.LocalTime.ToString('dd/MM/yyyy HH:mm')) — $($session.Title)")
    $lines.Add('')
    $lines.Add('- Session ID: `' + $session.Id + '`')
    $lines.Add('')
    $lines.Add('### Prompt đã dùng')
    $lines.Add('')
    if ($session.Prompts.Count -eq 0) {
        $lines.Add('_Không trích xuất được prompt độc lập; tiêu đề session phản ánh yêu cầu: ' + $session.Title + '._')
    } else {
        $number = 1
        foreach ($prompt in $session.Prompts) {
            $lines.Add("#### Prompt $number")
            $lines.Add('')
            $lines.Add('```text')
            $lines.Add($prompt)
            $lines.Add('```')
            $number++
        }
    }

    $lines.Add('')
    $lines.Add('### Nội dung/kết quả được Codex báo cáo')
    $lines.Add('')
    if ($session.Answers.Count -eq 0) {
        $lines.Add('_Không có thông điệp kết thúc được lưu cho session này._')
    } else {
        foreach ($answer in $session.Answers) {
            $lines.Add($answer)
            $lines.Add('')
        }
    }
}

$directory = Split-Path -Parent $OutputPath
if ($directory) { New-Item -ItemType Directory -Path $directory -Force | Out-Null }
[System.IO.File]::WriteAllLines((Resolve-Path $directory).Path + '\' + (Split-Path -Leaf $OutputPath), $lines, [System.Text.UTF8Encoding]::new($false))
Write-Output "Wrote $OutputPath with $($sessions.Count) sessions."

