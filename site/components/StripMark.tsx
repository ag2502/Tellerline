// Tellerline's mark: a call as three bars, the caller's two in ink, Tellerline's reply in the accent.
export function StripMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 34 18" className={className} aria-hidden="true">
      <rect x="1" y="5" width="6" height="8" rx="3" fill="#4fe3c8" />
      <rect x="10" y="1" width="6" height="16" rx="3" fill="#4fe3c8" />
      <rect x="19" y="3" width="6" height="12" rx="3" fill="#ff6b8b" />
      <rect x="28" y="6.5" width="5" height="5" rx="2.5" fill="#ff6b8b" />
    </svg>
  );
}
