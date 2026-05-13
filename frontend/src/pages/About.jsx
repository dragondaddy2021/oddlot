export default function About() {
  return (
    <div className="min-h-screen bg-gray-50">
      <main className="max-w-3xl mx-auto px-4 py-10">
        <h2 className="text-2xl font-bold text-gray-900 mb-8">關於 oddlot 選股邏輯</h2>

        <div className="space-y-8">

          <Section title="一、資料來源">
            <ul className="list-disc list-inside space-y-2 text-gray-600 text-sm leading-relaxed">
              <li>股票資料來自<strong>台灣證券交易所（TWSE）</strong>官方公開 API，無需授權金鑰</li>
              <li>每日台股收盤後自動更新（台灣時間凌晨 2:00 執行）</li>
              <li>
                資料包含：
                <ul className="list-disc list-inside ml-5 mt-1 space-y-1">
                  <li>收盤價、本益比（PE Ratio）、殖利率（Dividend Yield）— BWIBBU_d</li>
                  <li>除權息日、除權息前收盤價、權值+息值 — TWT49U</li>
                  <li>個股日收盤價（用於計算填息天數）— STOCK_DAY</li>
                  <li>上市公司產業別（TWSE 33 大產業分類）— OpenAPI t187ap03_L</li>
                </ul>
              </li>
            </ul>
          </Section>

          <Section title="二、篩選條件">
            <p className="text-gray-700 text-sm mb-3 leading-relaxed">
              目標：<strong>幫小資族挑出可以自組 ETF 長期持有的零股</strong>，因此不只看殖利率高低，更重視配息穩定度與產業分散。
            </p>
            <ul className="list-disc list-inside space-y-2 text-gray-600 text-sm leading-relaxed">
              <li>股價 <strong>10～500 元</strong>（適合零股小額投資）</li>
              <li>本益比 <strong>大於 0</strong>（排除虧損股）</li>
              <li>殖利率 <strong>大於 0</strong> 且 ≤ 30%（過大者通常為資料錯位）</li>
              <li><strong>近 3 年每年至少配息一次</strong>（排除不穩定配息股）</li>
              <li>
                <strong>配息金額穩定度 CV ≤ 0.4</strong>：將近 3 年每年配發金額（權值+息值）加總後計算變異係數，過大者剔除 —
                直接打掉<strong>一次性高配發的景氣循環股</strong>（例如營建股結案大筆配息）
              </li>
              <li>
                <strong>產業分散：每個產業最多 3 檔送進 AI</strong>（依 TWSE 33 大產業別分類），避免單一產業過度集中
              </li>
              <li>
                <strong>近 3 年股價 CAGR ≥ -5%/年</strong>：用 STOCK_DAY 取 3 年前同月收盤對比現價計算年複合成長率，過低者剔除 —
                <strong>擋價值陷阱</strong>（年年配 6% 但股價 3 年跌 30% 的長期賠錢股）。資料缺漏時保留，避免誤殺
              </li>
              <li><strong>近 3 年至少成功填息 1 次</strong>（排除長期無法填息的股票）</li>
              <li>排除 ETF 及特殊商品（專注一般上市個股）</li>
              <li className="text-gray-500">
                整體流程：殖利率排序 → 年年配息 + CV 過濾 → 產業 cap → CAGR 過濾 → 填息計算 → 最多保留 <strong>50 檔</strong>送入 AI 分析
              </li>
            </ul>
          </Section>

          <Section title="三、AI 分析">
            <ul className="list-disc list-inside space-y-2 text-gray-600 text-sm leading-relaxed">
              <li>由 <strong>Claude AI（Anthropic）</strong>從 50 檔候選名單中選出 10 檔，組成<strong>產業分散、配息穩定</strong>的長期投資組合</li>
              <li>
                考量因素（按重要性排序）：
                <ol className="list-decimal list-inside ml-5 mt-1 space-y-1">
                  <li><strong>配息穩定度</strong>（dividend_cv，越低越好，&lt;0.2 為非常穩定）</li>
                  <li><strong>產業分散度</strong>（盡量涵蓋 6 個以上不同產業）</li>
                  <li><strong>股價長期趨勢</strong>（price_cagr_3y，&gt;0 為佳；負值代表填息也賠錢的價值陷阱風險）</li>
                  <li><strong>填息速度與填息率</strong>（avg_fill_days 越小、fill_rate 越高越佳）</li>
                  <li><strong>殖利率與本益比合理性</strong>（殖利率 &gt;8% 視為隱含風險訊號，不再是越高越好）</li>
                  <li><strong>股價親民度</strong>（適合零股小額累積）</li>
                </ol>
              </li>
              <li>每檔股票附上繁體中文推薦理由（50 字以內）</li>
              <li>
                股票卡片代號旁顯示<strong>產業類別標籤</strong>，方便快速判斷組合的產業分散度
              </li>
              <li>
                股票卡片會顯示兩項填息指標：
                <ul className="list-disc list-inside ml-5 mt-1 space-y-1">
                  <li><strong>填息速度</strong>：近 3 年已填息事件的平均天數（越短越佳）</li>
                  <li><strong>填息率</strong>：填息事件數 / 除息事件數（越高代表填息機率越高）</li>
                  <li>顯示「—」代表該股樣本不足或資料尚未更新，需搭配其他指標判斷</li>
                </ul>
              </li>
              <li>
                <strong>上次配息</strong>：近 3 年內最近一次除息日（TWSE TWT49U 資料），可參考配息頻率與時間點
              </li>
            </ul>
          </Section>

          <Section title="四、限制與風險">
            <ul className="list-disc list-inside space-y-2 text-gray-600 text-sm leading-relaxed">
              <li>僅分析<strong>當日資料快照</strong>，未考慮歷史股價走勢與總報酬</li>
              <li>殖利率為<strong>過去配息資料</strong>，不保證未來實際配息金額或比率</li>
              <li>未考慮負債比率、現金流、營收成長、ROE 與 EPS／payout ratio 等財務健康指標</li>
              <li>
                <strong>景氣循環股陷阱</strong>：CV 過濾已能擋掉一次性大筆配息，但若一檔股票連續 3 年都配同樣金額仍可能是循環高峰，
                <strong>使用者仍需自行判斷</strong>
              </li>
              <li>
                <strong>CAGR 為價格走勢</strong>：未含現金股利再投入，僅反映股價走勢；長期持有實際總報酬會略高於顯示值
              </li>
              <li>
                <strong>產業別缺漏</strong>：少數新上市公司可能未及時收錄產業別，會以「未分類」處理
              </li>
              <li>AI 分析結果每日不同，不具一致性，不構成持續性投資建議</li>
              <li className="text-red-500 font-medium">本平台資訊僅供參考，不構成任何投資建議，投資人須自行評估風險，本平台不負任何投資損失責任。</li>
            </ul>
          </Section>

          <Section title="五、更新頻率">
            <ul className="list-disc list-inside space-y-2 text-gray-600 text-sm leading-relaxed">
              <li>每日<strong>台灣時間凌晨 2:00</strong> 自動執行選股並更新資料</li>
              <li>非交易日（週末、國定假日）可能顯示前一個交易日的資料</li>
              <li>若當日資料尚未產生，頁面會顯示提示訊息</li>
            </ul>
          </Section>

          <Section title="六、會員功能">
            <ul className="list-disc list-inside space-y-2 text-gray-600 text-sm leading-relaxed">
              <li><strong>我的最愛</strong>：收藏單檔股票，方便日後追蹤</li>
              <li><strong>我的 ETF</strong>：自組個人化投資組合，可從我的最愛挑選成分股並設定權重</li>
              <li className="text-gray-400">目前登入功能尚未開放，相關會員功能敬請期待</li>
            </ul>
          </Section>

        </div>

        <div className="mt-10 pt-6 border-t border-gray-100 text-center">
          <p className="text-xs text-gray-500">
            特別感謝選股邏輯檢視員：Wen Cheng 🐟
          </p>
          <p className="text-xs text-gray-400 mt-2">
            © 2026 oddlot
          </p>
        </div>
      </main>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <section className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
      <h3 className="text-base font-bold text-gray-800 mb-4">{title}</h3>
      {children}
    </section>
  );
}
