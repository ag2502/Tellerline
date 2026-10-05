import { data, recentCommits } from "@/lib/data";

import { Section, Source } from "./Section";

export async function LogSection() {
  const decisions = [...data.decisions].reverse();
  const commits = await recentCommits();
  return (
    <Section id="log" title="Every decision, with the measurement behind it" command="git log docs/DECISIONS.md">
      <div className="grid gap-16 xl:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        <div>
          <p className="dim mb-6 max-w-[62ch]">
            {decisions.length} decisions so far, newest first. Each says what was chosen, why, and
            what was tried instead; open one to read it.
          </p>
          <ol className="space-y-0.5">
            {decisions.map((item) => (
              <li key={item.id}>
                <details className="group">
                  <summary className="grid grid-cols-[6ch_1fr] gap-x-[1ch] py-1 hover:bg-glass sm:grid-cols-[6ch_11ch_1fr]">
                    <span className="bloom">{item.id}</span>
                    <span className="dim hidden tabular sm:block">{item.date}</span>
                    <span className="min-w-0">
                      <span className="after group-open:hidden" aria-hidden="true">
                        +{" "}
                      </span>
                      <span className="after hidden group-open:inline" aria-hidden="true">
                        -{" "}
                      </span>
                      {item.title}
                    </span>
                  </summary>
                  <div className="mb-4 ml-[7ch] mt-2 max-w-[70ch] space-y-3 text-[0.95em] sm:ml-[19ch]">
                    {item.decision ? (
                      <p>
                        <span className="dim">decision </span>
                        {item.decision}
                      </p>
                    ) : null}
                    {item.why ? (
                      <p>
                        <span className="dim">why </span>
                        {item.why}
                      </p>
                    ) : null}
                    {item.result ? (
                      <p>
                        <span className="dim">result </span>
                        {item.result}
                      </p>
                    ) : null}
                    {item.considered ? (
                      <p className="dim">
                        <span>considered </span>
                        {item.considered}
                      </p>
                    ) : null}
                  </div>
                </details>
              </li>
            ))}
          </ol>
          <p className="mt-6">
            <Source file="docs/DECISIONS.md">The whole log</Source>
          </p>
        </div>

        <div>
          <h3 className="bloom mb-2">Latest commits</h3>
          <p className="dim mb-5 text-[0.95em]">From the repository, refreshed every hour.</p>
          {commits.length ? (
            <ol className="space-y-3">
              {commits.map((commit) => (
                <li key={commit.sha} className="grid grid-cols-[8ch_1fr] gap-x-[1ch]">
                  <a href={commit.url} className="bloom tabular no-underline hover:underline">
                    {commit.sha}
                  </a>
                  <span className="min-w-0">
                    {commit.message}
                    <span className="dim block text-[0.85em]">{relative(commit.date)}</span>
                  </span>
                </li>
              ))}
            </ol>
          ) : (
            <p className="dim">
              GitHub didn&apos;t answer just now.{" "}
              <a href="https://github.com/ag2502/Tellerline/commits/main">See the commits there</a>.
            </p>
          )}
        </div>
      </div>
    </Section>
  );
}

function relative(iso: string): string {
  const hours = (Date.now() - new Date(iso).getTime()) / 3_600_000;
  if (hours < 1) return "within the hour";
  if (hours < 24) return `${Math.round(hours)} hour${Math.round(hours) === 1 ? "" : "s"} ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days} day${days === 1 ? "" : "s"} ago`;
  return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}
