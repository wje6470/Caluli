# 部署任務:把 Caluli 從 Vercel 搬到 DigitalOcean

> **這份文件是「執行前的填空表 + 執行順序」。**
>
> | 文件 | 用途 |
> |---|---|
> | [deploy-brief.md](deploy-brief.md) | **從這裡開始** —— 貼給主機上 Claude 的任務指示 |
> | **deploy-plan.md**(本文) | 架構釐清、待索取清單、Part A→G 執行順序與驗收 |
> | [deploy-do.md](deploy-do.md) | 每一步的完整指令內容 |
>
> **這三份都會進版控,所以全文只有佔位符,沒有任何實際的網域、IP、密碼或金鑰。**
> 實際值一律由執行者在需要的當下向使用者口頭索取,見下方「待索取清單」。
>
> **撰寫日期**:2026-08-05|**適用版本**:`main`(commit `09bf723`)

---

## ⚠️ 架構釐清(先讀這段,原版本的前提是錯的)

原本這份文件假設有「3 個 Next.js 網站、3 個 repo、3 個網域」。**實際上沒有。**

已上線 Vercel 的網頁、第二輪的推薦餐廳、第三輪的管理後台,是**同一個 Next.js
app 裡的三組路由**,共用同一份 build、同一個 repo、同一組資料庫:

| 原文件的稱呼 | 實際上是 | 路徑 |
|---|---|---|
| site1(Vercel 上線) | 第一輪頁面 | `/dashboard` `/capture` `/trends` `/profile` |
| site2(剛做好) | 第二輪推薦餐廳 | `/restaurants` `/restaurants/[storeId]` |
| site3(剛做好) | 第三輪管理後台 | `/admin` `/admin/stores/[storeId]` |

全部來自 `frontend/src/app/`,由 `npm run build` 一次產出。

**真正要部署的是這 4 個服務**(全部一個網域,由 nginx 依路徑分流):

| 服務 | 內容 | 位置 | 對外 |
|---|---|---|---|
| 前端 | Next.js 15,含上表全部頁面 | `frontend/` | `/`(經 nginx) |
| 後端 | FastAPI | `backend/` | `/api/*`(經 nginx) |
| 資料庫 | PostgreSQL 16 | 主機本機 | 不對外 |
| 辨識 | 第三方代管 API,**不需自架** | Google Cloud Run | 不適用 |

**因此下列事情不要做**:不要 clone 三個 repo、不要建三個 Dockerfile、不要
寫三份 nginx server block、不要申請三個網域。

**部署方式**:deploy-do.md 用的是 **systemd + 主機 nginx**(非 Docker)。
repo 根目錄的 `docker-compose.yml` 只給本機開發用(起 postgres 與 stub),
**不是正式環境的部署檔**,不要拿它上線。

---

## 從 repo 就能確定的資訊(不必問)

| 項目 | 值 |
|---|---|
| GitHub Repo | `https://github.com/wje6470/Caluli.git` |
| 分支 | `main` |
| Node 版本 | `20.x` |
| Python 版本 | `3.12`(用 `uv` 管理) |
| 辨識服務 URL | `https://taiwanese-food-api-528488788338.asia-east1.run.app` |

---

## 待索取清單 —— 執行者請在需要的當下向使用者索取

**這份文件會進版控,所以不要在這裡填入任何實際值。**
不要建立任何檔案來存放這些值,也不要為此改 `.gitignore` ——
用到的時候直接問使用者,拿到後只寫進主機上的 `.env`(權限 600)
或指定的憑證路徑,寫完不要在對話裡覆述。

全文使用下列佔位符,執行時逐一替換:

### A. 部署必需

| # | 佔位符 | 什麼時候要 | 使用者從哪裡拿 |
|---|---|---|---|
| 1 | `<DROPLET_IP>` | Part B(DNS) | DigitalOcean 主機的公網 IP |
| 2 | `<DOMAIN>` | Part B 起 | Cloudflare 上你擁有的網域,例 `app.example.com` |
| 3 | `<DB_PASSWORD>` | Part B | 使用者自己產:`openssl rand -base64 24` |
| 4 | `<JWT_SECRET>` | Part D | 使用者自己產:`openssl rand -base64 48`。**不可沿用 Vercel 那把** |
| 5 | `<LINE_CHANNEL_ID>` | Part D | LINE Developers → 該 channel → Basic settings(純數字) |
| 6 | `<LINE_CHANNEL_SECRET>` | Part D | 同上頁 |
| 7 | `<LIFF_ID>` | Part D | LINE Developers → LIFF 分頁,形如 `2001234567-AbCdEfGh` |
| 8 | `<RECOGNITION_API_KEY>` | Part D | 辨識 API 提供方給的 `X-API-Key` |
| 9 | Origin 憑證 + 私鑰 | Part B | Cloudflare → SSL/TLS → Origin Server → Create Certificate。**兩段 PEM 由使用者直接在主機上貼進檔案,不要經過對話** |
| 10 | `<ADMIN_LINE_USER_ID>` | Part E | 見下方註 ① |

