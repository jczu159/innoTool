# Claude Jira Assistant v2 使用方式

## 1. 解壓縮

把整包解壓到例如：

```text
D:\tiger-release-helper\dist\AI自動查單工具
```

## 2. 複製標準 MD

把：

```text
AI_JIRA_WORK_STANDARD.md
```

複製到：

```text
D:\第三方排查MD檔\AI_JIRA_WORK_STANDARD.md
```

## 3. 第一次設定 Jira Token

用 PowerShell 執行：

```powershell
setx JIRA_BASE_URL "https://innotech.atlassian.net"
setx JIRA_EMAIL "ryan@innotech.me"
setx JIRA_API_TOKEN "你的新 Jira API token"
```

設定後請重新開 CMD / PowerShell。

## 4. 執行

雙擊：

```text
start_claude_jira.bat
```

輸入：

```text
IN-128950
```

會輸出到：

```text
D:\第三方排查MD檔
```

## 5. 如果 GUI 還是沒跳

請用 PowerShell 手動執行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\tiger-release-helper\dist\AI自動查單工具\run_claude_jira_gui.ps1"
```
