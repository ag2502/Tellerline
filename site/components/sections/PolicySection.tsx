import { data } from "@/lib/data";

import { FactStrip, Section, Source } from "./Section";

// What a caller can reach is decided by code and by the bank's API, not by the prompt.
type Reach = "yes" | "done" | "no" | "a colleague" | "refused";

const MATRIX: { what: string; unverified: Reach; verified: Reach }[] = [
  { what: "check who they are", unverified: "yes", verified: "done" },
  { what: "balances and recent payments", unverified: "no", verified: "yes" },
  { what: "freeze, unfreeze or replace a card", unverified: "no", verified: "yes" },
  { what: "ask whether a card is frozen", unverified: "no", verified: "yes" },
  { what: "open a dispute", unverified: "no", verified: "yes" },
  { what: "anyone else's account", unverified: "no", verified: "no" },
  { what: "move money, loans, hardship", unverified: "a colleague", verified: "a colleague" },
  { what: "a full card number or PIN", unverified: "refused", verified: "refused" },
];

const COLUMNS = "sm:grid-cols-[minmax(0,1fr)_9.75rem_9.75rem]";

export function PolicySection({ number }: { number: number }) {
  const copied = data.examples.find((item) => item.case === "h-verify-double-oh");
  const invented = data.examples.find((item) => item.case === "h-unfreeze-no-digits");
  const template = data.template;
  return (
    <Section id="policy" number={number} title="The model decides; code owns the facts" command="less src/tellerline/brain.py">
      <div className="grid gap-x-14 gap-y-20 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
        <div>
          <h3 className="headline text-[1.6rem]">What a caller can reach</h3>
          <p className="prose-width mt-3 text-[0.95rem] leading-relaxed text-ink-2">
            Before verification only the identity check can run, whatever the model writes; the
            bank&apos;s API is scoped to the verified customer, so another customer&apos;s data is out
            of reach by construction.
          </p>
          <div className={`label mt-7 hidden pl-[calc(10px+0.7rem)] pr-[3px] sm:grid ${COLUMNS}`} aria-hidden="true">
            <span>request</span>
            <span className="pl-[0.7rem]">not verified</span>
            <span className="pl-[0.7rem]">verified</span>
          </div>
          <ul className="mt-6 flex flex-col gap-1.5 sm:mt-2">
            {MATRIX.map((row) => (
              <li key={row.what} className="holder-plain">
                <dl className={`strip grid grid-cols-2 ${COLUMNS}`}>
                  <div className="box col-span-2 border-b border-rule sm:col-span-1 sm:border-b-0">
                    <dt className="sr-only">request</dt>
                    <dd className="m-0 font-medium">{row.what}</dd>
                  </div>
                  <div className="box border-l-0 sm:border-l">
                    <dt className="label sm:sr-only">not verified</dt>
                    <dd className="m-0 pt-0.5">
                      <Stamp reach={row.unverified} />
                    </dd>
                  </div>
                  <div className="box">
                    <dt className="label sm:sr-only">verified</dt>
                    <dd className="m-0 pt-0.5">
                      <Stamp reach={row.verified} />
                    </dd>
                  </div>
                </dl>
              </li>
            ))}
          </ul>
          <p className="prose-width mt-7 text-[0.95rem] leading-relaxed text-ink-2">
            Every call opens by saying it is an AI. A reply never starts over a caller who carries
            on after a pause, and nothing reaches the bank while they&apos;re still talking. The call
            ends only once the caller has said goodbye, and the agent waits for its last words to be
            heard before it hangs up.
          </p>
        </div>

        <div className="flex flex-col gap-20">
          <div>
            <h3 className="headline text-[1.6rem]">The model never says a number</h3>
            <p className="prose-width mt-3 text-[0.95rem] leading-relaxed text-ink-2">
              Gemma writes one line naming an action. Code runs it against the bank and a template
              speaks the bank&apos;s own figures, so a balance, date or reference can&apos;t be made up.
            </p>
            <div className="mt-6 flex flex-col gap-2">
              <FactStrip label="Gemma wrote" holder="agent">
                <code className="font-semibold text-blue-ink">{template.action}</code>
              </FactStrip>
              <FactStrip label="the bank returned">
                <code className="break-words text-ink-2">{JSON.stringify(template.bank).replace(/,"/g, ', "')}</code>
              </FactStrip>
              <FactStrip label="caller hears" holder="agent">
                {template.spoken}
              </FactStrip>
            </div>
          </div>

          <div>
            <h3 className="headline text-[1.6rem]">Values the caller never said don&apos;t reach the bank</h3>
            <p className="prose-width mt-3 text-[0.95rem] leading-relaxed text-ink-2">
              Two held-out turns, before and after this phase&apos;s checks. A card number, a customer
              number or a date has to appear in the caller&apos;s own words, or the agent asks for it.
            </p>
            <div className="mt-6 flex flex-col gap-8">
              {copied ? (
                <Pair said={copied.said} before={copied.before} why="the number from the prompt's example" now={<code className="font-semibold text-blue-ink">{copied.after}</code>} />
              ) : null}
              {invented ? (
                <Pair said={invented.said} before={invented.before} why="the tail of the customer number" now={<>&ldquo;{invented.after}&rdquo;</>} />
              ) : null}
            </div>
            <p className="mt-6">
              <Source file="src/tellerline/brain.py">Brain.interpret, where this happens</Source>
            </p>
          </div>
        </div>
      </div>
    </Section>
  );
}

// A controller's stamp: what this request gets, before and after the caller is verified.
function Stamp({ reach }: { reach: Reach }) {
  const tone = reach === "yes" ? "text-blue-ink" : reach === "no" ? "text-ink-3" : "text-ink";
  return <span className={`stamp ${tone}`}>{reach === "a colleague" ? "to a colleague" : reach}</span>;
}

function Pair({ said, before, why, now }: { said: string; before: string; why: string; now: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      <FactStrip label="caller said" holder="caller">
        &ldquo;{said}&rdquo;
      </FactStrip>
      <FactStrip label="before">
        <code className="text-ink-2">
          <s className="decoration-ink-2">{before}</s>
        </code>
        <span className="mt-0.5 block text-[0.8rem] text-ink-2">{why}</span>
      </FactStrip>
      <FactStrip label="now" holder="agent">
        {now}
      </FactStrip>
    </div>
  );
}