> **註 ①**:LINE user ID 不是顯示名稱,也不是 `@` 開頭的 LINE ID,
> 而是 `U` 開頭的 33 字元字串。**要等新站上線後才拿得到**:
> 使用者用自己的帳號正常登入一次,再查
> `select line_user_id, display_name from users order by created_at desc limit 5;`
> 所以第 10 項不擋前面的步驟,Part E 再索取即可。

### B. 資料搬遷用(只在 Part C 需要,用完即作廢)

| # | 佔位符 | 使用者從哪裡拿 |
|---|---|---|
| 11 | `<SUPABASE_DB_URL>` | 舊的 `backend/.env` 的 `DATABASE_URL`,**去掉 `+psycopg`** |
| 12 | `<SUPABASE_URL>` | 舊 Supabase 專案網址,形如 `https://<ref>.supabase.co` |
| 13 | `<SUPABASE_SERVICE_KEY>` | Supabase → Project Settings → API → `service_role` |

> 第 11–13 項是最敏感的三個值(等同舊環境的完整讀寫權)。
> 建議做法:請使用者**直接在主機上** `export` 成環境變數,執行者只在指令中
> 引用變數名,不要求對方把值貼進對話。搬完之後請使用者到 Supabase 後台
> **輪換這三個憑證**。

### 索取時的規則

1. 一次只問**當下這個 Part 需要的**,不要一開始就把 13 項全要走。
2. 拿到值之後:寫進 `.env` → `chmod 600` → **不要在後續對話中重複該值**,
   也不要寫進任何會被 commit 的檔案。
3. 每個 Part 開始前先說明「這個 Part 我需要第 N 項」,讓使用者有準備。

---

## 執行順序

執行者請依 Part A → F 依序執行,**每個 Part 跑完對應的「驗收」再進下一個**。
指令失敗就停下來貼完整錯誤訊息,不要自行猜測修復或跳過。

### Part A — 主機基礎環境

照 [deploy-do.md §0](deploy-do.md) 與 [§1](deploy-do.md)。重點:

1. `free -h && nproc && df -h /` 看規格
2. **2 GB 機器必須先開 2 GB swap**,否則 `next build` 會被 OOM killer 砍掉
3. 建 `caluli` 一般使用者,服務不要用 root 跑
4. `ufw` 只開 22 / 80 / 443。**8000、3000、5432 一律不對外**
5. 確認金鑰能登入後,關掉 root 密碼登入
6. 裝 Node 20 與 uv

**驗收**
```bash
node -v                  # v20.x
uv --version             # 有版本號
sudo ufw status          # 只有 22/80/443
swapon --show            # 2 GB 機器要看到 /swapfile
```

---

### Part B — 網域、憑證、資料庫

照 [deploy-do.md §2](deploy-do.md) 與 [§3](deploy-do.md)。
**本 Part 需索取**:`<DROPLET_IP>`、`<DOMAIN>`、`<DB_PASSWORD>`、Origin 憑證。

1. Cloudflare 新增 A 記錄 → `<DROPLET_IP>`,Proxy 開啟(橘色雲)
2. SSL/TLS 模式選 **Full (strict)**
   —— 選 Flexible 會無限重新導向,選 Full(非 strict)等於沒有中間人防護
3. 貼上 Origin 憑證到 `/etc/ssl/caluli/origin.pem` 與 `origin.key`,`chmod 600` 私鑰
4. 建立 PostgreSQL 使用者與資料庫,只聽本機

**驗收**
```bash
sudo -u postgres psql -c "\l" | grep caluli
psql "postgresql://caluli:<DB_PASSWORD>@127.0.0.1:5432/caluli" -c "select 1;"
ls -l /etc/ssl/caluli/          # origin.key 權限應為 600
```

