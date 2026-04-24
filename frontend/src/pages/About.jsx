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
              <li><strong>近 3 年每年至少配息一次</strong>（排除不穩定配息股）</li>
              <li><strong>近 3 年至少成功填息 1 次</strong>（排除長期無法填息的股票）</li>
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
                  <li>填息速度與填息率（參考近 3 年 TWSE 除權息與日收盤資料計算）</li>
                </ul>
              </li>
              <li>每檔股票附上繁體中文推薦理由（50 字以內）</li>
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
              <li>僅分析<strong>當日資料快照</strong>，未考慮歷史趨勢與股價走勢</li>
              <li>殖利率為<strong>過去配息資料</strong>，不保證未來實際配息金額或比率</li>
              <li>未考慮負債比率、現金流、營收成長等財務健康指標</li>
              <li>
                <strong>產業集中風險</strong>：篩選第一步依殖利率由高到低排序，名單容易集中在營造、金融等高殖利率的
                <strong>景氣循環股</strong>，AI 雖會參考產業分散度，但不保證涵蓋所有產業，使用者需自行評估組合分散度
              </li>
              <li>
                <strong>景氣循環股陷阱</strong>：營造、航運等產業獲利波動大，過去高殖利率常是獲利高峰年的結果，
                <strong>不代表未來可持續配息</strong>
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
