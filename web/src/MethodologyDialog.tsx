import { useEffect } from 'react'
import type { ReactNode } from 'react'
import { Dot } from './format'
import { Logo } from './Logo'
import { useI18n } from './i18n'

function Block({ title, dot, children }: { title: string; dot?: boolean; children: ReactNode }) {
  return (
    <section className="mb-4">
      <h3 className="mb-1 flex items-center gap-2 text-sm font-semibold text-slate-100">
        {dot ? <Dot tone="green" /> : null}
        {title}
      </h3>
      <div className="text-[13px] leading-relaxed text-slate-300">{children}</div>
    </section>
  )
}

function BodyEn() {
  return (
    <>
      <p className="mb-5 text-[13px] leading-relaxed text-slate-300">
        Screener3000 runs <strong className="text-slate-100">four independent value/growth screens</strong> on one merged universe
        &mdash; the S&amp;P 500, Dow 30, Nasdaq-100, the top 100 holdings of VUG, VTV and VIG (Growth / Value / Dividend 100), and
        every other US stock of $1B+ market cap in VTI (Total US) &mdash; then shows where they agree and where they don&rsquo;t. The default list shows names that clear{' '}
        <strong className="text-slate-100">all four</strong>. Each system answers a different question, and they often disagree &mdash;
        that disagreement is the signal.
      </p>

      <Block title="Azqato — growth rank vs the field" dot>
        The live azqato screener&rsquo;s relative percentile model. Six metrics in four evenly weighted pillars &mdash;{' '}
        <strong className="text-slate-100">TTM 25%</strong> (revenue growth 10, EPS growth 15),{' '}
        <strong className="text-slate-100">FWD 25%</strong> (revenue growth 10, EPS growth 15) &mdash; proven results count the same as
        analyst forecasts, and EPS growth outweighs revenue growth in both &mdash;{' '}
        <strong className="text-slate-100">Valuation 25%</strong> (PEG forward),{' '}
        <strong className="text-slate-100">Balance sheet 25%</strong> (cash vs debt). Each metric earns points by percentile rank
        against every other screened name: only the top 22% earns full marks, the bottom 22% earns zero, and a missing metric scores a
        hard zero. Scores map to rank tiers &mdash; S = top 10%, A = next 10%, B = 20&ndash;50%, C = 50&ndash;75%, F = bottom 25%; a
        perfect 100 earns S+. A stock <strong className="text-slate-100">passes</strong> at tier A or better (the top ~20%). Forward
        figures are current-fiscal-year analyst consensus; unprofitable names rank worst on valuation rather than dropping out. Because
        the model is relative, the peer set is part of the score: the tier here ranks a stock against <em>all</em> screened names, while
        the scorecard also shows its rank inside each curated pool &mdash; the way azqato&rsquo;s own screener, which loads one
        universe at a time, would rank it.
      </Block>

      <Block title="Lynch — growth at a reasonable price" dot>
        Peter Lynch&rsquo;s PEG-centric method. Fair value is estimated two ways, giving two verdicts: a{' '}
        <strong className="text-slate-100">Value</strong> band (price vs. the earnings &times; (growth + dividend yield) fair value) and
        a <strong className="text-slate-100">PEG price band</strong> (price vs. the PEG fair value). Each is graded Strong Buy / Buy /
        Hold / Avoid &mdash; cheap relative to its growth reads as Buy.
      </Block>

      <Block title="Graham — intrinsic value + balance-sheet safety" dot>
        Benjamin Graham&rsquo;s two orthogonal checks. <strong className="text-slate-100">Valuation</strong>: his revised
        intrinsic-value formula &mdash; earnings &times; (8.5 + 2 &times; growth), rate-adjusted by the current AAA corporate-bond yield
        &mdash; graded Deep Buy / Buy / Watch / Avoid by margin of safety. <strong className="text-slate-100">Defensive</strong>: eight
        balance-sheet criteria (size, current ratio &ge; 2, long-term debt &le; working capital, positive EPS every year for 10 years,
        20 years of uninterrupted dividends, 33% 10-year EPS growth, P/E &le; 15, P/B &le; 1.5) &mdash; Pass / Borderline / Fail. The
        10-year EPS criteria need a full decade of statements, which the free data source rarely supplies, so few names clear them.
      </Block>

      <Block title="Wealthmatica — growth-quality checklist" dot>
        The financial checklist the Wealthmatica newsletter runs in every stock report, made mechanical. Nine checks on the last two
        to three annual statements, each about the <em>direction</em> of the business: revenue growth &ge; 15%; growth speeding up
        (or &ge; 25%); free cash flow positive and rising; free cash flow still positive after stock-based compensation; share count up
        no more than 2% a year; gross margin down no more than 1 point; operating margin up; EPS rising (or a loss narrowing); cash at
        least equal to debt. A stock <strong className="text-slate-100">passes</strong> with 7 of the 9. A check the statements
        can&rsquo;t answer &mdash; a bank reports no gross margin &mdash; is skipped rather than failed, and the bar scales to the checks
        that apply (5 of 6, 6 of 7, 7 of 8); with fewer than 6 it is N/A. The newsletter publishes no cut-offs, so these thresholds
        are this screener&rsquo;s own.
      </Block>

      <Block title="Overall — informational 4-pillar composite">
        A separate, absolute 0&ndash;100 score shown alongside the four systems above &mdash; it does{' '}
        <strong className="text-slate-100">not</strong> count toward the <em>Pass</em> filter or the N/4 chip.{' '}
        <strong className="text-slate-100">Value 35%</strong> (Lynch/Graham discount, FCF/earnings/shareholder yield, distance from the
        52-week and 5-year low, DCF discount), <strong className="text-slate-100">Quality 30%</strong> (Graham defensive score,
        debt/equity, current ratio, ROIC), <strong className="text-slate-100">Growth 20%</strong> (growth rate and its stability across
        available years), <strong className="text-slate-100">Safety 15%</strong> (Piotroski F-Score, Altman Z&Prime;, plus the Quality
        leverage/liquidity signals). Discount thresholds scale with the live AAA yield &mdash; the same discount is less impressive when
        rates are high. Financial-sector names skip the Altman/DCF/earnings-yield legs (those formulas don&rsquo;t apply to bank balance
        sheets); a missing pillar is simply excluded from the average rather than penalized.
      </Block>

      <Block title="Reading the screen">
        Each card shows the four verdicts (a green-tinted tile is a pass), the informational Overall score in the ring,
        and the headline numbers: PEG, forward PEG, forward EPS growth, the Graham and Lynch discounts to fair value, dividend yield and
        where the price sits in its 52-week range. Tap a card (or type a ticker and press Enter) for the full scorecard &mdash; every
        verdict, its drivers, an RSI gauge, the per-pool Azqato ranks and the raw fundamentals behind them. Tighten the filter to{' '}
        <em>All 4</em>, or relax it to see names that clear 2, 1, or any; narrow to one pool with the pool picker (<em>All pools</em>). The dot at the top
        shows how old the data is; the app checks for a new screen in the background and offers it when one lands, and keeps working
        offline once installed. A stock is <em>picked</em> at each level the first time it clears exactly 1, 2, 3 or all 4 screens:
        its card shows the date and price of each pick at the levels you are filtering on, and the move since; the scorecard lists all
        four. A later pick never replaces an earlier one. That history starts with the first four-screen run in October 2026; picks
        from the earlier three-screen version are not carried over, because a level of three screens meant something different.
      </Block>

      <p className="mt-5 border-t border-white/[0.06] pt-4 text-[12px] leading-relaxed text-slate-500">
        Fundamentals from Yahoo Finance and Finnhub; AAA yield from FRED. Missing values render as &ldquo;&mdash;&rdquo;, never zero.{' '}
        <strong className="text-slate-400">Educational use only &mdash; not financial advice.</strong> Verify every name yourself before
        acting.
      </p>
    </>
  )
}

