import type { ColumnDef, VisibilityState } from '@tanstack/react-table'
import type { Azqato, AzqatoMetricKey, Row } from './types'
import { DASH, TONE, VerdictPill, compactUsd, num, pct, ptsTone, ratio, signalTone } from './format'
import { azCashDebt, azPegDisplay, azqatoVerdict, combinedVerdict, grahamVerdict, lynchVerdict, type Verdict } from './score'

export interface ColMeta {
  summary?: boolean
  align?: 'right'
  pinned?: boolean
}

function numLeaf(key: string, header: string, decimals = 2, summary = false, size = 84): ColumnDef<Row> {
  return {
    accessorKey: key,
    header,
    size,
    cell: ({ getValue }) => num(getValue(), decimals),
    meta: { summary, align: 'right' } satisfies ColMeta,
  }
}

function pctLeaf(key: string, header: string, summary = false, size = 92): ColumnDef<Row> {
  return {
    accessorKey: key,
    header,
    size,
    cell: ({ getValue }) => pct(getValue()),
    meta: { summary, align: 'right' } satisfies ColMeta,
  }
}

// Categorical status field rendered as tinted text (Full preset only).
function signalLeaf(key: string, header: string, size = 116): ColumnDef<Row> {
  return {
    accessorKey: key,
    header,
    size,
    cell: ({ getValue }) => {
      const v = getValue() as string | null | undefined
      return v ? <span className={`text-[11px] font-medium ${TONE[signalTone(key, v)].text}`}>{v}</span> : DASH
    },
    meta: {} satisfies ColMeta,
  }
}

function textLeaf(key: string, header: string, size = 150): ColumnDef<Row> {
  return {
    accessorKey: key,
    header,
    size,
    cell: ({ getValue }) => (getValue() as string) ?? DASH,
    meta: {} satisfies ColMeta,
  }
}

function verdictLeaf(id: string, fn: (r: Row) => Verdict, size = 108): ColumnDef<Row> {
  return {
    id,
    header: 'Verdict',
    size,
    accessorFn: (r) => fn(r).level, // sortable: Buy/Pass > Hold > Avoid/Fail
    sortDescFirst: true,
    cell: ({ row }) => {
      // A not-valued name (declining / growth-unknown) renders a muted slate
      // "N/A" pill — a distinct signal from a numeric dash, never a bare gap that
      // would read as a fetch failure.
      const v = fn(row.original)
      return (
        <VerdictPill tone={v.tone} colors={v.pillColors}>
          {v.label}
        </VerdictPill>
      )
    },
    meta: { summary: true } satisfies ColMeta,
  }
}

function worstIfNonPositive(v: number | null): number | null {
  return v !== null && v <= 0 ? Infinity : v
}

// Azqato metric cell, tinted by the stock's percentile points on that metric
// (green = top of the pack, red = bottom or missing-on-a-scored-metric, amber =
// middle). `sortOn` overrides the sort value for derived metrics (peVsG,
// display PEG, cash/debt ratio).
function azMetricLeaf(
  key: AzqatoMetricKey,
  header: string,
  fmt: (az: Azqato) => string,
  opts: { scored?: boolean; sortOn?: (az: Azqato) => number | null } = {},
): ColumnDef<Row> {
  const { scored = true, sortOn } = opts
  return {
    id: `azqato_${key}`,
    header,
    size: 88,
    accessorFn: (r) => (r.azqato ? (sortOn ? sortOn(r.azqato) : (r.azqato[key as keyof Azqato] as number | null)) : null),
    cell: ({ row }) => {
      const az = row.original.azqato
      if (!az) return DASH
      return <span className={TONE[ptsTone(az.parts?.[key], scored)].text}>{fmt(az)}</span>
    },
    meta: { align: 'right' } satisfies ColMeta,
  }
}

