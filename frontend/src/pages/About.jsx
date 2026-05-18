export default function About() {
  return (
    <div className="min-h-screen bg-gray-50">
      <main className="max-w-3xl mx-auto px-4 py-10">
        <h2 className="text-2xl font-bold text-gray-900 mb-8">關於 龍爹地的零股投資學習平台 選股邏輯</h2>

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
              <li>
                <strong>Momentum boost（近 3 個月漲跌幅排序強化）</strong>：對殖利率前 200 名計算近 3 月漲跌幅，
                用「殖利率 + momentum × 100」重排序，讓強勢股優先進入產業 cap —
                直擊 3 年回測證實的<strong>系統性錯過 AI/半導體強勢股</strong>問題
              </li>
              <li><strong>近 3 年至少成功填息 1 次</strong>（排除長期無法填息的股票）</li>
              <li>排除 ETF 及特殊商品（專注一般上市個股）</li>
              <li className="text-gray-500">
                整體流程：殖利率排序 → 年年配息 + CV 過濾 → momentum boost → 產業 cap → CAGR 過濾 → 填息計算 → 最多保留 <strong>50 檔</strong>送入 AI 分析
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
                  <li><strong>近期動能</strong>（momentum_3m，近 3 個月漲跌幅；&gt;0.05 強勢、&lt;-0.10 應警惕）</li>
                  <li><strong>填息速度與填息率</strong>（avg_fill_days 越小、fill_rate 越高越佳）</li>
                  <li><strong>殖利率與本益比合理性</strong>（殖利率 &gt;8% 視為隱含風險訊號，不再是越高越好）</li>
                  <li><strong>股價親民度</strong>（適合零股小額累積）</li>
                </ol>
              </li>
              <li>
                每檔股票附上繁體中文推薦理由，採 <strong>4 段固定結構</strong>：
                <ul className="list-disc list-inside ml-5 mt-1 space-y-1">
                  <li><strong>【持有邏輯】</strong>為什麼適合 5 年以上長期持有（連結商業模式 / 現金流特性）</li>
                  <li><strong>【組合角色】</strong>在 10 檔組合中的定位（如：高股息穩定軸、防禦現金流、成長補位）</li>
                  <li><strong>【風險】</strong>具體風險警示，不泛談「市場波動」</li>
                  <li><strong>【近況脈絡】</strong>產業或公司近期狀況（AI 訓練知識內，避免捏造具體數字）</li>
                </ul>
              </li>
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

          <Section title="四、回測表現（誠實揭露）">
            <p className="text-gray-700 text-sm mb-3 leading-relaxed">
              用 3 年（2023-05 → 2026-01）逐月 snapshot 回測，**33 個有效樣本**，與被動式 ETF 比較<strong>價格報酬</strong>（不含現金股利再投入）：
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-gray-700 border border-gray-200 mb-3">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-2 py-1.5 text-left font-medium border border-gray-200">持有期</th>
                    <th className="px-2 py-1.5 text-right font-medium border border-gray-200">本平台 平均</th>
                    <th className="px-2 py-1.5 text-center font-medium border border-gray-200">vs 0056（高股息）</th>
                    <th className="px-2 py-1.5 text-center font-medium border border-gray-200">vs 0050（大盤）</th>
                  </tr>
                </thead>
                <tbody>
                  <tr><td className="px-2 py-1.5 border border-gray-200">3 個月</td><td className="px-2 py-1.5 text-right border border-gray-200">+3.02%</td><td className="px-2 py-1.5 text-center border border-gray-200">勝率 61%，超額 +1.15%</td><td className="px-2 py-1.5 text-center border border-gray-200 text-gray-500">勝率 30%，落後 -5.65%</td></tr>
                  <tr><td className="px-2 py-1.5 border border-gray-200">6 個月</td><td className="px-2 py-1.5 text-right border border-gray-200">+6.50%</td><td className="px-2 py-1.5 text-center border border-gray-200">勝率 67%，超額 +1.95%</td><td className="px-2 py-1.5 text-center border border-gray-200 text-gray-500">勝率 27%，落後 -14.69%</td></tr>
                  <tr><td className="px-2 py-1.5 border border-gray-200">12 個月</td><td className="px-2 py-1.5 text-right border border-gray-200">+10.13%</td><td className="px-2 py-1.5 text-center border border-gray-200">勝率 58%，超額 +1.46%</td><td className="px-2 py-1.5 text-center border border-gray-200 text-gray-500">勝率 9%，落後 -35.87%</td></tr>
                  <tr><td className="px-2 py-1.5 border border-gray-200 font-medium">持有至今</td><td className="px-2 py-1.5 text-right border border-gray-200 font-medium">+22.63%</td><td className="px-2 py-1.5 text-center border border-gray-200"><strong>勝率 33%，平手 -0.34%</strong></td><td className="px-2 py-1.5 text-center border border-gray-200 text-gray-500">勝率 3%，大幅落後</td></tr>
                </tbody>
              </table>
            </div>
            <ul className="list-disc list-inside space-y-2 text-gray-600 text-sm leading-relaxed">
              <li><strong>vs 0056</strong>：短中期勝率約 6 成、超額報酬 +1～2%；長期持有則與 0056 平手。本平台 的價值不在「打敗 0056」而是「可控的自組 ETF 體驗 + 跟 0056 差不多的表現」</li>
              <li><strong>vs 0050</strong>：全期大幅落後，這預期之中 — 本平台 是高股息風格、0050 是大型權值股 ETF（台積電權重 50%），不該硬比</li>
              <li><strong>限制：</strong>只計算<strong>價格報酬</strong>不含現金股利再投入（實際長期報酬會略高）；已處理 0050 在 2025-06-18 的 1:4 拆股；AI 選股有隨機性，重跑同一日結果未必完全一致</li>
              <li className="text-orange-600">2025-Q2 之後 momentum 在恢復期表現轉弱，目前持續觀察中</li>
            </ul>
          </Section>

          <Section title="五、適合誰用 / 不適合誰用">
            <p className="text-gray-700 text-sm mb-3 leading-relaxed">
              基於回測結果與定位，誠實告訴你 本平台 適不適合：
            </p>
            <div className="space-y-3">
              <div className="border-l-4 border-green-500 pl-3 py-1">
                <p className="text-sm font-medium text-gray-800 mb-1">✓ 適合這三種人</p>
                <ul className="list-disc list-inside space-y-1 text-gray-600 text-sm leading-relaxed">
                  <li><strong>想學投資的小資族</strong> — 每天看 4 段選股理由（持有邏輯/組合角色/風險/近況脈絡），慢慢建立產業判斷力</li>
                  <li><strong>每月小額零股累積者</strong>（如 1-3 千元/月） — 零股機制適合分批進場，10 檔組合每月買一兩檔逐步建立部位</li>
                  <li><strong>想自己掌控組合的人</strong> — 透過「我的最愛」與「我的 ETF」客製成分股與權重，比直接買 ETF 多一層彈性</li>
                </ul>
              </div>
              <div className="border-l-4 border-orange-500 pl-3 py-1">
                <p className="text-sm font-medium text-gray-800 mb-1">✗ 這種情況直接買 0056 更簡單</p>
                <p className="text-gray-600 text-sm leading-relaxed">
                  「只想領股息、不想動腦、不想每天看 app」的話 — <strong>直接買 0056（元大高股息）更省事</strong>。回測顯示 本平台 長期報酬與 0056 接近（持有至今 -0.34% 平手），
                  但 本平台 需要自己操作零股買賣、自行管理 10 檔個股，沒有 ETF 自動再平衡。
                </p>
              </div>
              <div className="border-l-4 border-gray-400 pl-3 py-1">
                <p className="text-sm font-medium text-gray-800 mb-1">⚠ 不要期待</p>
                <p className="text-gray-600 text-sm leading-relaxed">
                  「AI 幫我贏大盤 / 賺更多」— 回測證實 本平台 vs 0050（大盤）全期落後，因為定位是高股息穩定軸，不是抓 AI / 半導體成長浪潮。
                </p>
              </div>
            </div>
          </Section>

          <Section title="六、限制與風險">
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

          <Section title="七、更新頻率">
            <ul className="list-disc list-inside space-y-2 text-gray-600 text-sm leading-relaxed">
              <li>每日<strong>台灣時間凌晨 2:00</strong> 自動執行選股並更新資料</li>
              <li>非交易日（週末、國定假日）可能顯示前一個交易日的資料</li>
              <li>若當日資料尚未產生，頁面會顯示提示訊息</li>
            </ul>
          </Section>

          <Section title="八、會員功能">
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
            © 2026 龍爹地的零股投資學習平台
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
