// Tellerline's mark: one flight strip in its holder, the caller's end amber, Tellerline's blue.
export function StripMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 34 18" className={className} aria-hidden="true">
      <rect x="0" y="0" width="17" height="18" rx="3" fill="#f2c14e" />
      <rect x="17" y="0" width="17" height="18" rx="3" fill="#2f6fd6" />
      <rect x="11" y="0" width="12" height="18" fill="#2f6fd6" />
      <rect x="11" y="0" width="6" height="18" fill="#f2c14e" />
      <rect x="5" y="3" width="24" height="12" rx="1.5" fill="#ffffff" />
      <rect x="8" y="6.5" width="9" height="2" rx="1" fill="#16191d" />
      <rect x="8" y="10" width="14" height="1.5" rx="0.75" fill="#9aa3ad" />
    </svg>
  );
}