export const columns: ColumnDef<Row>[] = [
  {
    accessorKey: 'Ticker',
    header: 'Ticker',
    size: 96,
    cell: ({ getValue }) => <span className="font-mono text-[13px] font-semibold text-slate-100">{getValue() as string}</span>,
    meta: { summary: true, pinned: true } satisfies ColMeta,
  },
  {
    id: 'combined',
    header: 'Pass',
    size: 76,
    accessorFn: (r) => combinedVerdict(r).passCount,
    sortDescFirst: true,
    cell: ({ row }) => {
      const c = combinedVerdict(row.original)
      return (
        <VerdictPill tone={c.tone} glyph={false}>
          {c.passCount}/3
        </VerdictPill>
      )
    },
    meta: { summary: true } satisfies ColMeta,
  },

  {
    id: 'g_azqato',
    header: 'Azqato',
    columns: [
      verdictLeaf('azqato_verdict', azqatoVerdict, 76),
      {
        id: 'azqato_score',
        header: 'Score',
        size: 76,
        // `!= null` on tier gates out a stale pre-tier dataset shape too.
        accessorFn: (r) => (r.azqato?.tier != null ? r.azqato.score : null),
        sortDescFirst: true,
        cell: ({ getValue }) => {
          const s = getValue() as number | null | undefined
          return typeof s === 'number' ? `${s}/100` : DASH
        },
        meta: { summary: true, align: 'right' } satisfies ColMeta,
      },
      {
        id: 'azqato_factors',
        header: 'Factors',
        size: 78,
        accessorFn: (r) => (r.azqato?.total ? (r.azqato.passes ?? 0) / r.azqato.total : null),
        sortDescFirst: true,
        cell: ({ row }) => {
          const az = row.original.azqato
          return az?.total ? `${az.passes}/${az.total}` : DASH
        },
        meta: { align: 'right' } satisfies ColMeta,
      },
      azMetricLeaf('revTTM', 'Rev TTM', (az) => pct(az.revTTM)),
      azMetricLeaf('revFwd', 'Rev FWD', (az) => pct(az.revFwd)),
      azMetricLeaf('epsTTM', 'EPS TTM', (az) => pct(az.epsTTM)),
      azMetricLeaf('epsFwd', 'EPS FWD', (az) => pct(az.epsFwd)),
      // Sorting: a negative P/E or PEG is "worst" (unprofitable) — sort it like
      // a very high value rather than a cheap low one (screener.js sortRows).
      azMetricLeaf('peVsG', 'P/E FWD', (az) => num(az.peFwd), { scored: false, sortOn: (az) => worstIfNonPositive(az.peFwd) }),
      azMetricLeaf('pegFwd', 'PEG FWD', (az) => num(azPegDisplay(az)), { sortOn: (az) => worstIfNonPositive(azPegDisplay(az)) }),
      {
        id: 'azqato_cash',
        header: 'Cash',
        size: 88,
        accessorFn: (r) => r.azqato?.cash,
        cell: ({ getValue }) => compactUsd(getValue()),
        meta: { align: 'right' } satisfies ColMeta,
      },
      {
        id: 'azqato_debt',
        header: 'Debt',
        size: 88,
        accessorFn: (r) => r.azqato?.debt,
        cell: ({ getValue }) => compactUsd(getValue()),
        meta: { align: 'right' } satisfies ColMeta,
      },
      azMetricLeaf('cashDebt', 'Cash/Debt', (az) => ratio(azCashDebt(az)), { sortOn: azCashDebt }),
      {
        id: 'azqato_rsi',
        header: 'RSI(14)',
        size: 84,
        accessorFn: (r) => r.azqato?.rsi,
        cell: ({ getValue }) => num(getValue(), 1),
        meta: { align: 'right' } satisfies ColMeta,
      },
      {
        id: 'azqato_52w',
        header: '52w pos',
        size: 88,
        accessorFn: (r) => r.azqato?.pos_52w_pct,
        cell: ({ getValue }) => pct(getValue()),
        meta: { align: 'right' } satisfies ColMeta,
      },
    ],
  },

  {
    id: 'g_lynch',
    header: 'Lynch',
    columns: [
      verdictLeaf('lynch_verdict', lynchVerdict),
      numLeaf('Lynch_Lynch_Score', 'Score', 2, true),
      numLeaf('Lynch_PE', 'P/E', 2),
      numLeaf('Lynch_PEG', 'PEG', 2, true),
      numLeaf('Lynch_Lynch_BuyPrice', 'Buy price', 2),
      pctLeaf('Lynch_Lynch_Discount_Pct', 'Discount'),
      signalLeaf('Lynch_Lynch_PEG_Band', 'PEG band'),
      signalLeaf('Lynch_PEG_Status', 'PEG status'),
      signalLeaf('Lynch_PEGY_Status', 'PEGY status'),
    ],
  },

  {
    id: 'g_graham',
    header: 'Graham',
    columns: [
      verdictLeaf('graham_verdict', grahamVerdict),
      {
        accessorKey: 'DefensiveScore',
        header: 'Defensive',
        size: 88,
        cell: ({ getValue }) => {
          const v = getValue()
          return typeof v === 'number' ? `${v}/8` : DASH
        },
        meta: { align: 'right' } satisfies ColMeta,
      },
      signalLeaf('DefensiveLabel', 'Safety'),
      numLeaf('Graham_Graham_FV', 'Fair value', 2),
      pctLeaf('Graham_Graham_Discount_Pct', 'Discount', true),
    ],
  },

  {
    id: 'g_overall',
    header: 'Overall',
    columns: [
      numLeaf('OverallScore', 'Score', 1, true, 76),
      numLeaf('scores.value', 'Value', 1),
      numLeaf('scores.quality', 'Quality', 1),
      numLeaf('scores.growth', 'Growth', 1),
      numLeaf('scores.safety', 'Safety', 1),
      textLeaf('Sector', 'Sector'),
      {
        accessorKey: 'Piotroski_F',
        header: 'Piotroski',
        size: 84,
        cell: ({ getValue }) => {
          const v = getValue()
          return typeof v === 'number' ? `${v}/9` : DASH
        },
        meta: { align: 'right' } satisfies ColMeta,
      },
      numLeaf('Altman_Z', 'Altman Z', 2),
      pctLeaf('DCF_Discount_Pct', 'DCF disc.'),
      textLeaf('Trap_Reasons', 'Trap flags', 160),
    ],
  },

  {
    id: 'g_snapshot',
    header: 'Snapshot',
    columns: [
      numLeaf('Price', 'Price', 2, true),
      numLeaf('EPS_TTM', 'EPS TTM', 2),
      {
        accessorKey: 'MarketCap_B',
        header: 'Mkt cap',
        size: 92,
        cell: ({ getValue }) => {
          const v = getValue()
          return typeof v === 'number' ? `${num(v, 1)}B` : DASH
        },
        meta: { summary: true, align: 'right' } satisfies ColMeta,
      },
      pctLeaf('Growth_g_Pct', 'Growth', true),
      pctLeaf('DivYield_Pct', 'Div yld'),
      numLeaf('PB_Ratio', 'P/B', 2),
      textLeaf('Indexes', 'Indexes'),
    ],
  },
]