---

### Part C — 從 Supabase 搬資料 ⚠️ 不可逆,最需謹慎

照 [deploy-do.md §4](deploy-do.md)。
**本 Part 需索取**:`<SUPABASE_DB_URL>`、`<SUPABASE_URL>`、`<SUPABASE_SERVICE_KEY>`
—— 建議請使用者直接在主機上 `export`,不要貼進對話。

**順序不能顛倒**:先搬資料庫 → 再搬照片 → **最後才切 DNS**。
切 DNS 之前 Supabase 仍是正式資料來源,中途產生的新資料要記得補搬。

1. `pg_dump` → `pg_restore`
2. **立刻核對筆數**(`users` / `meal_records` / `meal_items` / `health_profiles`),
   跟 Supabase 上同一組查詢逐項對 —— 不要只看有沒有報錯
3. 跑 `alembic upgrade head`(線上只跑過 `0001`,第二三輪的 `stores`、
   `menu_items` 兩張表還不存在)
4. `seed_foods` **不能跳過**,沒有它辨識完查不到營養值
5. 照片從 Supabase Storage 逐檔下載到 `/var/lib/caluli/photos`,路徑格式不變

**驗收**
```bash
uv run alembic current                       # 應顯示 0002
find /var/lib/caluli/photos -type f | wc -l  # 與 DB 裡 photo_path 筆數相符
# 且下載迴圈的 MISSING: 應為 0 筆
```
> 照片是使用者資料,遺失無法復原。這一步的核對不要省。

---

### Part D — 前後端上線

照 [deploy-do.md §5](deploy-do.md)、[§6](deploy-do.md)、[§8](deploy-do.md)。
**本 Part 需索取**:`<JWT_SECRET>`、`<LINE_CHANNEL_ID>`、`<LINE_CHANNEL_SECRET>`、
`<LIFF_ID>`、`<RECOGNITION_API_KEY>`(`<DOMAIN>`、`<DB_PASSWORD>` 沿用 Part B)。

辨識是外部 API,**這台不用架**,所以只需要 **2 個** systemd 服務:
`caluli-api`、`caluli-web`。照 [deploy-do.md §7](deploy-do.md) 先單獨
`curl` 驗一次 API 金鑰再往下走 —— 金鑰錯誤時後端只回「服務不可用」,
不會告訴你是認證問題。

`backend/.env` 重點:
```ini
DATABASE_URL=postgresql+psycopg://caluli:<DB_PASSWORD>@127.0.0.1:5432/caluli
JWT_SECRET=<JWT_SECRET>
LINE_CHANNEL_ID=<LINE_CHANNEL_ID>
LINE_CHANNEL_SECRET=<LINE_CHANNEL_SECRET>

RECOGNITION_SERVICE_URL=https://taiwanese-food-api-528488788338.asia-east1.run.app
RECOGNITION_API_KEY=<RECOGNITION_API_KEY>
RECOGNITION_TIMEOUT_SECONDS=30

# ⚠️ 兩者留空才會走本機檔案系統。只要有一個有值就會繼續打 Supabase
#    (photo_storage.py 的 get_photo_storage() 依此判斷)
SUPABASE_URL=
SUPABASE_SERVICE_KEY=
PHOTO_STORAGE_ROOT=/var/lib/caluli/photos

SERVERLESS=false
ADMIN_LINE_USER_IDS=          # Part E 才補,見待索取清單註 ①
```
```bash
chmod 600 /home/caluli/Caluli/backend/.env
```

`frontend/.env.local` 重點 —— **`NEXT_PUBLIC_*` 在 `next build` 時寫死進
bundle**,不是執行時讀取,改完必須重新 build:
```ini
NEXT_PUBLIC_API_BASE_URL=/api/v1        # 同源,相對路徑,換網域不必重 build
NEXT_PUBLIC_LIFF_ID=<LIFF_ID>
NEXT_PUBLIC_LINE_CHANNEL_ID=<LINE_CHANNEL_ID>
NEXT_PUBLIC_LINE_REDIRECT_URI=https://<DOMAIN>/auth/callback
```

nginx 設定照 §8 全文貼。**兩個最容易漏的**:
- `client_max_body_size 12M` —— 預設 1M,照片上限 10M,不改上傳會回 413,
  且錯誤發生在 nginx,後端日誌什麼都看不到
