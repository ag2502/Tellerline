// A window of the session: a heading written as a shell comment, the real command that produced
// what follows, then its output.
export function Section({
  id,
  title,
  command,
  children,
}: {
  id: string;
  title: string;
  command: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="window border-t border-scan">
      <div className="mx-auto max-w-[80rem]">
        <h2 id={`${id}-title`} className="cmd">
          <span className="prompt" aria-hidden="true">
            #{" "}
          </span>
          {title}
        </h2>
        <p className="mt-3 break-words text-[0.95em]">
          <span className="dim" aria-hidden="true">
            ${" "}
          </span>
          <code>{command}</code>
        </p>
        <div className="mt-10">{children}</div>
      </div>
    </section>
  );
}

export function Source({ file, children }: { file: string; children?: React.ReactNode }) {
  return (
    <a className="dim text-[0.85em]" href={`https://github.com/ag2502/Tellerline/blob/main/${file}`}>
      {children ?? file}
    </a>
  );
}
