# DigitalOcean 單機部署指南

把 Caluli 從 Vercel + Supabase 搬到一台 DigitalOcean Droplet，回到
[plan.md](../specs/001-diet-log-mvp/plan.md) 原本設定的「單台 Linux 伺服器」架構。

**適用版本**：`main`（第一、二、三輪已合併，commit `82da7ff`）
**撰寫日期**：2026-08-04

---

## 佔位符

全文用這幾個佔位符，開始前先決定並全域取代：

| 佔位符 | 意義 | 範例 |
|---|---|---|
| `example.com` | 你在 Cloudflare 的網域 | `caluli.app` |
| `app.example.com` | 對外服務的完整網域 | `app.caluli.app` |
| `<DROPLET_IP>` | Droplet 的公網 IP | `159.65.x.x` |
| `<DB_PASSWORD>` | 新的本機 PostgreSQL 密碼 | 自行產生 |

前端與後端**共用同一個網域**，由 nginx 依路徑分流（`/api/*` 給後端，其餘給前端）。
這樣做的理由：同源之後 CORS 完全不存在，`NEXT_PUBLIC_API_BASE_URL` 可以寫成
相對路徑 `/api/v1`，日後換網域也不必重新 build 前端。

---

## 0. 先確認 Droplet 規格

```bash
free -h && nproc && df -h /
```

最低要求，分兩個階段看：

| 用途 | RAM | 說明 |
|---|---|---|
| 前端 + 後端 + PostgreSQL + stub | 2 GB | 可行，但 `next build` 可能 OOM，需先開 swap |
| 加上真的 YOLO + HF 模型 | 未知 | 模型還沒寫，大小未定。**先不要為此升規格** |

`next build` 在 2 GB 機器上容易被 OOM killer 砍掉。先開 swap：

```bash
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

> 另一條路是在本機 build 完把 `.next` 傳上去，就不必在 Droplet 上跑 build。
> 但 `NEXT_PUBLIC_*` 是 build 時寫死的（見第 6 節），本機 build 必須用正式值。

---

## 1. Droplet 基礎設定

假設 Ubuntu 24.04。以 root 登入後：

```bash
# 建一般使用者，之後不要用 root 跑服務
adduser caluli && usermod -aG sudo caluli
rsync --archive --chown=caluli:caluli ~/.ssh /home/caluli/

apt update && apt upgrade -y
apt install -y nginx postgresql-16 postgresql-contrib git curl ufw fail2ban
```

防火牆。**只開 22/80/443**，8000 / 3000 / 8900 / 5432 一律不對外：

```bash
ufw allow OpenSSH && ufw allow 80 && ufw allow 443
ufw --force enable
```

停用 root 密碼登入（確認金鑰能登入之後再做）：

```bash
sed -i 's/^#*PermitRootLogin.*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config
sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart ssh
```

Node 20（前端需要）與 uv（後端需要）：

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
curl -LsSf https://astral.sh/uv/install.sh | sh    # 以 caluli 身分執行
```

---

## 2. Cloudflare DNS 與憑證

### 2.1 DNS

Cloudflare → 你的網域 → DNS → 新增：

| Type | Name | Content | Proxy |
|---|---|---|---|
| A | `app` | `<DROPLET_IP>` | 🟠 Proxied |

### 2.2 SSL/TLS 模式（最容易踩的一步）

Cloudflare → SSL/TLS → Overview → 選 **Full (strict)**。

- 選 **Flexible** 會造成無限重新導向，而且 Cloudflare 到你伺服器那段是明文
- 選 **Full**（非 strict）不驗證origin憑證，等於中間人攻擊沒有防護

同頁的 Edge Certificates → **Always Use HTTPS** 開啟。

### 2.3 Origin Certificate

因為 Proxy 開著，用 Cloudflare 自己簽的 origin 憑證最省事，有效期 15 年、
不必處理 Let's Encrypt 的續期。

Cloudflare → SSL/TLS → Origin Server → Create Certificate，
hostname 填 `app.example.com` 與 `*.example.com`，產生後把兩段貼到伺服器：

