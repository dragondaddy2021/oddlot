# oddlot 自動化測試

## 環境變數

| 變數 | 說明 | 預設值 |
|------|------|--------|
| `SUPABASE_URL` | Supabase 專案 URL | 必填 |
| `SUPABASE_ANON_KEY` | Supabase anon 金鑰 | 必填 |
| `TEST_BASE_URL` | 前端測試目標 URL | `https://dragondaddy2021.github.io/oddlot` |

## 安裝依賴

```bash
pip install -r tests/requirements-test.txt
```

## 執行方式

```bash
# 只跑 API 測試（不需要瀏覽器）
pytest tests/test_api.py -v

# 只跑 Selenium 測試（需要 Chrome）
pytest tests/test_selenium.py -v

# 跑所有測試（不含 Appium）
pytest tests/ -v --ignore=tests/test_appium.py

# 產生 HTML 測試報告
pytest tests/ -v --ignore=tests/test_appium.py --html=report.html --self-contained-html

# 跑 Appium 測試（需要 Appium server + Android 模擬器）
pytest tests/test_appium.py -v --run-appium
```

## 測試內容

### test_api.py（requests）
| 測試 | 說明 |
|------|------|
| `test_homepage_loads` | 首頁回傳 HTTP 200 |
| `test_supabase_recommendations` | 今日 ai_recommendations 資料存在 |
| `test_supabase_rls_anon_can_read` | 匿名用戶可讀取選股資料 |
| `test_supabase_rls_anon_cannot_write` | 匿名用戶無法寫入（RLS 保護） |
| `test_recommendations_data_format` | 10 筆選股，每筆欄位完整 |

### test_selenium.py（瀏覽器 E2E）
| 測試 | 說明 |
|------|------|
| `test_homepage_title` | 標題包含 "oddlot" |
| `test_disclaimer_banner` | 免責聲明 banner 存在 |
| `test_stock_cards_displayed` | 首頁顯示至少 1 張股票卡片 |
| `test_navbar_links` | Navbar 有三個導覽連結 |
| `test_about_page` | 選股說明頁有「資料來源」 |
| `test_login_page` | 登入頁有「登入功能即將開放」 |
| `test_footer_copyright` | Footer 有著作權聲明 |

### test_appium.py（手機 E2E）
需加 `--run-appium` 才執行，預設跳過。

## Appium 環境設定

1. 安裝 Appium：`npm install -g appium`
2. 安裝 UiAutomator2 driver：`appium driver install uiautomator2`
3. 啟動 Android 模擬器（AVD Manager）
4. 啟動 Appium：`appium`
5. 執行：`pytest tests/test_appium.py -v --run-appium`
