// Every string the app itself shows, per language. `en` is the source; the
// Chinese catalog is typed as `Messages`, so a key added here without a
// translation fails the typecheck. System names (Azqato, Lynch, Graham,
// Wealthmatica) stay English in both — the owner's call.

import type { ReactNode } from 'react'
import type { Lang } from './i18n'
import type { AzqatoTier, IndexName, PickLevel, WealthmaticaCheckKey } from './types'
import type { SortKey } from './filters'
import type { AgeUnit } from './freshness'

const en = {
  lang: 'en' as Lang,

  // App
  summary: (all: ReactNode, total: ReactNode, pool: string | null): ReactNode => (
    <>
      {all} of {total} stocks{pool ? ` in ${pool}` : ''} pass all four screens
    </>
  ),
  loadFailed: (why: string) => `Couldn’t load the screen: ${why}`,
  tryAgain: 'Try again',
  noMatch: (q: string) => `No stocks match${q ? ` “${q}”` : ''}.`,
  clearSearch: 'Clear search',
  showLooser: (level: number, n: number) => `Show ${level === 0 ? 'every name' : `${level}+ screens`} (${n})`,
  footer: (shown: number, total: number) => `${shown} of ${total} shown · Educational use only — not financial advice.`,

  // FilterBar
  passLevels: { 4: 'All 4', 3: '3+', 2: '2+', 1: '1+', 0: 'Any' } as Record<0 | 1 | 2 | 3 | 4, string>,
  passLevelsSpoken: {
    4: 'Passes all 4 screens',
    3: 'Passes 3 or more',
    2: 'Passes 2 or more',
    1: 'Passes 1 or more',
    0: 'Any',
  } as Record<0 | 1 | 2 | 3 | 4, string>,
  passLevelCount: (spoken: string, n: number) => `${spoken}: ${n} stocks`,
  screensPassed: 'Screens passed',
  searchPlaceholder: 'Ticker or sector',
  searchLabel: 'Search by ticker or sector',
  pool: 'Pool',
  sort: 'Sort',
  allPools: 'All pools',
  poolLabel: {
    'S&P500': 'S&P 500',
    Dow30: 'Dow 30',
    Nasdaq100: 'Nasdaq 100',
    Growth100: 'Growth 100',
    Value100: 'Value 100',
    Dividend100: 'Dividend 100',
    TotalUS: 'Total US $1B+',
  } as Record<IndexName, string>,
  sortLabel: {
    best: 'Consensus',
    azqato: 'Azqato score',
    overall: 'Overall score',
    graham: 'Graham discount',
    lynch: 'Lynch discount',
    peg: 'Lowest PEG',
    pegFwd: 'Lowest fwd PEG',
    epsFwd: 'Fwd EPS growth',
    yield: 'Dividend yield',
    cap: 'Market cap',
    ticker: 'Ticker A–Z',
  } as Record<SortKey, string>,

  // Header
  age: (unit: AgeUnit, n: number): string =>
    unit === 'now' ? 'just now' : unit === 'min' ? `${n} min ago` : unit === 'hr' ? `${n} hr ago` : `${n} day${n === 1 ? '' : 's'} ago`,
  offline: 'Offline · ',
  updated: (rel: string) => `Updated ${rel}`,
  dateUnknown: 'Data date unknown',
  stale: '· stale',
  screened: 'Screened',
  nextScreen: 'Next screen',
  lastChecked: 'Last checked',
  checkFailed: 'failed · ',
  staleNote: 'Over a week old — the daily screen has not published since. Treat prices and verdicts with care.',
  freshNote: 'Screens run every weekday morning (US); new data appears here once the run finishes.',
  offlineNote: ' You are offline, so this is the last copy saved on this device.',
  checking: 'Checking…',
  checkNow: 'Check for new data',
  howItWorks: 'How the screens work',
  methodologyTitle: 'How Screener3000 works',
  switchTo: { label: '中文', lang: 'zh-TW' as Lang, aria: 'Switch to Traditional Chinese' },

  // Toasts
  dismiss: 'Dismiss',
  newVersion: 'A new version of the app is ready.',
  update: 'Update',
  freshData: (when: ReactNode): ReactNode => <>Fresh data from {when}</>,
  load: 'Load',

  // StockCard
  wk52: '52-wk',
  wk52Title: 'Position in the 52-week range',
  pickedLine: (level: PickLevel, date: string, price: ReactNode): ReactNode => (
    <>
      Picked on {LEVEL_EN[level]} {date} at {price}
    </>
  ),
  overallTitle: 'Overall score (informational, not part of the pass gate)',
  verdictAria: (system: string, label: string, pass: boolean) => `${system}: ${label}${pass ? ', passes' : ''}`,
  stat: { peg: 'PEG', pegFwd: 'Fwd PEG', epsFwd: 'Fwd EPS', grahamDisc: 'Graham disc', lynchDisc: 'Lynch disc', divYield: 'Div yield' },
  screensCount: (n: number, of: number) => `${n}/${of} screens`,

  // Scorecard
  scorecardAria: (t: string) => `${t} scorecard`,
  openFinviz: 'Open on Finviz',
  close: 'Close',
  capLine: (cap: ReactNode): ReactNode => <>{cap} mkt cap</>,
  noScores: (t: string, why: string) => `No scores for ${t}: ${why}.`,
  valuationNA: (why: string) =>
    `Lynch and Graham are N/A here: ${why}. The name stays visible — Azqato ranks it relative to the universe, and the Graham defensive checks still run.`,
  rankInPools: 'Rank inside each pool it belongs to',
  dotsNote: 'Dots rank each metric against every screened name: green top of the field, amber middle, red bottom or missing.',
  rsiTiming: 'RSI(14) — entry timing',
  pos52w: '52-week position',
  overall: 'Overall',
  overallSub: 'Informational 4-pillar composite — not part of the pass gate above',
  pillars: { value: 'Value', quality: 'Quality', growth: 'Growth', safety: 'Safety' },
  dcfDiscount: 'DCF discount',
  dcfImpliedGrowth: 'DCF implied growth',
  dcfMethod: 'DCF method',
  researchFlags: 'Research flags: ',
  dcfNote: 'DCF note: ',
  firstPicked: 'First picked',
  levelLabel: (l: PickLevel) => LEVEL_EN[l].replace(/^./, (c) => c.toUpperCase()),
  now: 'now',
  never: 'Never',
  fundamentals: 'Fundamentals',
  fund: {
    growthUsed: 'Growth (g) used',
    epsTtm: 'EPS TTM',
    pb: 'P/B',
    divYield: 'Dividend yield',
    lynchScore: 'Lynch score',
    peFwd: 'P/E FWD',
    cash: 'Cash',
    debt: 'Debt',
    netCashCap: 'Net cash / cap',
  },

  // score.ts — verdicts and drivers
  question: {
    Azqato: 'Growth rank vs the field',
    Lynch: 'Growth at a reasonable price',
    Graham: 'Intrinsic value + balance-sheet safety',
    Wealthmatica: 'Growth-quality checklist',
  },
  noData: 'No data',
  wmTooFew: 'Too few statement lines to judge',
  tierTagline: {
    sp: 'Perfect score — tops every scored metric',
    s: 'Top 10% of the screened universe',
    a: 'Top 20% of the screened universe',
    b: 'Upper half of the screened universe',
    c: 'Below the median',
    f: 'Bottom quarter of the screened universe',
  } as Record<AzqatoTier, string>,
  az: {
    score: 'Score',
    strong: 'Strong metrics',
    revTTM: 'Revenue growth TTM',
    revFwd: 'Revenue growth FWD',
    epsTTM: 'EPS growth TTM',
    epsFwd: 'EPS growth FWD',
    pegFwd: 'PEG FWD',
    cashDebt: 'Cash vs debt',
  },
  lynch: { pe: 'P/E', peg: 'PEG', buyPrice: 'Buy price', discount: 'Discount' },
  graham: { fairValue: 'Fair value', discount: 'Discount' },
  wm: {
    revGrowth: 'Revenue growth',
    revAccel: 'Growth vs prior year',
    fcf: 'FCF margin',
    fcfSbc: 'FCF − stock comp',
    shareChange: 'Share count',
    grossMargin: 'Gross margin',
    opMargin: 'Operating margin',
    eps: 'EPS',
    cashDebt: 'Cash − debt',
  } as Record<WealthmaticaCheckKey, string>,
  pts: (s: string) => `${s} pts`,
  wmPass: 'Growing, cash-generating, not diluting',
  wmFail: 'Fails the growth-quality checklist',
  notValued: 'Not valued — needs positive growth',
  lynchTagline: { green: 'Reasonably priced for its growth', yellow: 'Fairly priced', red: 'Expensive for its growth' },
  grahamTagline: { green: 'Below intrinsic value', yellow: 'Near fair value', red: 'Above intrinsic value' },
  line: {
    checklist: 'Checklist',
    tier: 'Tier',
    lynchValue: 'Value (G+D)',
    pegBand: 'PEG price band',
    valuation: 'Valuation',
    defensive: 'Defensive',
  },
  // The backend's grade strings. They stay the data's own keys (the pass gate
  // reads them); only their display is translated.
  status: {} as Record<string, string>,
}

