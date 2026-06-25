// Flat, minimalist mark: three tapering bars — a filter/funnel that screens
// down to the names passing all three systems. Uses currentColor so it themes.
export function Logo({ className = 'h-5 w-5' }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden>
      <rect x="3" y="5" width="18" height="3.4" rx="1.7" />
      <rect x="6.5" y="10.3" width="11" height="3.4" rx="1.7" />
      <rect x="10" y="15.6" width="4" height="3.4" rx="1.7" />
    </svg>
  )
}
