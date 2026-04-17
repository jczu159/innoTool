# Tiger Release Branch Helper

打版輔助工具，用於管理 tiger 系列 Spring Boot 專案的 Release Branch 建立與版本同步。

---

## 環境需求

- Windows 10+
- 本機已安裝並設定好 `git`（需可在 CMD 執行）
- 可連線至 GitLab（`https://gitlab.service-hub.tech`）

---

## 啟動方式

直接執行 `TigerReleaseBranchHelper.exe`，無需安裝任何環境。

---

## 設定說明

| 欄位 | 說明 | 預設值 |
|------|------|--------|
| GitLab URL | GitLab 伺服器網址 | `https://gitlab.service-hub.tech` |
| Access Token | GitLab Personal Access Token（至少需有 `read_api` + `write_repository` 權限） | - |
| Group | GitLab Group 名稱 | `java-backend` |
| Filter | 篩選專案名稱關鍵字 | `tiger` |
| 本地根目錄 | 所有專案的本地父資料夾 | `D:\tigerProject` |
| 目標 Branch | 手動指定要建立的 branch 名稱（格式：`release/x.y.z`），留空則自動推算 | - |

填寫完畢後點選 **儲存設定** 即可永久保存（Token 加密儲存）。

---

## 功能按鈕說明

### 重新載入專案
- 從 GitLab 拉取符合 Filter 關鍵字的所有專案清單（速度快，不打 tag API）
- 顯示每個專案的本地路徑是否存在（`Ready` / `Not Found`）
- 雙擊專案列可手動指定該專案的本地路徑
- 無效專案（`tiger-values` 等）已列入排除清單，不會出現在清單中

### 取得最新 Tags
- 對目前清單中的所有專案重新打 GitLab API 取得最新 release tag
- 並自動推算建議的下一個 Branch 名稱

### 自動帶出 Branch
- 若「目標 Branch」欄位為空：對每個專案依其最新 Tag 自動推算 Branch（patch +1）
- 若填有「目標 Branch」：將所有專案統一套用該 Branch 名稱

### 單筆切 Branch
- 對目前「點選」（highlight）的單一專案建立 Release Branch

### 批次一鍵切 Branch
- 對所有「勾選」的專案批次建立 Release Branch
- 執行前會顯示確認清單

> **Branch 建立流程：**
> 1. 檢查遠端 branch 是否已存在（重複則跳過）
> 2. 若本地路徑存在：執行 `git fetch --tags` → `git checkout -b` → 寫入 `version.properties` 並 commit
> 3. 若本地路徑不存在：改用 GitLab API 直接建立 branch

### 全選 / 全不選
- 切換所有專案的勾選狀態

### 同步 GAME
- **僅對 `tiger-thirdparty` 與 `tiger-thirdparty-payment` 兩個專案有效**（需先勾選）
- 自動判斷應使用的 `tiger-game` 版本：
  - 若本地 `tiger-game` 的 branch 以 `release` 開頭 → 從 branch 名稱取版本（例如 `release/5.39.13` → `v5.39.13`）
  - 否則 → 從 GitLab 取 `tiger-game` 最新的 release tag（例如 `release-5.39.12` → `v5.39.12`）
- 將勾選專案的 `pom.xml` 中 `<tiger.game.version>` 更新為對應版本

### 同步 COMMON
- 對所有「勾選」的專案有效
- 自動判斷應使用的 `tiger-common` 版本：
  - 若本地 `tiger-common` 的 branch 以 `release` 開頭 → 從 branch 名稱取版本
  - 否則 → 從 GitLab 取 `tiger-common` 最新的 release tag
- 將勾選專案的 `pom.xml` 中 `<tiger.common.version>` 更新為對應版本

---

## 專案列表說明

| 欄位 | 說明 |
|------|------|
| ✓ | 勾選框，點擊切換；用於批次操作 |
| 專案名稱 | GitLab 上的專案名稱 |
| 最新 Tag | 目前 GitLab 上最新的 `release-x.y.z` tag |
| 本地路徑 | 對應的本地 git repo 路徑（雙擊可修改） |
| 目標 Branch | 預計建立的 branch 名稱 |
| 狀態 | `Ready` / `Not Found` / `No Tag` / `Working...` / `Done` / `Error` |

**列顏色含義：**
- 綠色 = Ready（本地路徑存在且有 Tag）
- 黃色 = Not Found（本地路徑不存在，仍可透過 API 建立 branch）
- 紅色 = Error

---

## 預設排除專案

以下專案無論是否符合 Filter，載入時均自動排除：

```
tiger-tools, tiger-value, tiger-values, tiger-wallet, tiger-sqlddl, tiger-sign,
tiger-s3-lambda, tiger-registry, tiger-proxy, tiger-project,
tiger-oncall-sql, tiger-initial, tiger-blockchain, tiger-actuator
```

---

## 注意事項

- Branch 格式必須為 `release/x.y.z`，否則操作會被拒絕
- 同步 GAME 只改 `tiger-thirdparty` / `tiger-thirdparty-payment` 的 pom.xml，其他專案無效
- 同步 COMMON / GAME 若專案 pom.xml 內找不到對應的 version tag，該專案會被跳過並顯示錯誤
- Token 使用 Fernet 對稱加密儲存於設定檔，請妥善保管設定檔