const LEVEL_EN: Record<PickLevel, string> = { 4: 'all 4 screens', 3: '3 screens', 2: '2 screens', 1: '1 screen' }
const LEVEL_ZH: Record<PickLevel, string> = { 4: '全部 4 項', 3: '3 項', 2: '2 項', 1: '1 項' }

export type Messages = typeof en

const zhTW: Messages = {
  lang: 'zh-TW',

  summary: (all, total, pool) => (
    <>
      {pool ? `${pool} ` : ''}
      {total} 檔股票中，{all} 檔通過全部四項篩選
    </>
  ),
  loadFailed: (why) => `無法載入篩選結果：${why}`,
  tryAgain: '重試',
  noMatch: (q) => (q ? `沒有符合「${q}」的股票。` : '沒有符合的股票。'),
  clearSearch: '清除搜尋',
  showLooser: (level, n) => `${level === 0 ? '顯示全部' : `顯示通過 ${level} 項以上`}（${n}）`,
  footer: (shown, total) => `顯示 ${total} 檔中的 ${shown} 檔 · 僅供教育用途，並非投資建議。`,

  passLevels: { 4: '全 4', 3: '3+', 2: '2+', 1: '1+', 0: '不限' },
  passLevelsSpoken: { 4: '通過全部 4 項篩選', 3: '通過 3 項以上', 2: '通過 2 項以上', 1: '通過 1 項以上', 0: '不限' },
  passLevelCount: (spoken, n) => `${spoken}：${n} 檔`,
  screensPassed: '通過篩選數',
  searchPlaceholder: '代號或產業',
  searchLabel: '依代號或產業搜尋',
  pool: '股池',
  sort: '排序',
  allPools: '全部股池',
  poolLabel: {
    'S&P500': 'S&P 500',
    Dow30: 'Dow 30',
    Nasdaq100: 'Nasdaq 100',
    Growth100: '成長 100',
    Value100: '價值 100',
    Dividend100: '股息 100',
    TotalUS: '全美股 $10億+',
  },
  sortLabel: {
    best: '共識',
    azqato: 'Azqato 分數',
    overall: '綜合分數',
    graham: 'Graham 折價',
    lynch: 'Lynch 折價',
    peg: 'PEG 最低',
    pegFwd: '預估 PEG 最低',
    epsFwd: '預估 EPS 成長',
    yield: '殖利率',
    cap: '市值',
    ticker: '代號 A–Z',
  },

  age: (unit, n) => (unit === 'now' ? '剛剛' : unit === 'min' ? `${n} 分鐘前` : unit === 'hr' ? `${n} 小時前` : `${n} 天前`),
  offline: '離線 · ',
  updated: (rel) => `${rel}更新`,
  dateUnknown: '資料日期不明',
  stale: '· 已過期',
  screened: '篩選時間',
  nextScreen: '下次篩選',
  lastChecked: '上次檢查',
  checkFailed: '失敗 · ',
  staleNote: '資料已超過一週 — 每日篩選此後未曾發布。請審慎看待股價與評等。',
  freshNote: '篩選於每個交易日早上（美國時間）執行；執行完成後新資料會顯示於此。',
  offlineNote: '您目前離線，這是此裝置上保存的最後一份資料。',
  checking: '檢查中…',
  checkNow: '檢查新資料',
  howItWorks: '篩選方式說明',
  methodologyTitle: 'Screener3000 如何運作',
  switchTo: { label: 'EN', lang: 'en', aria: 'Switch to English' },

  dismiss: '關閉',
  newVersion: '新版本已就緒。',
  update: '更新',
  freshData: (when) => <>有新資料：{when}</>,
  load: '載入',

  wk52: '52 週',
  wk52Title: '在 52 週區間中的位置',
  pickedLine: (level, date, price) => (
    <>
      {LEVEL_ZH[level]}入選 {date}，{price}
    </>
  ),
  overallTitle: '綜合分數（僅供參考，不計入篩選門檻）',
  verdictAria: (system, label, pass) => `${system}：${label}${pass ? '，通過' : ''}`,
  stat: { peg: 'PEG', pegFwd: '預估 PEG', epsFwd: '預估 EPS', grahamDisc: 'Graham 折價', lynchDisc: 'Lynch 折價', divYield: '殖利率' },
  screensCount: (n, of) => `通過 ${n}/${of} 項`,

  scorecardAria: (t) => `${t} 評分卡`,
  openFinviz: '在 Finviz 開啟',
  close: '關閉',
  capLine: (cap) => <>市值 {cap}</>,
  noScores: (t, why) => `${t} 無評分：${why}。`,
  valuationNA: (why) => `此股 Lynch 與 Graham 無法估值：${why}。仍保留顯示 — Azqato 以相對排名評分，Graham 防禦性檢查照常進行。`,
  rankInPools: '在所屬各股池內的排名',
  dotsNote: '圓點代表各指標在所有受篩股票中的排名：綠色居前、琥珀色居中、紅色居後或缺資料。',
  rsiTiming: 'RSI(14) — 進場時機',
  pos52w: '52 週位置',
  overall: '綜合',
  overallSub: '僅供參考的四支柱綜合分數 — 不計入上方的篩選門檻',
  pillars: { value: '價值', quality: '品質', growth: '成長', safety: '安全' },
  dcfDiscount: 'DCF 折價',
  dcfImpliedGrowth: 'DCF 隱含成長率',
  dcfMethod: 'DCF 方法',
  researchFlags: '研究警示：',
  dcfNote: 'DCF 附註：',
  firstPicked: '首次入選',
  levelLabel: (l) => LEVEL_ZH[l],
  now: '目前',
  never: '從未',
  fundamentals: '基本面',
  fund: {
    growthUsed: '採用成長率 (g)',
    epsTtm: 'EPS（近四季）',
    pb: '股價淨值比',
    divYield: '殖利率',
    lynchScore: 'Lynch 分數',
    peFwd: '預估本益比',
    cash: '現金',
    debt: '負債',
    netCashCap: '淨現金／市值',
  },

  question: {
    Azqato: '成長性相對排名',
    Lynch: '以合理價格買成長',
    Graham: '內在價值＋資產負債表安全性',
    Wealthmatica: '成長品質檢查表',
  },
  noData: '無資料',
  wmTooFew: '財報項目過少，無法判斷',
  tierTagline: {
    sp: '滿分 — 每項計分指標皆居首',
    s: '受篩股票中前 10%',
    a: '受篩股票中前 20%',
    b: '受篩股票中前半段',
    c: '低於中位數',
    f: '受篩股票中後 25%',
  },
  az: {
    score: '分數',
    strong: '強勢指標',
    revTTM: '營收成長（近四季）',
    revFwd: '營收成長（預估）',
    epsTTM: 'EPS 成長（近四季）',
    epsFwd: 'EPS 成長（預估）',
    pegFwd: '預估 PEG',
    cashDebt: '現金對負債',
  },
  lynch: { pe: '本益比', peg: 'PEG', buyPrice: '買進價', discount: '折價' },
  graham: { fairValue: '合理價值', discount: '折價' },
  wm: {
    revGrowth: '營收成長',
    revAccel: '成長率較前一年',
    fcf: '自由現金流率',
    fcfSbc: '自由現金流 − 股票酬勞',
    shareChange: '股數變化',
    grossMargin: '毛利率',
    opMargin: '營業利益率',
    eps: 'EPS',
    cashDebt: '現金 − 負債',
  },
  pts: (s) => `${s} 個百分點`,
  wmPass: '持續成長、產生現金、未稀釋股權',
  wmFail: '未通過成長品質檢查',
  notValued: '未估值 — 需要正成長',
  lynchTagline: { green: '相對成長性，價格合理', yellow: '價格大致合理', red: '相對成長性偏貴' },
  grahamTagline: { green: '低於內在價值', yellow: '接近合理價值', red: '高於內在價值' },
  line: {
    checklist: '檢查表',
    tier: '等級',
    lynchValue: '價值 (G+D)',
    pegBand: 'PEG 價格帶',
    valuation: '估值',
    defensive: '防禦性',
  },
  status: {
    'Strong Buy': '強力買進',
    'Deep Buy': '深度買進',
    Buy: '買進',
    Hold: '持有',
    Watch: '觀察',
    Avoid: '避開',
    Pass: '通過',
    Borderline: '邊緣',
    Fail: '未通過',
    Cheap: '便宜',
    Reasonable: '合理',
    Rich: '偏貴',
  },
}

export const MESSAGES: Record<Lang, Messages> = { en, 'zh-TW': zhTW }

// A backend grade ("Strong Buy", "Pass", "N/A") as this language shows it.
export function statusLabel(m: Messages, s: string): string {
  return m.status[s] ?? s
}
