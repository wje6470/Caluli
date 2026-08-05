# 交給主機上 Claude 的部署任務指示

> **使用方式**:把下面「任務指示」那一整段(從 `---` 之間)複製,
> 貼給已 SSH 連進 DigitalOcean 主機的 Claude Code。

---

## 任務指示(複製這段)

我要把 Caluli 這個專案從 Vercel + Supabase 搬到你現在所在的這台
DigitalOcean 主機上。請依照 repo 內的兩份文件執行:

- `reference/deploy-plan.md` —— 執行順序、填空表、每個階段的驗收指令
- `reference/deploy-do.md` —— 每一步的完整指令內容

**先做這件事**:把上面兩份文件**完整讀過一遍再開始動手**,尤其是
deploy-plan.md 開頭的「架構釐清」。這個專案很容易被誤解成三個獨立網站,
實際上是**一個 Next.js app(含 dashboard / restaurants / admin 三組路由)
+ 一個 FastAPI 後端 + 一個 PostgreSQL**,共用單一網域,由 nginx 依
`/api/*` 分流。不要建三個 container 或三個網域。

**執行規則**:

1. 依 Part A → G 順序執行,**每個 Part 跑完必須先跑該 Part 的「驗收」
   指令,把輸出貼給我確認,再進下一個 Part**。不要一口氣跑完。
2. 指令失敗就**停下來**,把完整錯誤訊息貼出來。不要自行猜測修復、
   不要跳過、不要改用別的做法繞過。
3. **所有 `<佔位符>` 的實際值都要向我索取**,不要自己編網域、IP、金鑰或密碼,
   也不要從 git 歷史或其他檔案裡撈。索取規則:
   - **一次只問當下這個 Part 需要的**,不要一開始就把 13 項全要走
   - 每個 Part 開始前先說「這個 Part 我需要 X、Y、Z」,讓我有時間去拿
   - 拿到之後直接寫進主機上的 `.env` 或憑證檔,`chmod 600`,
     **不要在後續對話中複述該值**
4. **不要為了存放這些值而建立任何檔案,也不要改 `.gitignore`。**
   密鑰只存在於 `backend/.env`、`frontend/.env.local`、
   `/etc/ssl/caluli/` 這幾個既有位置。動 git 之前先跑 `git status`
   確認沒有把它們列進去。
5. Part C(從 Supabase 搬資料)是**不可逆**的一步,而且照片遺失無法復原。
   該 Part 的筆數核對與 `MISSING:` 檢查一項都不要省。
6. **切 DNS 是最後一步**。在那之前 Supabase 仍是正式資料來源。

**幾個已知會踩的地方**,執行到時請特別留意(文件內都有標註):

- 2 GB 機器要**先開 swap**,否則 `next build` 會被 OOM killer 砍掉
- Cloudflare SSL/TLS 要選 **Full (strict)**,選 Flexible 會無限重新導向
- nginx 的 `client_max_body_size` 要設 **12M**,預設 1M 會讓照片上傳回 413,
  而且錯誤只在 nginx,後端日誌完全看不到
- `Permissions-Policy` 要用 `geolocation=(self)`,不要沿用 `vercel.json`
  那份的 `geolocation=()` —— 會讓推薦餐廳頁整個壞掉
- `NEXT_PUBLIC_*` 是 **build 時寫死**進 bundle 的,改了 `.env.local`
  一定要重新 `npm run build` 才生效
- 辨識服務是**外部 API,不要自架**。金鑰錯誤時後端只會回「服務不可用」,
  不會說是認證問題,所以請照 deploy-do.md §7 先單獨 curl 驗一次金鑰
- 管理員權限**只能**靠 `ADMIN_LINE_USER_IDS`,直接改資料庫的 `role` 無效,
  下次登入就被名單覆寫

先讀文件,然後告訴我:(a) 你的執行計畫摘要,(b) **Part A 與 Part B 需要我
先準備哪些值**(只講這兩個 Part 的,後面的到時候再問),(c) 有沒有發現文件與
repo 實際狀況不符的地方。等我確認後再開始 Part A。

---

## 給你(專案擁有者)的行前檢查

貼上面那段之前,先確認這幾件事,可以省掉來回:

- [ ] 手邊拿得到:主機 IP、Cloudflare 網域(且有權改 DNS 與 SSL/TLS)
- [ ] 拿得到 LINE Developers Console 的存取權(channel ID、secret、LIFF ID)
- [ ] 拿得到辨識 API 的 `X-API-Key`
- [ ] 找得到舊的 `backend/.env`,裡面有 Supabase 的 `DATABASE_URL`;
      以及 Supabase 後台的 `service_role` key
- [ ] 舊的 Vercel / Supabase 專案**先不要動**,出事要能切回去

**密鑰怎麼給**:等它問到再給,不要預先整理成檔案放進 repo。
最敏感的三個(Supabase DB 連線字串、`service_role` key、資料庫密碼)
建議你**直接在主機的終端機裡 `export` 成環境變數**,讓它在指令中引用變數名,
這樣值不會出現在對話紀錄裡。Cloudflare 的 Origin 私鑰同理,自己在主機上
`nano /etc/ssl/caluli/origin.key` 貼進去就好。

部署過程中需要你手動操作的有三處,Claude 代替不了:
**Cloudflare DNS 與憑證**(Part B)、**LINE Developers 設定**(Part E)、
**瀏覽器實測**(Part F)。

搬完之後記得到 Supabase 後台**輪換 DB 密碼與 `service_role` key**
—— 它們在搬遷過程中曾以明文出現在主機的 shell 環境裡。
