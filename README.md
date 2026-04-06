# oddlot — AI 台股零股選股平台

oddlot 是一個以 AI 驅動的台股零股投資參考平台。每日從台灣證券交易所（TWSE）抓取上市股票資料，由 Claude AI 篩選出適合零股長期投資的標的，並提供殖利率、本益比、推薦理由等參考資訊。

> ⚠️ **免責聲明：本平台所有資訊由 AI 自動產生，僅供參考，不構成任何投資建議。投資人須自行評估風險，本平台不負任何投資損失責任。**

---

## 功能介紹

- **今日 AI 選股**：每日自動從 TWSE 取得股票資料，經 Claude AI 篩選出 10 檔適合零股投資的標的
- **選股理由**：每檔股票附有 AI 產生的繁體中文推薦理由（50 字以內）
- **收藏清單**：登入後可將喜歡的股票加入個人收藏，隨時查閱
- **Google 登入**：透過 Supabase Auth 整合 Google OAuth，快速完成身份驗證
- **快取機制**：AI 選股結果快取 24 小時，避免重複呼叫 AI API

---

## 技術架構

| 層次       | 技術                                      |
|------------|-------------------------------------------|
| 前端       | React 18 + Vite + Tailwind CSS            |
| 後端       | Python FastAPI + uvicorn                  |
| 資料庫     | Supabase（PostgreSQL + Row Level Security）|
| 快取       | Upstash Redis（TTL 86400 秒）             |
| AI         | Anthropic Claude claude-haiku-4-5-20251001             |
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

## License

[MIT License](LICENSE) © 2026 Dragon