```bash
sudo mkdir -p /etc/ssl/caluli
sudo nano /etc/ssl/caluli/origin.pem   # 貼 Origin Certificate
sudo nano /etc/ssl/caluli/origin.key   # 貼 Private Key
sudo chmod 600 /etc/ssl/caluli/origin.key
```

> ⚠️ Origin Certificate **只有 Cloudflare 認得**。直接用 IP 或關掉 Proxy 存取
> 會出現憑證錯誤，那是正常的，不是設定壞掉。

---

## 3. PostgreSQL

```bash
sudo -u postgres psql <<'SQL'
CREATE USER caluli WITH PASSWORD '<DB_PASSWORD>';
CREATE DATABASE caluli OWNER caluli;
\c caluli
CREATE EXTENSION IF NOT EXISTS pgcrypto;
SQL
```

只聽本機即可（預設就是），不要開 `listen_addresses = '*'`。

---

## 4. 從 Supabase 搬資料

**順序很重要**：先搬資料庫，再搬照片，最後才切 DNS。切 DNS 之前
Supabase 仍然是正式資料來源，中途產生的新資料要記得補搬。

### 4.1 資料庫

在 Droplet 上（`pg_dump` 版本要 ≥ 來源）：

```bash
# 來源字串取自 backend/.env 的 DATABASE_URL，但要去掉 +psycopg
export SRC="postgresql://postgres.<ref>:<pw>@aws-0-ap-northeast-1.pooler.supabase.com:5432/postgres?sslmode=require"

pg_dump "$SRC" \
  --no-owner --no-privileges --no-acl \
  --schema=public \
  -Fc -f caluli-$(date +%Y%m%d).dump

pg_restore --no-owner --no-privileges \
  -d "postgresql://caluli:<DB_PASSWORD>@127.0.0.1:5432/caluli" \
  caluli-$(date +%Y%m%d).dump
```

restore 完**立刻核對筆數**，不要只看有沒有報錯：

```bash
psql "postgresql://caluli:<DB_PASSWORD>@127.0.0.1:5432/caluli" -c \
"select 'users' t, count(*) from users
 union all select 'meal_records', count(*) from meal_records
 union all select 'meal_items', count(*) from meal_items
 union all select 'health_profiles', count(*) from health_profiles;"
```

跟 Supabase 上同一組查詢的結果逐項對。

### 4.2 補上第二、三輪的 migration

線上目前只跑過 `0001`，`stores` 與 `menu_items` 兩張表還不存在。
第 5 節設定完後端 `.env` 之後執行：

```bash
cd ~/Caluli/backend && uv run alembic upgrade head
uv run alembic current      # 應顯示 0002
```

店家種子資料（可選，正式環境通常自己用後台建）：

```bash
uv run python -m app.scripts.seed_foods    # 通用食物營養對照表，必要
uv run python -m app.scripts.seed_stores   # 測試店家，正式站建議跳過
```

`seed_foods` **不能跳過**——沒有它辨識完查不到營養值。

### 4.3 照片

線上照片存在 Supabase Storage 的 `meal-photos` bucket，DB 只存相對路徑。
搬到本機檔案系統後，路徑格式不變，所以只要把檔案照原路徑放好即可。

```bash
sudo mkdir -p /var/lib/caluli/photos
sudo chown caluli:caluli /var/lib/caluli/photos
```

先把 DB 裡的路徑列出來：

```bash
psql "postgresql://caluli:<DB_PASSWORD>@127.0.0.1:5432/caluli" -tAc \
  "select photo_path from meal_records where photo_path is not null;" > /tmp/photos.txt
wc -l /tmp/photos.txt
```

逐一從 Supabase 下載（`SUPABASE_URL` 與 service key 取自 `backend/.env`）：

```bash
export SB_URL="https://<ref>.supabase.co"
export SB_KEY="<service_role_key>"

while read -r p; do
  [ -z "$p" ] && continue
  mkdir -p "/var/lib/caluli/photos/$(dirname "$p")"
  curl -sf -H "Authorization: Bearer $SB_KEY" -H "apikey: $SB_KEY" \
    "$SB_URL/storage/v1/object/meal-photos/$p" \
    -o "/var/lib/caluli/photos/$p" || echo "MISSING: $p"
done < /tmp/photos.txt
```

