<#
.SYNOPSIS
    啟動本機開發環境：PostgreSQL、辨識 stub、後端 API、前端。

.DESCRIPTION
    本機沒有 Docker（需管理員權限），改用免安裝的 PostgreSQL 二進位檔。
    此腳本會確認資料庫已啟動，必要時初始化並套用 migration 與種子資料，
    然後在背景啟動三個服務。

.EXAMPLE
    .\scripts\dev-up.ps1             # 前端走 http://localhost:3000
    .\scripts\dev-up.ps1 -Https      # 前端走 https://localhost:3000（LINE Login 需要）
    .\scripts\dev-up.ps1 -Stop       # 關閉所有服務
#>
param(
    [switch]$Stop,
    # LINE Login 的 Callback URL 已不接受 http，測試網頁登入入口時需開此旗標。
    # 首次執行會自動下載 mkcert 並產生自簽憑證（瀏覽器會警告一次，選繼續即可）。
    [switch]$Https
)

# 刻意用 Continue 而非 Stop：Windows PowerShell 5.1 會把原生執行檔
# （initdb / pg_ctl / createdb）寫到 stderr 的**警告**包成 ErrorRecord，
# 在 Stop 模式下會讓成功的指令也中斷腳本。改以 $LASTEXITCODE 明確判斷。
$ErrorActionPreference = 'Continue'

$Root = Split-Path -Parent $PSScriptRoot
$PgRoot = Join-Path $env:LOCALAPPDATA 'caluli-pg'
$PgBin = Join-Path $PgRoot 'pgsql\bin'
$PgData = Join-Path $PgRoot 'data'
$LogDir = Join-Path $Root '.dev-logs'
$PgPort = 55432

function Write-Step($message) { Write-Host "`n>> $message" -ForegroundColor Cyan }
function Write-Ok($message) { Write-Host "   OK  $message" -ForegroundColor Green }
function Write-Warn2($message) { Write-Host "   !!  $message" -ForegroundColor Yellow }

