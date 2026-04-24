# oddlot — AI 台股零股選股平台

🌐 **線上體驗：** https://dragondaddy2021.github.io/oddlot

oddlot 是一個以 AI 驅動的台股零股投資參考平台。每日從台灣證券交易所（TWSE）抓取上市股票資料，由 Claude AI 篩選出適合零股長期投資的標的，並提供殖利率、本益比、推薦理由等參考資訊。

> ⚠️ **免責聲明：本平台所有資訊由 AI 自動產生，僅供參考，不構成任何投資建議。投資人須自行評估風險，本平台不負任何投資損失責任。**

---

## 功能介紹

- **今日 AI 選股**：每日自動從 TWSE 取得股票資料，經 Claude AI 篩選出 10 檔適合零股投資的標的
- **選股理由**：每檔股票附有 AI 產生的繁體中文推薦理由（50 字以內）
- **收藏清單**：登入後可將喜歡的股票加入個人收藏，隨時查閱
- **我的 ETF**：自組個人化投資組合，可從我的最愛挑選成分股並設定權重
- **Google 登入**：透過 Supabase Auth 整合 Google OAuth，快速完成身份驗證
- **快取機制**：AI 選股結果快取 24 小時，避免重複呼叫 AI API
- **PWA 支援**：可安裝至手機主畫面，像 App 一樣使用，支援 Android 與 iOS

---

## 選股邏輯

### 資料來源

- 股票資料來自 **台灣證券交易所（TWSE）** 官方公開 API，無需授權金鑰
- 使用的端點：
  - `BWIBBU_d`：每日本益比與殖利率
  - `TWT49U`：除權除息計算結果（取得除權息日、除權息前收盤價）
  - `STOCK_DAY`：個股日成交資訊（用於計算填息天數）
- 每日台股收盤後自動更新（台灣時間凌晨 2:00 執行）

### 篩選條件

- 股價 **10～500 元**（適合零股小額投資）
- 本益比 **大於 0**（排除虧損股）
- 殖利率 **大於 0**（有過去配息紀錄）
- **近 3 年每年至少配息一次**（排除不穩定配息股）
- **近 3 年至少成功填息 1 次**（排除長期無法填息的股票）
- 排除 ETF 及特殊商品（專注一般上市個股）
- 依殖利率取前 **80 檔** 計算填息資料，過濾掉近 3 年完全沒填息的股票後，最多保留 **50 檔** 送入 AI 分析

### 填息資料計算

- 以 `TWT49U` 取得每檔個股的除權息日與除權息前收盤價（baseline）
- 用 `STOCK_DAY` 往後逐月掃描，第一個收盤價 ≥ baseline 的日子即為填息日
- 最多往後追蹤 3 個月（約 90 天），逾期視為未填息
- 為每檔個股計算下列指標：
  - `avg_fill_days`：已填息事件的平均填息天數
  - `fill_rate`：填息事件數 / 除息事件數
  - `fill_samples`：樣本數（參考可信度用）
  - `last_ex_date`：近 3 年內最近一次除息日（前端顯示為「上次配息」）

### AI 分析

- 由 **Claude AI（Anthropic）** 從 50 檔候選名單中選出 10 檔
- 考量因素：殖利率穩定性、本益比合理性、產業分散度、股價親民度、填息速度與填息率
- 每檔股票附上繁體中文推薦理由（50 字以內）

### 已知限制

- **產業集中風險**：篩選第一步依殖利率由高到低排序，名單容易集中在營造、金融等高殖利率的**景氣循環股**。AI 雖會參考產業分散度，但不保證涵蓋所有產業，使用者需自行評估組合分散度
- **景氣循環股陷阱**：營造、航運等產業獲利波動大，過去高殖利率常是獲利高峰年的結果，**不代表未來可持續配息**
- **財務指標有限**：未考慮負債比率、現金流、營收成長等財務健康指標
- **單日快照**：僅分析當日資料，未考慮歷史趨勢與股價走勢
- **建議搭配**：本平台名單適合作為**殖利率型標的候選池**，建議搭配其他類型股票（金融、電信、民生、科技等）建構分散的個人投資組合

---

## 技術架構

| 層次       | 技術                                      |
|------------|-------------------------------------------|
| 前端       | React 18 + Vite + Tailwind CSS            |
| PWA        | vite-plugin-pwa（可安裝至手機主畫面）     |
| 後端       | Python FastAPI + uvicorn                  |
| 資料庫     | Supabase（PostgreSQL + Row Level Security）|
| 快取       | Upstash Redis（TTL 86400 秒）             |
| AI         | Anthropic Claude claude-haiku-4-5-20251001|
| 股票資料   | TWSE BWIBBU_d 公開 API（免金鑰）          |
| 身份驗證   | Supabase Auth（Google OAuth + ES256 JWT） |
| 限流       | slowapi（一般 60/min，AI 端點 20/hr）     |