跑完檢查 `MISSING:` 有幾筆，以及檔案數對不對：

```bash
find /var/lib/caluli/photos -type f | wc -l
```

> 照片是使用者資料，遺失無法復原。這一步的核對不要省。

---

## 5. 後端

```bash
sudo -u caluli git clone <your-repo-url> /home/caluli/Caluli
cd /home/caluli/Caluli/backend && uv sync
```

`/home/caluli/Caluli/backend/.env`：

```ini
# 本機 PostgreSQL。注意不是 6543，也不要有 pgbouncer 參數——
# 這台是長時運行的 uvicorn，走一般連線 + SQLAlchemy 連線池。
DATABASE_URL=postgresql+psycopg://caluli:<DB_PASSWORD>@127.0.0.1:5432/caluli

# ⚠️ 產生一組全新的，不要沿用 Vercel 上那把。
# 換掉會讓所有現有登入失效，使用者需重新登入一次——這是可接受的。
JWT_SECRET=<openssl rand -base64 48 產生>
JWT_EXPIRES_SECONDS=604800

LINE_CHANNEL_ID=2010915096
LINE_CHANNEL_SECRET=<照舊>

RECOGNITION_SERVICE_URL=http://127.0.0.1:8900
RECOGNITION_TIMEOUT_SECONDS=30

# ⚠️ 兩者留空才會走本機檔案系統。只要有一個有值就會繼續打 Supabase
#（見 photo_storage.py:132 的判斷）。
SUPABASE_URL=
SUPABASE_SERVICE_KEY=
PHOTO_STORAGE_ROOT=/var/lib/caluli/photos
PHOTO_MAX_BYTES=10485760

NEARBY_RADIUS_KM=5.0
NEARBY_LIMIT=10

# 第三輪：可進後台的 LINE user ID，半形逗號分隔。
# 留空 = 沒有人是管理員，後台誰都進不去。
ADMIN_LINE_USER_IDS=<你的 LINE user ID>

# 這台是長時運行的伺服器，不是 serverless。
SERVERLESS=false
APP_TIMEZONE=Asia/Taipei

# 同源部署後 CORS 其實用不到，但留著以防日後前後端分家。
CORS_ORIGINS=["https://app.example.com"]
```

```bash
chmod 600 /home/caluli/Caluli/backend/.env
```

systemd unit `/etc/systemd/system/caluli-api.service`：

```ini
[Unit]
Description=Caluli FastAPI
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=exec
User=caluli
WorkingDirectory=/home/caluli/Caluli/backend
ExecStart=/home/caluli/.local/bin/uv run uvicorn app.main:app \
  --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

`--host 127.0.0.1` 是刻意的：後端只能經 nginx 存取，不對外開。

---

## 6. 前端

`NEXT_PUBLIC_*` 會在 `next build` 時**寫死進 bundle**，不是執行時讀取。
所以這些值必須在 build 之前設好，日後要改就得重新 build。

`/home/caluli/Caluli/frontend/.env.local`：

```ini
# 同源，走相對路徑。換網域不必重 build。
NEXT_PUBLIC_API_BASE_URL=/api/v1

NEXT_PUBLIC_LIFF_ID=<LIFF app ID，形如 2010915096-AbCdEfGh>
NEXT_PUBLIC_LINE_CHANNEL_ID=2010915096
NEXT_PUBLIC_LINE_REDIRECT_URI=https://app.example.com/auth/callback

# 只在 development 生效，正式 build 中永遠無效，留 false 即可
NEXT_PUBLIC_DEV_FORCE_LIFF=false
```

```bash
cd /home/caluli/Caluli/frontend
npm ci
npm run build
```

systemd unit `/etc/systemd/system/caluli-web.service`：

```ini
[Unit]
Description=Caluli Next.js
After=network.target

[Service]
Type=exec
User=caluli
WorkingDirectory=/home/caluli/Caluli/frontend
Environment=NODE_ENV=production
ExecStart=/usr/bin/npm run start -- --port 3000 --hostname 127.0.0.1
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

---

