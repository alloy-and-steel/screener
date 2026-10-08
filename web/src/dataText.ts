// English text the screener writes INTO the data (sector names, "why N/A"
// notes, DCF notes, research flags, error rows), translated for display. The
// backend joins phrases with "; ", so each phrase is translated on its own; one
// this table doesn't know stays English rather than vanishing.
// dataText.test.ts diffs this against every phrase stock_screener.py emits.

import type { Lang } from './i18n'

const SECTOR_ZH: Record<string, string> = {
  'Basic Materials': '原物料',
  'Communication Services': '通訊服務',
  'Consumer Cyclical': '非必需消費',
  'Consumer Defensive': '必需消費',
  Energy: '能源',
  'Financial Services': '金融服務',
  Healthcare: '醫療保健',
  Industrials: '工業',
  'Real Estate': '不動產',
  Technology: '科技',
  Utilities: '公用事業',
}

export function sectorLabel(sector: string, lang: Lang): string {
  return lang === 'zh-TW' ? (SECTOR_ZH[sector] ?? sector) : sector
}

// Every Chinese sector name, for search: typing 科技 finds Technology names.
export function sectorMatches(sector: string, query: string): boolean {
  return sector.toUpperCase().includes(query) || (SECTOR_ZH[sector] ?? '').includes(query)
}

const MISSING_INPUT_ZH: Record<string, string> = {
  'risk-free rate': '無風險利率',
  'market cap': '市值',
  'total debt': '總債務',
  cash: '現金',
  'diluted shares': '稀釋後股數',
  'base FCFF': '基期 FCFF',
  'compatible price and financial currencies': '一致的股價與財報幣別',
}

const PHRASE_ZH: Record<string, string> = {
  // Valuation_Input_Warning
  'Non-positive EPS': 'EPS 非正值',
  'EPS unavailable': '缺少 EPS',
  'Growth unavailable': '缺少成長率',
  // Trap_Reasons
  'High leverage': '高槓桿',
  'Weak liquidity': '流動性偏弱',
  'Unstable earnings': '盈餘不穩定',
  'Negative FCF': '自由現金流為負',
  // DCF_Data_Warning
  'Currency metadata incomplete': '幣別資料不完整',
  'Non-positive base FCFF': '基期 FCFF 非正值',
  'Beta unavailable': '缺少 Beta',
  'Interest expense unavailable': '缺少利息費用',
  'AAA debt cost used': '改以 AAA 債券殖利率作為舉債成本',
  'High leverage makes DCF equity value highly sensitive': '槓桿偏高，DCF 股權價值極為敏感',
  'Stressed DCF case implies zero common-equity value': '壓力情境下 DCF 普通股價值為零',
  'DCF excluded': '不計入 DCF',
  // DCF_Method, Error
  'FCFF screen-grade': 'FCFF 篩選級',
  'No price': '無股價',
}

const PATTERN_ZH: [RegExp, (...g: string[]) => string][] = [
  [/^Non-positive growth \((.+)%\)$/, (g) => `成長率非正值（${g}%）`],
  [/^defaulted to (.+)$/, (v) => `以 ${v} 代入`],
  [/^WACC guardrail applied \((.+)% to (.+)%\)$/, (a, b) => `WACC 已套用下限（${a}% 調至 ${b}%）`],
  [/^Terminal value exceeds (.+)% of EV$/, (p) => `終值占企業價值逾 ${p}%`],
  [/^Currency mismatch \((\S+) price vs (\S+) financials\)$/, (p, f) => `幣別不一致（股價為 ${p}、財報為 ${f}）`],
  [/^Missing (.+)$/, (list) => `缺少${list.split(', ').map((i) => MISSING_INPUT_ZH[i] ?? i).join('、')}`],
  [/^Processing failed: (.*)$/, (why) => `處理失敗：${why}`],
]

function phraseZh(p: string): string {
  const exact = PHRASE_ZH[p]
  if (exact) return exact
  for (const [re, f] of PATTERN_ZH) {
    const m = p.match(re)
    if (m) return f(...m.slice(1))
  }
  return p
}

export function dataNote(text: string, lang: Lang): string {
  if (lang === 'en') return text
  return text.split('; ').map(phraseZh).join('；')
}