# ---------------------------------------------------------------- 停止
if ($Stop) {
    Write-Step '停止服務'

    # 依「監聽埠」而非程序路徑來找——node 的執行檔位於 winget 安裝目錄，
    # 用路徑比對抓不到，會留下佔用 3000 埠的殘留程序。
    # 反覆掃到全部釋放為止。注意兩個陷阱：
    #  1. node 的執行檔在 winget 目錄，用程序路徑比對抓不到 → 改用監聽埠。
    #  2. uvicorn --reload 的 watcher 死掉後，其 multiprocessing 子程序會
    #     成為**孤兒**並繼續持有埠；此時 Get-Process 查父 PID 會失敗，
    #     必須直接殺掉持有埠的那個 PID（不經 Get-Process 過濾）。
    for ($round = 1; $round -le 5; $round++) {
        $owners = foreach ($port in @(3000, 3001, 3002, 8000, 8900)) {
            Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
                Select-Object @{n = 'Port'; e = { $port } }, OwningProcess
        }
        $owners = $owners | Sort-Object OwningProcess -Unique
        if (-not $owners) { break }

        foreach ($owner in $owners) {
            $name = (Get-Process -Id $owner.OwningProcess -ErrorAction SilentlyContinue).ProcessName
            if (-not $name) { $name = '孤兒程序' }
            Write-Host "   停止 PID $($owner.OwningProcess) ($name)  port $($owner.Port)"
            Stop-Process -Id $owner.OwningProcess -Force -ErrorAction SilentlyContinue
        }
        Start-Sleep -Milliseconds 800
    }

    if (Test-Path $PgData) {
        & "$PgBin\pg_ctl.exe" -D $PgData stop -m fast 2>&1 | Out-Null
        Write-Ok 'PostgreSQL 已停止'
    }
    Write-Ok '服務已全部停止'
    return
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
# 清除上一輪的 log——否則後面偵測「Next 是否被擠到其他埠」時會讀到舊紀錄而誤報。
Get-ChildItem $LogDir -Filter '*.log' -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
Get-ChildItem $LogDir -Filter '*.err' -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

# ---------------------------------------------------------- 前置檢查
Write-Step '檢查前置需求'

foreach ($file in @("$Root\backend\.env", "$Root\frontend\.env.local")) {
    if (-not (Test-Path $file)) {
        throw "缺少設定檔 $file，請從對應的 .example 複製後填入實際值。"
    }
}
Write-Ok '設定檔齊備'

if (-not (Test-Path "$PgBin\pg_ctl.exe")) {
    throw @"
找不到 PostgreSQL 二進位檔（預期在 $PgBin）。
請下載並解壓：
  https://get.enterprisedb.com/postgresql/postgresql-16.4-1-windows-x64-binaries.zip
  解壓後把 pgsql 資料夾放到 $PgRoot
或改用 Docker：docker compose up -d postgres（需管理員權限）
"@
}

# ------------------------------------------------------------ 資料庫
Write-Step 'PostgreSQL'

$ready = (& "$PgBin\pg_isready.exe" -h 127.0.0.1 -p $PgPort 2>&1) -match 'accepting'
if (-not $ready) {
    if (-not (Test-Path $PgData)) {
        Write-Host '   初始化資料庫叢集…'
        $pwFile = Join-Path $env:TEMP 'caluli-pgpw.txt'
        Set-Content -Path $pwFile -Value 'caluli' -NoNewline -Encoding ascii
        & "$PgBin\initdb.exe" -D $PgData -U caluli --pwfile=$pwFile -E UTF8 --locale=C | Out-Null
        $initExit = $LASTEXITCODE
        Remove-Item $pwFile -Force -ErrorAction SilentlyContinue
        if ($initExit -ne 0) { throw "initdb 失敗（exit $initExit）" }
    }
    # ⚠️ -o 的值含空格，必須自行加引號包成單一 token。
    # Start-Process 的 -ArgumentList 只是用空白把陣列串起來，不會自動加引號，
    # 因此 "-p 55432" 會被 pg_ctl 解析成兩個參數，並把 55432 當成操作模式而失敗。
    Start-Process -FilePath "$PgBin\pg_ctl.exe" `
        -ArgumentList '-D', "`"$PgData`"", '-o', "`"-p $PgPort`"", 'start' `
        -RedirectStandardOutput "$LogDir\pg.log" -RedirectStandardError "$LogDir\pg.err" `
        -WindowStyle Hidden

    # 必須實際確認啟動成功——先前這裡無條件印出「已運行」，
    # 導致 pg_ctl 失敗被完全掩蓋，直到登入時才以 DB 連線逾時的形式爆出來。
    $pgDeadline = (Get-Date).AddSeconds(30)
    $ready = $false
    while ((Get-Date) -lt $pgDeadline -and -not $ready) {
        Start-Sleep -Seconds 1
        $ready = (& "$PgBin\pg_isready.exe" -h 127.0.0.1 -p $PgPort 2>&1) -match 'accepting'
    }
    if (-not $ready) {
        throw @"
PostgreSQL 啟動失敗（$PgPort 埠無回應）。
請查看： $LogDir\pg.err
"@
    }
}
Write-Ok "PostgreSQL 已在 127.0.0.1:$PgPort 運行"

$env:PGPASSWORD = 'caluli'
foreach ($dbName in @('caluli_dev', 'caluli_test')) {
    & "$PgBin\createdb.exe" -h 127.0.0.1 -p $PgPort -U caluli $dbName 2>&1 | Out-Null
}
Write-Ok '資料庫 caluli_dev / caluli_test 就緒'

# -------------------------------------------------- migration 與種子
Write-Step 'Migration 與種子資料'
Push-Location "$Root\backend"
try {
    uv run alembic upgrade head 2>&1 | Select-String 'Running upgrade|already at' | Out-Null
    Write-Ok 'Migration 已套用'
    uv run python -m app.scripts.seed_foods 2>&1 | Select-String '匯入完成'
}
finally { Pop-Location }

# -------------------------------------------------------------- 服務
$venvPython = "$Root\backend\.venv\Scripts\python.exe"

Write-Step '啟動服務'

Start-Process -FilePath $venvPython `
    -ArgumentList '-m', 'uvicorn', 'stub:app', '--port', '8900' `
    -WorkingDirectory "$Root\tools\recognition-stub" `
    -RedirectStandardOutput "$LogDir\stub.log" -RedirectStandardError "$LogDir\stub.err" `
    -WindowStyle Hidden
Write-Ok '辨識 stub  → http://localhost:8900'

# 刻意不加 --reload：reload 模式會多開一個 watcher 父程序，殺掉子程序後
# 父程序又立刻重生，導致 -Stop 清不乾淨 8000 埠。手動測試期間不需熱重載，
# 改動後端程式碼時重跑本腳本即可。
Start-Process -FilePath $venvPython `
    -ArgumentList '-m', 'uvicorn', 'app.main:app', '--port', '8000' `
    -WorkingDirectory "$Root\backend" `
    -RedirectStandardOutput "$LogDir\api.log" -RedirectStandardError "$LogDir\api.err" `
    -WindowStyle Hidden
Write-Ok '後端 API   → http://localhost:8000  (docs: /docs)'

$webScript = if ($Https) { 'dev:https' } else { 'dev' }
$webScheme = if ($Https) { 'https' } else { 'http' }

# ⚠️ 3000 埠被佔用時，Next.js 會**靜默改用其他埠**（例如 3002）。
# 那會讓 redirect_uri 與 LINE 後台設定的 Callback URL 不符，登入必然失敗，
# 而且錯誤訊息在 LINE 端，很難聯想到是埠號問題。此處明確擋下。
$occupied = Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue
if ($occupied) {
    $pids = ($occupied | Select-Object -ExpandProperty OwningProcess -Unique) -join ', '
    throw @"
3000 埠已被佔用（PID: $pids），Next.js 會改用其他埠而導致 LINE 登入的
redirect_uri 不符。請先執行：
    .\scripts\dev-up.ps1 -Stop
"@
}

Start-Process -FilePath 'npm.cmd' -ArgumentList 'run', $webScript `
    -WorkingDirectory "$Root\frontend" `
    -RedirectStandardOutput "$LogDir\web.log" -RedirectStandardError "$LogDir\web.err" `
    -WindowStyle Hidden
Write-Ok "前端       → ${webScheme}://localhost:3000"

# -------------------------------------------------------------- 驗證
Write-Step '等待服務就緒'
$deadline = (Get-Date).AddSeconds(60)
$apiUp = $false
$webUp = $false
while ((Get-Date) -lt $deadline -and -not ($apiUp -and $webUp)) {
    Start-Sleep -Seconds 2
    if (-not $apiUp) {
        try { Invoke-WebRequest 'http://127.0.0.1:8000/healthz' -UseBasicParsing -TimeoutSec 2 | Out-Null; $apiUp = $true } catch {}
    }
    if (-not $webUp) {
        # 自簽憑證會讓 Invoke-WebRequest 憑證驗證失敗；只要連得上就算就緒。
        try {
            Invoke-WebRequest "${webScheme}://localhost:3000/login" -UseBasicParsing -TimeoutSec 2 | Out-Null
            $webUp = $true
        }
        catch {
            if ($_.Exception.Message -match '信任|trust|SSL|憑證|certificate') { $webUp = $true }
        }
    }
}

if ($apiUp) { Write-Ok '後端健康檢查通過' } else { Write-Warn2 "後端未就緒，見 $LogDir\api.err" }
if ($webUp) { Write-Ok '前端已可存取' } else { Write-Warn2 "前端未就緒，見 $LogDir\web.err" }

# 再次確認 Next 真的落在 3000（而非被擠到 3002 等其他埠）。
$portNote = Get-Content "$LogDir\web.log" -ErrorAction SilentlyContinue |
    Select-String 'using available port (\d+) instead' |
    Select-Object -First 1
if ($portNote) {
    $actualPort = $portNote.Matches.Groups[1].Value
    Write-Warn2 "前端實際跑在 $actualPort 埠而非 3000——LINE 登入會因 redirect_uri 不符而失敗"
    Write-Warn2 '請執行 .\scripts\dev-up.ps1 -Stop 後重試'
    $webUp = $false
}

# ------------------------------------------------------- LIFF 設定提醒
# 未設定時 Select-String 沒有比對結果，直接取 .Matches 會是 null，需先判斷。
$liffMatch = Get-Content "$Root\frontend\.env.local" |
    Select-String '^NEXT_PUBLIC_LIFF_ID=(.+)$' |
    Select-Object -First 1
$liffId = if ($liffMatch) { $liffMatch.Matches.Groups[1].Value.Trim() } else { '' }

if ($liffId) {
    Write-Ok "LIFF ID 已設定（$liffId）—— 可測試 LIFF 入口"
}
else {
    Write-Host "`n   註：NEXT_PUBLIC_LIFF_ID 尚未設定 —— 目前一律走「一般網頁」模式。" -ForegroundColor DarkGray
    Write-Host "       這是合法狀態，可直接測試網頁入口；要測 LIFF 需先建立 LIFF app。" -ForegroundColor DarkGray
}

if (-not $Https) {
    Write-Host "`n   註：LINE Login 的 Callback URL 不接受 http。要測試網頁登入入口，" -ForegroundColor DarkGray
    Write-Host "       請改用 .\scripts\dev-up.ps1 -Https" -ForegroundColor DarkGray
}

Write-Host "`n開始測試： ${webScheme}://localhost:3000/login" -ForegroundColor White
Write-Host "關閉服務： .\scripts\dev-up.ps1 -Stop`n" -ForegroundColor DarkGray

# 明確設定結束碼——否則會沿用最後一個原生指令（npm/uv）的 $LASTEXITCODE。
if ($apiUp -and $webUp) { exit 0 } else { exit 1 }