## 7. 辨識服務（目前是 stub）

真服務還沒寫。先把 stub 掛上去，讓拍照流程不會整條斷掉：

```bash
cd /home/caluli/Caluli/tools/recognition-stub && uv sync
```

`/etc/systemd/system/caluli-recognition.service`：

```ini
[Unit]
Description=Caluli Recognition (STUB - 尚未接真模型)
After=network.target

[Service]
Type=exec
User=caluli
WorkingDirectory=/home/caluli/Caluli/tools/recognition-stub
Environment=STUB_DEFAULT_MODE=normal
ExecStart=/home/caluli/.local/bin/uv run uvicorn stub:app \
  --host 127.0.0.1 --port 8900
Restart=always

[Install]
WantedBy=multi-user.target
```

> ⚠️ **stub 回傳的是假辨識結果**。正式對外之前要想清楚：是要先關閉拍照
> 入口，還是明確告知使用者辨識功能尚未開放。讓真實使用者拿到假結果並
> 存進自己的飲食紀錄，比功能不開放更糟。
>
> 真服務就緒後，接觸點集中在
> [recognition_client.py](../backend/app/services/recognition_client.py)
> 一個模組（OQ-3 的隔離措施），換掉那裡的解析邏輯即可，其餘不受影響。

啟動三個服務：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now caluli-api caluli-web caluli-recognition
sudo systemctl status caluli-api caluli-web caluli-recognition --no-pager
```

---

## 8. nginx

`/etc/nginx/sites-available/caluli`：

```nginx
# Cloudflare 的來源 IP 還原，否則日誌裡全是 Cloudflare 的 IP。
# 清單見 https://www.cloudflare.com/ips/ ，變動不頻繁但需偶爾更新。
set_real_ip_from 173.245.48.0/20;
set_real_ip_from 103.21.244.0/22;
set_real_ip_from 103.22.200.0/22;
set_real_ip_from 103.31.4.0/22;
set_real_ip_from 141.101.64.0/18;
set_real_ip_from 108.162.192.0/18;
set_real_ip_from 190.93.240.0/20;
set_real_ip_from 188.114.96.0/20;
set_real_ip_from 197.234.240.0/22;
set_real_ip_from 198.41.128.0/17;
set_real_ip_from 162.158.0.0/15;
set_real_ip_from 104.16.0.0/13;
set_real_ip_from 104.24.0.0/14;
set_real_ip_from 172.64.0.0/13;
set_real_ip_from 131.0.72.0/22;
real_ip_header CF-Connecting-IP;

server {
    listen 80;
    server_name app.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name app.example.com;

    ssl_certificate     /etc/ssl/caluli/origin.pem;
    ssl_certificate_key /etc/ssl/caluli/origin.key;
    ssl_protocols TLSv1.2 TLSv1.3;

    # ⚠️ 預設是 1M，照片上限是 10M。不改的話上傳會回 413，
    #    而且錯誤發生在 nginx，後端日誌什麼都看不到。
    client_max_body_size 12M;

    # 沿用 vercel.json 的安全標頭，但 geolocation 必須改成 (self)——
    # 原本的 geolocation=() 會停用定位，第二輪的推薦店家整條壞掉。
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Permissions-Policy "camera=(self), microphone=(), geolocation=(self), payment=()" always;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_read_timeout 90s;    # 辨識逾時是 30s，留餘裕
    }

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/caluli /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

---

## 9. LINE 設定

LINE Developers Console → 你的 Provider → channel `2010915096`。

### 9.1 LINE Login

**Callback URL** 新增（舊的 Vercel 那筆先留著，確認新站沒問題再刪）：

```
https://app.example.com/auth/callback
```

必須逐字相同：含 `https`、不加結尾斜線，且與 `NEXT_PUBLIC_LINE_REDIRECT_URI` 一致。

### 9.2 LIFF

LIFF 分頁 → 編輯既有的 LIFF app：

| 欄位 | 值 |
|---|---|
| Endpoint URL | `https://app.example.com` |
| Size | 依現況（`Full` 通常最合適） |
| Scopes | `profile`, `openid` |