function leaves(cols: ColumnDef<Row>[]): ColumnDef<Row>[] {
  return cols.flatMap((c) => ((c as { columns?: ColumnDef<Row>[] }).columns ? leaves((c as { columns: ColumnDef<Row>[] }).columns) : [c]))
}

function colId(c: ColumnDef<Row>): string {
  return (c.id ?? (c as { accessorKey?: string }).accessorKey ?? '') as string
}

export function presetVisibility(preset: 'summary' | 'full'): VisibilityState {
  if (preset === 'full') return {}
  const vis: VisibilityState = {}
  for (const c of leaves(columns)) {
    vis[colId(c)] = Boolean((c.meta as ColMeta | undefined)?.summary)
  }
  return vis
}

export interface PickerGroup {
  group: string
  items: { id: string; header: string }[]
}

// Catalog for the column picker — every toggleable column grouped by system
// (Ticker is pinned/always on and excluded).
export const pickerGroups: PickerGroup[] = (() => {
  const out: PickerGroup[] = []
  const general: { id: string; header: string }[] = []
  const headerOf = (c: ColumnDef<Row>) => (typeof c.header === 'string' ? c.header : colId(c))
  for (const c of columns) {
    const sub = (c as { columns?: ColumnDef<Row>[] }).columns
    if (sub) {
      out.push({ group: headerOf(c), items: sub.map((s) => ({ id: colId(s), header: headerOf(s) })) })
    } else if (colId(c) !== 'Ticker') {
      general.push({ id: colId(c), header: headerOf(c) })
    }
  }
  return general.length ? [{ group: 'General', items: general }, ...out] : out
})()
