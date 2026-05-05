# Claude Jira Assistant v2
# This file should be saved as UTF-8 with BOM.

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# Fixed settings
$ProjectDir = "D:\tigerProject"
$OutputDir = "D:\第三方排查MD檔"
$StandardMd = Join-Path $OutputDir "AI_JIRA_WORK_STANDARD.md"
$GorFile = "C:\Users\user\OneDrive\桌面\testpage\GOR.txt"
$DbFile = "C:\Users\user\OneDrive\桌面\testpage\DB連線.txt"

# Jira settings from environment variables
$JiraBaseUrl = $env:JIRA_BASE_URL
$JiraEmail = $env:JIRA_EMAIL
$JiraToken = $env:JIRA_API_TOKEN

if ([string]::IsNullOrWhiteSpace($JiraBaseUrl)) {
    $JiraBaseUrl = "https://innotech.atlassian.net"
}

if (!(Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}

# GUI
$form = New-Object System.Windows.Forms.Form
$form.Text = "Claude Jira Assistant"
$form.Size = New-Object System.Drawing.Size(520, 250)
$form.StartPosition = "CenterScreen"
$form.Topmost = $true

$label = New-Object System.Windows.Forms.Label
$label.Text = "Input Jira issue key, example: IN-128950"
$label.AutoSize = $true
$label.Location = New-Object System.Drawing.Point(30, 30)
$form.Controls.Add($label)

$textBox = New-Object System.Windows.Forms.TextBox
$textBox.Size = New-Object System.Drawing.Size(430, 30)
$textBox.Location = New-Object System.Drawing.Point(30, 65)
$textBox.Font = New-Object System.Drawing.Font("Consolas", 12)
$form.Controls.Add($textBox)

$checkOpen = New-Object System.Windows.Forms.CheckBox
$checkOpen.Text = "Open markdown after finished"
$checkOpen.Checked = $true
$checkOpen.AutoSize = $true
$checkOpen.Location = New-Object System.Drawing.Point(30, 105)
$form.Controls.Add($checkOpen)

$button = New-Object System.Windows.Forms.Button
$button.Text = "Start"
$button.Size = New-Object System.Drawing.Size(120, 36)
$button.Location = New-Object System.Drawing.Point(340, 145)
$form.Controls.Add($button)

$global:IssueKey = $null
$global:OpenAfterDone = $true

$button.Add_Click({
    $global:IssueKey = $textBox.Text.Trim()
    $global:OpenAfterDone = $checkOpen.Checked
    $form.Close()
})

$form.AcceptButton = $button
$form.ShowDialog() | Out-Null

if ([string]::IsNullOrWhiteSpace($global:IssueKey)) {
    Write-Host "[ERROR] No Jira issue key input."
    exit 1
}

$IssueKey = $global:IssueKey.ToUpper()

if ($IssueKey -notmatch "^IN-\d+$") {
    Write-Host "[ERROR] Invalid Jira issue key. Example: IN-128950"
    exit 1
}

# Read standard md
if (Test-Path $StandardMd) {
    $StandardContent = Get-Content $StandardMd -Raw -Encoding UTF8
} else {
    $StandardContent = "Standard markdown not found: $StandardMd"
}

# Read GOR
if (Test-Path $GorFile) {
    $GorContent = Get-Content $GorFile -Raw -Encoding UTF8
} else {
    $GorContent = "GOR file not found: $GorFile"
}

# Read Jira
$JiraContent = ""

if (![string]::IsNullOrWhiteSpace($JiraEmail) -and ![string]::IsNullOrWhiteSpace($JiraToken)) {
    try {
        $pair = "$JiraEmail`:$JiraToken"
        $encoded = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes($pair))

        $headers = @{
            Authorization = "Basic $encoded"
            Accept = "application/json"
        }

        $url = "$JiraBaseUrl/rest/api/3/issue/$IssueKey"
        Write-Host "[INFO] Reading Jira: $url"

        $response = Invoke-RestMethod -Uri $url -Headers $headers -Method Get

        $summary = $response.fields.summary
        $status = $response.fields.status.name
        $created = $response.fields.created
        $updated = $response.fields.updated
        $descJson = $response.fields.description | ConvertTo-Json -Depth 30

        $JiraContent = @"
Jira issue: $IssueKey
Summary: $summary
Status: $status
Created: $created
Updated: $updated

Description JSON:
$descJson
"@
    } catch {
        $JiraContent = "Failed to read Jira: $($_.Exception.Message). Continue with local context."
    }
} else {
    $JiraContent = "JIRA_EMAIL or JIRA_API_TOKEN not set. Continue with issue key and local context."
}

# Existing MD list
try {
    $RelatedMdList = Get-ChildItem -Path $OutputDir -Filter "*.md" -Recurse -ErrorAction SilentlyContinue |
        Select-Object -First 80 FullName |
        ForEach-Object { $_.FullName } |
        Out-String
} catch {
    $RelatedMdList = "Failed to list existing markdown files: $($_.Exception.Message)"
}

$Prompt = @"
You are a senior Java Backend / SRE / payment / KYC debugging engineer.

Please follow the standard markdown below and generate a complete markdown debug report.

==============================
STANDARD MD
==============================
$StandardContent

==============================
JIRA CONTENT
==============================
$JiraContent

==============================
GOR CONTENT
==============================
$GorContent

==============================
PROJECT PATH
==============================
$ProjectDir

==============================
DB CONNECTION FILE
==============================
$DbFile

==============================
EXISTING MD FILE LIST
==============================
$RelatedMdList

==============================
TASK
==============================
Please debug Jira issue $IssueKey.

Requirements:
1. Analyze Jira/GOR background.
2. Suggest code search modules and keywords.
3. Point out likely Java class / method / mapper / config.
4. Generate SELECT SQL if DB verification is needed.
5. Do not generate direct PROD UPDATE/DELETE except in a clearly marked manual-confirmation section.
6. Output a practical markdown report.
"@

$time = Get-Date -Format "yyyyMMdd_HHmmss"
$outFile = Join-Path $OutputDir "result_$IssueKey`_$time.md"
$promptFile = Join-Path $OutputDir "prompt_$IssueKey`_$time.md"

$Prompt | Out-File $promptFile -Encoding UTF8

Write-Host "[INFO] Prompt saved: $promptFile"
Write-Host "[INFO] Calling Claude..."
Write-Host ""

try {
    claude -p $Prompt | Out-File $outFile -Encoding UTF8
    Write-Host ""
    Write-Host "[OK] Markdown generated: $outFile"

    if ($global:OpenAfterDone -eq $true) {
        Start-Process $outFile
    }
} catch {
    Write-Host "[ERROR] Claude failed: $($_.Exception.Message)"
    Write-Host "[INFO] Prompt file saved. You can manually copy it to Claude:"
    Write-Host $promptFile
}