把 LIFF ID 填回 `frontend/.env.local` 的 `NEXT_PUBLIC_LIFF_ID`，然後
**重新 build 前端**（build 時寫死，改 .env 不重 build 不會生效）。

### 9.3 管理員後台不走 LIFF

後台網址直接給管理員，用一般瀏覽器開：

```
https://app.example.com/admin
```

管理員在這裡走的是**一般網頁 OAuth**（不是 LIFF），登入後
[line_auth.py](../backend/app/services/line_auth.py) 的 `upsert_user()`
會拿 LINE 回傳的 `sub` 去核對 `ADMIN_LINE_USER_IDS`，命中才給 admin。

取得自己 LINE user ID 的方式：先用該帳號正常登入一次，然後查

```bash
psql "postgresql://caluli:<DB_PASSWORD>@127.0.0.1:5432/caluli" -c \
  "select line_user_id, display_name, role from users order by created_at desc limit 5;"
```

把 ID 填進 `.env` 的 `ADMIN_LINE_USER_IDS`，`sudo systemctl restart caluli-api`，
再登出重新登入一次即生效。

> ⚠️ 直接在資料庫把 `role` 改成 `admin` **是無效的**——下次登入就會被名單覆寫
> （見 [admin_roles.py](../backend/app/services/admin_roles.py) 的說明）。授予一律走名單。

---

## 10. 上線驗證

DNS 切過去之後，依序確認：

```bash
# 1. 憑證與導轉
curl -sI https://app.example.com | head -3

# 2. 後端活著
curl -s https://app.example.com/api/v1/stores | head -c 200

# 3. 上傳大小限制沒擋（應該是 401 而不是 413）
curl -s -o /dev/null -w '%{http_code}\n' -X POST \
  https://app.example.com/api/v1/recognitions \
  -F "photo=@$(mktemp).jpg"
```

瀏覽器上要手動走一遍：

- [ ] 一般瀏覽器開 `https://app.example.com` → LINE 登入 → 進 dashboard
- [ ] `/restaurants` 定位權限有跳出來（沒跳 = `Permissions-Policy` 沒改對）
- [ ] LINE App 內開 LIFF → 同一個帳號、同一份資料
- [ ] 管理員開 `/admin` → 看得到店家清單
- [ ] 一般使用者開 `/admin` → 被擋（403）
- [ ] 舊照片顯示得出來（驗證第 4.3 節搬對了）
- [ ] 拍照上傳 → 存得起來（辨識結果目前是 stub 的假資料）

---

## 11. 收尾

### 備份

搬到自架之後備份是你的責任了，Supabase 不再幫你做。

`/etc/cron.daily/caluli-backup`：

```bash
#!/bin/sh
set -e
D=/var/backups/caluli
mkdir -p "$D"
pg_dump "postgresql://caluli:<DB_PASSWORD>@127.0.0.1:5432/caluli" \
  -Fc -f "$D/db-$(date +%Y%m%d).dump"
tar czf "$D/photos-$(date +%Y%m%d).tar.gz" -C /var/lib/caluli photos
find "$D" -type f -mtime +14 -delete
```

備份放在同一台等於沒備份——Droplet 掛了兩份一起沒。至少要往
DO Spaces 或其他機器同步一份。DO 的 Droplet Backup（每週快照）也建議開。

### 舊環境退役

確認新站穩定運行**數天**之後再動：

1. Vercel 兩個專案先設為停止部署，不要立刻刪 —— 出事要能切回去
2. LINE Callback URL 移除舊的 Vercel 那筆
3. Supabase 專案暫停前，先確認照片與資料都在新機上
4. **輪換金鑰**：Supabase 的 DB 密碼與 `service_role` key 曾寫在
   `backend/.env`，退役時一併作廢

### 已知待辦

- **辨識服務**：真模型尚未實作，目前是 stub（OQ-3）
- **KI-001**：第一輪數值欄位回傳字串但型別宣告為 number，見
  [known-issues.md](known-issues.md)。目前不會壞，但沒有機制防止它壞
- **`geolocation=()`**：`frontend/vercel.json` 那份仍是錯的。若日後還會用
  Vercel 部署，那個檔案也要一起改
