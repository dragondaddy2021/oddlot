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
              <li>資料包含：收盤價、本益比（PE Ratio）、殖利率（Dividend Yield）</li>
            </ul>
          </Section>

          <Section title="二、篩選條件">
            <ul className="list-disc list-inside space-y-2 text-gray-600 text-sm leading-relaxed">
              <li>股價 <strong>10～500 元</strong>（適合零股小額投資）</li>
              <li>本益比 <strong>大於 0</strong>（排除虧損股）</li>
              <li>殖利率 <strong>大於 0</strong>（有過去配息紀錄）</li>
              <li>排除 ETF 及特殊商品（專注一般上市個股）</li>
              <li>從符合條件的股票中依殖利率由高到低排序，取前 <strong>50 檔</strong>送入 AI 分析</li>
            </ul>
          </Section>

          <Section title="三、AI 分析">
            <ul className="list-disc list-inside space-y-2 text-gray-600 text-sm leading-relaxed">
              <li>由 <strong>Claude AI（Anthropic）</strong>從 50 檔候選名單中選出 10 檔</li>
              <li>
                考量因素：
                <ul className="list-disc list-inside ml-5 mt-1 space-y-1">
                  <li>殖利率穩定性</li>
                  <li>本益比合理性</li>
                  <li>產業分散度</li>
                  <li>股價親民度（適合零股小額累積）</li>
                </ul>
              </li>
              <li>每檔股票附上繁體中文推薦理由（50 字以內）</li>
            </ul>
          </Section>

          <Section title="四、限制與風險">
            <ul className="list-disc list-inside space-y-2 text-gray-600 text-sm leading-relaxed">
              <li>僅分析<strong>當日資料快照</strong>，未考慮歷史趨勢與股價走勢</li>
              <li>殖利率為<strong>過去配息資料</strong>，不保證未來實際配息金額或比率</li>
              <li>未考慮負債比率、現金流、營收成長等財務健康指標</li>
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