```
oddlot/
├── frontend/          # React + Vite 前端
│   ├── public/
│   └── src/
│       ├── components/    # 共用元件（Navbar）
│       ├── hooks/         # useAuth
│       ├── lib/           # api.js、supabase.js
│       └── pages/         # Home、Favorites、Login
├── backend/           # FastAPI 後端
│   ├── main.py
│   └── app/
│       ├── api/v1/        # recommendations、favorites
│       ├── core/          # config、security、limiter
│       ├── db/            # supabase、redis
│       └── services/      # ai_selector、stock_service
├── db/migrations/     # Supabase SQL 遷移腳本
├── .env.example
├── .gitignore
├── docker-compose.yml
└── README.md
```

---

## 本地開發啟動步驟

### 前置需求

- Node.js 20+
- Python 3.11+
- Supabase 專案（含資料庫 migration 執行完成）
- Upstash Redis 帳號
- Anthropic API 金鑰

### 1. 複製並設定環境變數

```bash
git clone <repo-url>
cd oddlot
cp .env.example .env
# 在 .env 填入所有必要的金鑰與設定值（請勿提交 .env）
```

### 2. 資料庫 Migration

在 Supabase 專案的 SQL Editor 依序執行：

```
db/migrations/001_create_tables.sql
db/migrations/002_enable_rls.sql
db/migrations/003_create_indexes.sql
db/migrations/004_create_custom_etfs.sql
```

### 3. 啟動後端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
# 後端運行於 http://localhost:8000
```

### 4. 啟動前端

```bash
cd frontend
npm install
npm run dev
# 前端運行於 http://localhost:5173
```

### 5. 觸發 AI 選股（開發測試用）

```bash
curl -X POST http://localhost:8000/internal/run-daily-recommendation \
  -H "X-Cron-Secret: <INTERNAL_CRON_SECRET>"
```

---

## 環境變數說明

複製 `.env.example` 為 `.env` 並填入以下變數（請勿將 `.env` 提交至版本控制）：

| 變數名稱                    | 說明                                  |
|-----------------------------|---------------------------------------|
| `ANTHROPIC_API_KEY`         | Anthropic API 金鑰                    |
| `SUPABASE_URL`              | Supabase 專案 URL                     |
| `SUPABASE_ANON_KEY`         | Supabase anon（公開）金鑰             |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role 金鑰（後端專用）|
| `UPSTASH_REDIS_URL`         | Upstash Redis REST URL                |
| `UPSTASH_REDIS_TOKEN`       | Upstash Redis REST Token              |
| `INTERNAL_CRON_SECRET`      | 內部排程觸發用密鑰                    |
| `FINMIND_API_TOKEN`         | FinMind API Token（保留欄位，未啟用） |
| `ALLOWED_ORIGINS`           | CORS 允許的前端來源（逗號分隔）       |
| `VITE_API_BASE_URL`         | 前端 API Base URL（生產環境用）       |
| `VITE_SUPABASE_URL`         | 前端用 Supabase URL                   |
| `VITE_SUPABASE_ANON_KEY`    | 前端用 Supabase anon 金鑰             |

---

## PWA 安裝說明

oddlot 支援 PWA（Progressive Web App），可以安裝到手機主畫面，像原生 App 一樣使用。

### Android（Chrome）

1. 用 Chrome 開啟 https://dragondaddy2021.github.io/oddlot
2. 點右上角選單（⋮）→ **「新增至主畫面」**
3. 點「新增」確認

### iOS（Safari）

1. 用 Safari 開啟 https://dragondaddy2021.github.io/oddlot
2. 點下方分享按鈕（□↑）→ **「加入主畫面」**
3. 點右上角「新增」確認

### 安裝後的差異

| 功能 | 瀏覽器 | 安裝後 |
|------|:------:|:------:|
| 全螢幕顯示（無網址列）| ❌ | ✅ |
| 主畫面捷徑 | ❌ | ✅ |
| 啟動速度 | 一般 | 較快 |
| 離線瀏覽 | ❌ | ❌（需網路取得最新選股）|

---

## 免責聲明

本平台所有選股資訊皆由人工智慧（Claude AI）自動分析產生，**不構成任何形式的投資建議**。股票投資涉及市場風險，過去表現不代表未來結果。使用本平台前請詳閱相關風險，並自行負責所有投資決策與損益。

---

## GitHub Secrets 設定

前往 GitHub repo → **Settings → Secrets and variables → Actions → New repository secret**，加入以下 secrets：

| Secret 名稱 | 用途 |
|---|---|
| `ANTHROPIC_API_KEY` | Claude AI API 金鑰（每日選股 Action 使用） |
| `SUPABASE_URL` | Supabase 專案 URL（每日選股 Action 使用） |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role 金鑰（寫入資料庫用） |
| `VITE_SUPABASE_URL` | Supabase URL（前端 build 時注入） |
| `VITE_SUPABASE_ANON_KEY` | Supabase anon 金鑰（前端 build 時注入） |

> 設定完成後，推送到 main branch 即會自動觸發前端部署；每日 UTC 18:00（台灣凌晨 02:00）自動執行 AI 選股。

---

## 致謝

特別感謝選股邏輯檢視員：Wen Cheng 🐟

---

## License

[MIT License](LICENSE) © 2026 Dragon
