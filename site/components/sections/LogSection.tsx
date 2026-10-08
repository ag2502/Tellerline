import { data, recentCommits } from "@/lib/data";
import type { Decision } from "@/lib/types";

import { ArrowIcon } from "../icons";
import { REPO } from "../links";
import { Section, Source } from "./Section";

const SHOWN = 6; // the newest decisions on the board; the rest are filed behind them

export async function LogSection({ number }: { number: number }) {
  const decisions = [...data.decisions].reverse();
  const shown = decisions.slice(0, SHOWN);
  const filed = decisions.slice(SHOWN);
  const commits = await recentCommits();
  return (
    <Section id="log" number={number} title="Every decision, with the measurement behind it" command="git log docs/DECISIONS.md">
      <div className="grid gap-x-14 gap-y-16 xl:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        <div>
          <p className="prose-width mb-7 text-[1.05rem] leading-relaxed text-ink-2">
            {decisions.length} decisions so far, newest first. Each says what was chosen, why, what
            it measured and what was tried instead. Pull a strip to read it.
          </p>
          <ol className="flex flex-col gap-1.5">
            {shown.map((item) => (
              <li key={item.id}>
                <DecisionStrip item={item} />
              </li>
            ))}
          </ol>
          {filed.length ? (
            <details className="group/filed mt-4">
              <summary className="flex w-fit items-center gap-2 text-[0.92rem] font-semibold text-ink-2 hover:text-ink">
                <ArrowIcon className="h-3.5 w-3.5 rotate-90 transition-transform duration-200 group-open/filed:-rotate-90" />
                <span className="group-open/filed:hidden">The {filed.length} earlier decisions</span>
                <span className="hidden group-open/filed:inline">Put the earlier decisions back</span>
              </summary>
              <ol className="mt-4 flex flex-col gap-1.5">
                {filed.map((item) => (
                  <li key={item.id}>
                    <DecisionStrip item={item} />
                  </li>
                ))}
              </ol>
            </details>
          ) : null}
          <p className="mt-7">
            <Source file="docs/DECISIONS.md">The whole log</Source>
          </p>
        </div>

        <div>
          <h3 className="headline text-[1.6rem]">Latest commits</h3>
          <p className="mt-2 text-[0.95rem] text-ink-2">From the repository, refreshed every hour.</p>
          {commits.length ? (
            <ol className="mt-6 flex flex-col gap-1.5">
              {commits.map((commit) => (
                <li key={commit.sha} className="holder-plain">
                  <div className="strip grid grid-cols-[5.75rem_minmax(0,1fr)]">
                    <div className="box">
                      <a href={commit.url} className="print text-[0.85rem] font-semibold text-blue-ink">
                        {commit.sha}
                      </a>
                    </div>
                    <div className="box">
                      <span className="block leading-snug">{commit.message}</span>
                      <span className="block text-[0.78rem] text-ink-3">{relative(commit.date)}</span>
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          ) : (
            <p className="mt-6 text-ink-2">
              GitHub didn&apos;t answer just now. <a href={`${REPO}/commits/main`}>See the commits there</a>.
            </p>
          )}
        </div>
      </div>
    </Section>
  );
}

// A decision filed as a strip: its designator, date and title. Pulling it opens the record.
function DecisionStrip({ item }: { item: Decision }) {
  const parts: [string, string | undefined][] = [
    ["decision", item.decision],
    ["why", item.why],
    ["result", item.result],
    ["considered", item.considered],
  ];
  return (
    <details className="group holder-plain transition-[transform,box-shadow] duration-200 open:-translate-y-0.5 open:shadow-[var(--lift-high)]">
      <summary className="strip grid grid-cols-[4.25rem_minmax(0,1fr)_auto] items-center sm:grid-cols-[4.75rem_6.75rem_minmax(0,1fr)_auto] hover:bg-[#fafbfc]">
        <span className="box print text-[0.88rem] font-semibold">{item.id}</span>
        <span className="box print hidden text-[0.8rem] text-ink-3 sm:block">{item.date}</span>
        <span className="box font-medium leading-snug">{item.title}</span>
        <span className="box flex items-center gap-1.5 self-stretch text-[0.72rem] font-semibold uppercase tracking-[0.08em] text-ink-2">
          <span className="hidden sm:inline group-open:hidden">Pull</span>
          <span className="hidden sm:group-open:inline">Put back</span>
          <ArrowIcon className="h-3.5 w-3.5 rotate-90 transition-transform duration-200 group-open:-rotate-90" />
        </span>
      </summary>
      <div className="strip mt-[3px] grid gap-0 py-1 print-in">
        <p className="box text-[0.8rem] text-ink-3 sm:hidden">{item.date}</p>
        {parts.map(([label, text]) =>
          text ? (
            <div key={label} className="grid gap-x-4 border-t border-rule px-[0.7rem] py-2.5 first:border-t-0 sm:grid-cols-[6.5rem_minmax(0,1fr)]">
              <span className="label pt-1">{label}</span>
              <p className={`prose-width text-[0.94rem] leading-relaxed ${label === "considered" ? "text-ink-2" : ""}`}>
                <Inline text={text} />
              </p>
            </div>
          ) : null,
        )}
      </div>
    </details>
  );
}

// The log's own `code` spans, printed as code.
function Inline({ text }: { text: string }) {
  return text.split(/(`[^`]+`)/).map((part, index) =>
    part.startsWith("`") && part.endsWith("`") ? (
      <code key={index} className="text-[0.88em] text-blue-ink">
        {part.slice(1, -1)}
      </code>
    ) : (
      part
    ),
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