- `Permissions-Policy` 的 `geolocation=(self)` —— 沿用 `vercel.json` 的
  `geolocation=()` 會讓第二輪推薦店家整條壞掉

**驗收**
```bash
sudo systemctl status caluli-api caluli-web --no-pager   # 兩個都 active (running)
sudo nginx -t                                            # syntax is ok
curl -sI http://127.0.0.1:3000 | head -1                 # 200
curl -s http://127.0.0.1:8000/api/v1/stores | head -c 200
sudo ss -tlnp | grep -E '3000|8000'                      # 都應只綁 127.0.0.1
```

---

### Part E — LINE 設定與管理員授權

照 [deploy-do.md §9](deploy-do.md)。此部分需在 LINE Developers Console 手動操作。
**本 Part 需索取**:`<ADMIN_LINE_USER_ID>`(到這一步才拿得到)。

1. **LINE Login → Callback URL** 新增 `https://<DOMAIN>/auth/callback`
   —— 必須與 `NEXT_PUBLIC_LINE_REDIRECT_URI` **逐字相同**(含 `https`、
   結尾不加斜線)。舊的 Vercel 那筆先留著,確認新站沒問題再刪
2. **LIFF → Endpoint URL** 改成 `https://<DOMAIN>`,Scopes 保留 `profile`, `openid`
3. 用自己的帳號登入一次 → 查出 LINE user ID → 向使用者確認後填進
   `ADMIN_LINE_USER_IDS` → `sudo systemctl restart caluli-api` → **登出再登入**

> ⚠️ 直接在資料庫把 `role` 改成 `admin` **是無效的**,下次登入會被名單覆寫。
> 授予一律走 `ADMIN_LINE_USER_IDS`。

**驗收**
```bash
psql "postgresql://caluli:<DB_PASSWORD>@127.0.0.1:5432/caluli" -c \
  "select line_user_id, display_name, role from users order by created_at desc limit 5;"
# 你的帳號 role 應為 admin
```

---

### Part F — 最終驗收

照 [deploy-do.md §10](deploy-do.md)。DNS 切過去之後:

```bash
curl -sI https://<DOMAIN> | head -3                       # 200,憑證有效
curl -s https://<DOMAIN>/api/v1/stores | head -c 200      # 後端活著
```

瀏覽器手動走一遍(**這一段不能只看 curl**):

- [ ] 一般瀏覽器開 `https://<DOMAIN>` → LINE 登入 → 進 `/dashboard`
- [ ] `/restaurants` 定位權限有跳出來(沒跳 = `Permissions-Policy` 沒改對)
- [ ] `/trends` 圖表正常
- [ ] LINE App 內開 LIFF → 同一個帳號、同一份資料
- [ ] 管理員開 `/admin` → 看得到店家清單
- [ ] 一般使用者開 `/admin` → 被擋(403)
- [ ] **舊照片顯示得出來**(驗證 Part C 搬對了)
- [ ] 拍照上傳 → 辨識 → 存得起來(打的是外部 API,不是 stub)
- [ ] 重啟後端(`sudo systemctl restart caluli-api`)後前端仍可用

---

## Part G — 收尾(上線後,不要當天做)

照 [deploy-do.md §11](deploy-do.md)。

**備份**:搬到自架之後備份是你的責任,Supabase 不再幫你做。設定
`/etc/cron.daily/caluli-backup`,並**至少往另一台機器或 DO Spaces 同步一份**
—— 備份放在同一台等於沒備份。

**舊環境退役(確認新站穩定運行數天之後)**:
1. Vercel 兩個專案先設為停止部署,**不要立刻刪** —— 出事要能切回去
2. 移除 LINE Callback URL 的舊 Vercel 那筆
3. 暫停 Supabase 專案前,再確認一次照片與資料都在新機上
4. **輪換金鑰**:Supabase DB 密碼與 `service_role` key 在搬遷過程中曾以明文
   出現在主機的 shell 環境與 `.env` 中,退役時一併作廢

## 已知待辦(不影響上線,但要記著)

- **KI-001**:第一輪數值欄位回傳字串但型別宣告為 `number`,見
  [known-issues.md](known-issues.md)。目前不會壞,但沒有機制防止它壞
- **`frontend/vercel.json`** 的 `geolocation=()` 仍是錯的。若日後還會用
  Vercel 部署,那個檔案也要一起改
- **辨識逾時 30s** 是暫定值(OQ-4),上線後以 `recognition_jobs.duration_ms`
  的實測值校準