function BodyZh() {
  return (
    <>
      <p className="mb-5 text-[13px] leading-relaxed text-slate-300">
        Screener3000 對同一個合併股票池執行<strong className="text-slate-100">四項獨立的價值／成長篩選</strong>
        &mdash; S&amp;P 500、Dow 30、Nasdaq-100、VUG、VTV 與 VIG 的前 100 大持股（成長／價值／股息 100），以及 VTI
        中其餘市值 10 億美元以上的所有美股（全美股）&mdash; 再呈現它們意見一致與分歧之處。預設清單只顯示
        <strong className="text-slate-100">四項全數通過</strong>的股票。每套系統回答不同的問題，彼此經常意見分歧 &mdash;
        而分歧本身就是訊號。
      </p>

      <Block title="Azqato — 成長性相對排名" dot>
        即時運作的 azqato 篩選器所用的相對百分位模型。六項指標分屬四個權重相同的支柱 &mdash;{' '}
        <strong className="text-slate-100">近四季 (TTM) 25%</strong>（營收成長 10、EPS 成長 15）、
        <strong className="text-slate-100">預估 (FWD) 25%</strong>（營收成長 10、EPS 成長 15）&mdash;
        已實現的成果與分析師預估同等計分，且兩者中 EPS 成長的權重都高於營收成長 &mdash;{' '}
        <strong className="text-slate-100">估值 25%</strong>（預估 PEG）、
        <strong className="text-slate-100">資產負債表 25%</strong>（現金對債務）。每項指標依其在所有受篩股票中的百分位排名得分：
        只有前 22% 拿滿分，後 22% 得零分，缺少資料的指標直接以零分計。分數對應排名等級 &mdash; S = 前 10%、A = 次 10%、B =
        20&ndash;50%、C = 50&ndash;75%、F = 後 25%；滿分 100 為 S+。等級達 A 以上（約前 20%）即
        <strong className="text-slate-100">通過</strong>。預估數字為本會計年度的分析師共識；虧損公司在估值項排名墊底，而非被剔除。
        由於模型是相對的，比較對象本身就是分數的一部分：此處的等級是與<em>所有</em>受篩股票相比，評分卡另外列出它在各精選股池內的排名
        &mdash; 也就是 azqato 自家篩選器（一次只載入一個股池）會給出的排名。
      </Block>

      <Block title="Lynch — 以合理價格買成長" dot>
        Peter Lynch 以 PEG 為核心的方法。合理價值以兩種方式估算，得出兩個評等：
        <strong className="text-slate-100">價值</strong>帶（股價對比「盈餘 &times;（成長率 + 殖利率）」的合理價值）與
        <strong className="text-slate-100">PEG 價格帶</strong>（股價對比 PEG 合理價值）。兩者各自評為
        強力買進／買進／持有／避開 &mdash; 相對成長性便宜者即為買進。
      </Block>

      <Block title="Graham — 內在價值＋資產負債表安全性" dot>
        Benjamin Graham 兩項互不相干的檢查。<strong className="text-slate-100">估值</strong>：他修訂後的內在價值公式 &mdash;
        盈餘 &times;（8.5 + 2 &times; 成長率），並以當前 AAA 公司債殖利率調整 &mdash; 依安全邊際評為
        深度買進／買進／觀察／避開。<strong className="text-slate-100">防禦性</strong>：八項資產負債表條件（規模、流動比率 &ge;
        2、長期債務 &le; 營運資金、連續 10 年 EPS 為正、連續 20 年未中斷配息、10 年 EPS 成長 33%、本益比 &le; 15、股價淨值比
        &le; 1.5）&mdash; 評為 通過／臨界／未通過。10 年 EPS 條件需要完整十年的財報，免費資料來源很少提供，因此能通過的股票不多。
      </Block>

      <Block title="Wealthmatica — 成長品質檢查表" dot>
        Wealthmatica 電子報在每篇個股報告中都會檢視的財務檢查表，在此改為機械化判定。根據最近兩到三年的年度財報做九項檢查，
        每項都著眼於企業的<em>趨勢方向</em>：營收成長 &ge; 15%；成長加速（或 &ge; 25%）；自由現金流為正且上升；扣除股票酬勞後自由現金流仍為正；
        股數每年增加不超過 2%；毛利率下降不超過 1 個百分點；營業利益率上升；EPS 上升（或虧損收斂）；現金至少等於債務。九項中通過 7 項即
        <strong className="text-slate-100">通過</strong>。財報無法回答的檢查 &mdash; 例如銀行沒有毛利率 &mdash;
        會略過而非判為未通過，門檻依適用的檢查數等比調整（6 項中 5 項、7 項中 6 項、8 項中 7 項）；適用少於 6 項則為
        N/A。電子報並未公布門檻，以上數值為本篩選器自訂。
      </Block>

      <Block title="綜合 — 僅供參考的四支柱綜合分數">
        與上述四套系統並列顯示的獨立、絕對 0&ndash;100 分數 &mdash; 它
        <strong className="text-slate-100">不</strong>計入<em>通過</em>篩選，也不計入 N/4 標籤。
        <strong className="text-slate-100">價值 35%</strong>（Lynch／Graham 折價、自由現金流／盈餘／股東收益率、與 52 週及 5
        年低點的距離、DCF 折價）、<strong className="text-slate-100">品質 30%</strong>（Graham
        防禦性分數、負債權益比、流動比率、ROIC）、<strong className="text-slate-100">成長 20%</strong>
        （成長率及其在可得年度間的穩定度）、<strong className="text-slate-100">安全 15%</strong>（Piotroski F 分數、Altman
        Z&Prime;，加上品質支柱中的槓桿／流動性訊號）。折價門檻隨即時 AAA 殖利率調整 &mdash;
        利率高時，同樣的折價就沒那麼吸引人。金融類股略過 Altman／DCF／盈餘殖利率等項目（這些公式不適用於銀行的資產負債表）；
        缺少的支柱直接排除在平均之外，而不是扣分。
      </Block>

      <Block title="閱讀篩選結果">
        每張卡片顯示四個評等（綠色底色代表通過）、圓環中僅供參考的綜合分數，以及主要數字：PEG、預估 PEG、預估 EPS 成長、Graham 與
        Lynch 相對合理價值的折價、殖利率，以及股價在 52 週區間中的位置。點選卡片（或輸入代號後按 Enter）可開啟完整評分卡 &mdash;
        每個評等及其驅動因素、RSI 量表、Azqato 在各股池的排名，以及背後的原始基本面數據。篩選器可收緊到<em>全 4</em>，
        或放寬為通過 2 項、1 項或不限；用股池選單可縮小到單一股池（<em>全部股池</em>）。頂端的圓點顯示資料新舊；App
        會在背景檢查新的篩選結果並在出爐時提示，安裝後也能離線使用。股票第一次恰好通過 1、2、3 或全部 4 項篩選時，即在該層級
        <em>入選</em>：卡片顯示您所篩選層級的入選日期、價格及其後漲跌；評分卡則列出全部四個層級。之後的入選不會取代較早的紀錄。
        這段歷史從 2026 年 10 月第一次四項篩選開始；先前三項篩選版本的入選紀錄不予沿用，因為當時的「三項篩選」意義不同。
      </Block>

      <p className="mt-5 border-t border-white/[0.06] pt-4 text-[12px] leading-relaxed text-slate-500">
        基本面資料來自 Yahoo Finance 與 Finnhub；AAA 殖利率來自 FRED。缺少的數值顯示為「&mdash;」，絕不顯示為零。
        <strong className="text-slate-400">僅供教育用途 &mdash; 並非投資建議。</strong>採取任何行動前，請自行查證每一檔股票。
      </p>
    </>
  )
}

export default function MethodologyDialog({ onClose }: { onClose: () => void }) {
  const { m, lang } = useI18n()
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} aria-hidden />
      <div className="relative z-10 max-h-[85vh] w-full max-w-2xl overflow-auto rounded-3xl border border-white/10 bg-surface-1 shadow-2xl">
        <header className="sticky top-0 flex items-center justify-between border-b border-white/[0.06] bg-surface-1/95 backdrop-blur-xl px-6 py-4">
          <div className="flex items-center gap-2">
            <Logo className="h-5 w-5 text-emerald-400" />
            <h2 className="text-lg font-bold tracking-tight text-slate-100">{m.methodologyTitle}</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={m.close}
            className="grid size-11 shrink-0 place-items-center rounded-full text-slate-400 hover:bg-surface-3 hover:text-slate-100"
          >
            ✕
          </button>
        </header>

        <div className="px-6 py-5">
          {lang === 'zh-TW' ? <BodyZh /> : <BodyEn />}
        </div>
      </div>
    </div>
  )
}
