import { ArrowIcon } from "../icons";
import { source } from "../links";

// A bay of the board: its plate (the key that jumps to it), its title, and the command that
// produced what it shows.
export function Section({
  id,
  number,
  title,
  command,
  children,
}: {
  id: string;
  number: number;
  title: string;
  command: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="bay relative z-10 border-t border-rail">
      <div className="mx-auto max-w-[90rem]">
        <div className="flex items-start gap-4 sm:gap-5" data-reveal-target="">
          <span className="plate mt-1 shrink-0 sm:mt-2" aria-hidden="true">
            {number}
          </span>
          <div className="min-w-0">
            <h2 id={`${id}-title`} className="headline text-[clamp(2.2rem,1.1rem+3.6vw,4.75rem)]">
              {title}
            </h2>
            <p className="mt-3 flex flex-wrap items-baseline gap-x-2 gap-y-1 text-[0.85rem]">
              <span className="label">from</span>
              <code className="text-ink-2 [overflow-wrap:anywhere]">{command}</code>
            </p>
          </div>
        </div>
        <div className="mt-12 sm:mt-14">{children}</div>
      </div>
    </section>
  );
}

// A link to the file in the repository a number came from.
export function Source({ file, children }: { file: string; children?: React.ReactNode }) {
  return (
    <a
      className="inline-flex items-center gap-1.5 text-[0.85rem] font-semibold text-ink-2 no-underline hover:text-ink"
      href={source(file)}
    >
      {children ?? file}
      <ArrowIcon className="h-3.5 w-3.5" />
    </a>
  );
}

// A strip with a label box on the left, or above on a phone: the page's one way of laying out a
// fact.
export function FactStrip({
  label,
  children,
  holder = "plain",
  labelWidth = "8.5rem",
}: {
  label: React.ReactNode;
  children: React.ReactNode;
  holder?: "plain" | "caller" | "agent";
  labelWidth?: string;
}) {
  return (
    <div className={`holder-${holder}`}>
      <div
        className="strip grid grid-cols-1 items-stretch sm:grid-cols-[minmax(0,var(--label-w))_minmax(0,1fr)]"
        style={{ "--label-w": labelWidth } as React.CSSProperties}
      >
        <div className="box label flex items-center border-b border-rule pb-1 pt-1.5 sm:border-b-0 sm:py-[0.45rem]">{label}</div>
        <div className="box min-w-0 border-l-0 sm:border-l">{children}</div>
      </div>
    </div>
  );
}
