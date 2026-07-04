import { useRef } from 'react'
import { flexRender, getCoreRowModel, getSortedRowModel, useReactTable } from '@tanstack/react-table'
import type { ColumnDef, OnChangeFn, SortingState, VisibilityState } from '@tanstack/react-table'
import { useVirtualizer } from '@tanstack/react-virtual'
import type { Row } from './types'
import type { ColMeta } from './columns'
import { TONE } from './format'
import { combinedVerdict } from './score'

const ROW_HEIGHT = 32

// Columns grow to fill the container when there's spare width (so the grid
// always spans full width), and never shrink — when they overflow (Full
// preset), the table keeps its natural width and scrolls horizontally.
const cell = (size: number) => ({ flexGrow: size, flexShrink: 0, flexBasis: `${size}px` })

interface DataTableProps {
  data: Row[]
  columns: ColumnDef<Row>[]
  sorting: SortingState
  onSortingChange: OnChangeFn<SortingState>
  columnVisibility: VisibilityState
  onRowClick: (row: Row) => void
}

export default function DataTable({ data, columns, sorting, onSortingChange, columnVisibility, onRowClick }: DataTableProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  const table = useReactTable({
    data,
    columns,
    state: { sorting, columnVisibility },
    onSortingChange,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  const rows = table.getRowModel().rows
  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => containerRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 14,
  })

  const totalWidth = table.getVisibleLeafColumns().reduce((acc, c) => acc + c.getSize(), 0)
  const headerGroups = table.getHeaderGroups()

  // Vertical dividers between scoring groups (Azqato | Lynch | Graham |
  // Snapshot): the first leaf of each group gets a left border.
  const groupStartIds = new Set<string>()
  let prevParent: string | undefined
  for (const c of table.getVisibleLeafColumns()) {
    const parentId = c.parent?.id
    if (parentId !== undefined && parentId !== prevParent) groupStartIds.add(c.id)
    prevParent = parentId
  }

  return (
    <div ref={containerRef} className="h-full overflow-auto bg-surface-1">
      <div className="relative w-full" style={{ minWidth: totalWidth }}>
        {/* Two-level sticky header: group band (Azqato / Lynch / Graham) + leaves */}
        <div className="sticky top-0 z-20">
          {headerGroups.map((hg, gi) => {
            const isBand = gi === 0 && headerGroups.length > 1
            return (
              <div key={hg.id} className="flex bg-surface-2">
                {hg.headers.map((header) => {
                  const meta = header.column.columnDef.meta as ColMeta | undefined
                  const pinned = meta?.pinned
                  if (isBand) {
                    return (
                      <div
                        key={header.id}
                        style={cell(header.getSize())}
                        className={`flex h-6 items-center justify-center border-b border-hairline text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-500 ${
                          header.isPlaceholder ? '' : 'border-l border-edge'
                        } ${pinned ? 'sticky left-0 z-30 bg-surface-2' : ''}`}
                      >
                        {header.isPlaceholder ? '' : flexRender(header.column.columnDef.header, header.getContext())}
                      </div>
                    )
                  }
                  const sorted = header.column.getIsSorted()
                  return (
                    <div
                      key={header.id}
                      style={cell(header.getSize())}
                      onClick={header.column.getToggleSortingHandler()}
                      className={`flex h-9 cursor-pointer select-none items-center gap-1 border-b border-hairline px-3 text-[10px] font-semibold uppercase tracking-[0.06em] text-slate-400 hover:text-slate-200 ${
                        meta?.align === 'right' ? 'justify-end' : ''
                      } ${groupStartIds.has(header.column.id) ? 'border-l border-edge' : ''} ${
                        pinned ? 'sticky left-0 z-30 bg-surface-2' : ''
                      }`}
                    >
                      <span className="truncate">{flexRender(header.column.columnDef.header, header.getContext())}</span>
                      <span className="w-2 shrink-0 text-[8px] text-sky-400">{sorted === 'asc' ? '▲' : sorted === 'desc' ? '▼' : ''}</span>
                    </div>
                  )
                })}
              </div>
            )
          })}
        </div>

        {/* Virtualized body */}
        <div className="relative w-full" style={{ height: virtualizer.getTotalSize() }}>
          {virtualizer.getVirtualItems().map((vi) => {
            const row = rows[vi.index]
            const c = combinedVerdict(row.original)
            return (
              <div
                key={row.id}
                onClick={() => onRowClick(row.original)}
                style={{ transform: `translateY(${vi.start}px)`, height: ROW_HEIGHT }}
                className="group absolute left-0 top-0 flex w-full cursor-pointer border-b border-hairline hover:bg-surface-3"
              >
                {row.getVisibleCells().map((cellCtx) => {
                  const meta = cellCtx.column.columnDef.meta as ColMeta | undefined
                  const pinned = meta?.pinned
                  return (
                    <div
                      key={cellCtx.id}
                      style={cell(cellCtx.column.getSize())}
                      className={`flex items-center overflow-hidden whitespace-nowrap px-3 text-[12px] text-slate-200 ${
                        meta?.align === 'right' ? 'justify-end tnum' : ''
                      } ${groupStartIds.has(cellCtx.column.id) ? 'border-l border-edge' : ''} ${
                        pinned ? `sticky left-0 z-10 border-l-[3px] bg-surface-1 group-hover:bg-surface-3 ${TONE[c.tone].border}` : ''
                      }`}
                    >
                      {flexRender(cellCtx.column.columnDef.cell, cellCtx.getContext())}
                    </div>
                  )
                })}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
