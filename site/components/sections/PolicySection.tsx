import { data } from "@/lib/data";

import { Section, Source } from "./Section";

// What a caller can reach is decided by code and by the bank's API, not by the prompt.
const MATRIX: { what: string; unverified: string; verified: string }[] = [
  { what: "check who they are", unverified: "yes", verified: "done" },
  { what: "balances and recent payments", unverified: "no", verified: "yes" },
  { what: "freeze, unfreeze or replace a card", unverified: "no", verified: "yes" },
  { what: "ask whether a card is frozen", unverified: "no", verified: "yes" },
  { what: "open a dispute", unverified: "no", verified: "yes" },
  { what: "anyone else's account", unverified: "no", verified: "no" },
  { what: "move money, loans, hardship", unverified: "a colleague", verified: "a colleague" },
  { what: "a full card number or PIN", unverified: "refused", verified: "refused" },
];

export function PolicySection() {
  const copied = data.examples.find((item) => item.case === "h-verify-double-oh");
  const invented = data.examples.find((item) => item.case === "h-unfreeze-no-digits");
  const template = data.template;
  return (
    <Section id="policy" title="The model decides; code owns the facts" command="less src/tellerline/brain.py">
      <div className="grid gap-16 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <div>
          <h3 className="bloom mb-2">What a caller can reach</h3>
          <p className="dim mb-5 max-w-[56ch] text-[0.95em]">
            Before verification only the identity check can run, whatever the model writes; the
            bank&apos;s API is scoped to the verified customer, so another customer&apos;s data is
            out of reach by construction.
          </p>
          <table className="w-full border-collapse text-[0.92em]">
            <thead>
              <tr className="dim text-left">
                <th scope="col" className="pb-2 font-normal">request</th>
                <th scope="col" className="pb-2 font-normal">not verified</th>
                <th scope="col" className="pb-2 font-normal">verified</th>
              </tr>
            </thead>
            <tbody>
              {MATRIX.map((row) => (
                <tr key={row.what} className="border-t border-scan">
                  <td className="py-1.5 pr-[1ch]">{row.what}</td>
                  <td className={row.unverified === "yes" ? "bloom" : "dim"}>{row.unverified}</td>
                  <td className={row.verified === "yes" ? "bloom" : "dim"}>{row.verified}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="dim mt-5 max-w-[56ch] text-[0.95em]">
            Every call opens by saying it is an AI. The call ends only once the caller has said
            goodbye, and the agent waits for its last words to be heard before it hangs up.
          </p>
        </div>

        <div className="space-y-12">
          <div>
            <h3 className="bloom mb-2">The model never says a number</h3>
            <p className="dim mb-5 max-w-[58ch] text-[0.95em]">
              Gemma writes one line naming an action. Code runs it against the bank and a
              template speaks the bank&apos;s own figures, so a balance, date or reference can&apos;t
              be made up.
            </p>
            <dl className="space-y-3">
              <Pair label="Gemma" value={template.action} tone="bloom" />
              <Pair label="bank" value={JSON.stringify(template.bank).replace(/,"/g, ', "')} />
              <Pair label="caller hears" value={template.spoken} />
            </dl>
          </div>

          <div>
            <h3 className="bloom mb-2">Values the caller never said don&apos;t reach the bank</h3>
            <p className="dim mb-5 max-w-[58ch] text-[0.95em]">
              Two held-out turns, before and after this phase&apos;s checks. A card number, a
              customer number or a date has to appear in the caller&apos;s own words, or the agent
              asks for it.
            </p>
            <dl className="space-y-6">
              {copied ? (
                <div className="space-y-2">
                  <Pair label="caller" value={`"${copied.said}"`} />
                  <Pair label="before" value={`${copied.before}  (the number from the prompt's example)`} tone="dim" />
                  <Pair label="now" value={copied.after} tone="bloom" />
                </div>
              ) : null}
              {invented ? (
                <div className="space-y-2">
                  <Pair label="caller" value={`"${invented.said}"`} />
                  <Pair label="before" value={`${invented.before}  (the tail of the customer number)`} tone="dim" />
                  <Pair label="now" value={`"${invented.after}"`} tone="bloom" />
                </div>
              ) : null}
            </dl>
            <p className="mt-5">
              <Source file="src/tellerline/brain.py">Brain.interpret, where this happens</Source>
            </p>
          </div>
        </div>
      </div>
    </Section>
  );
}

function Pair({ label, value, tone = "text-p1" }: { label: string; value: string; tone?: string }) {
  return (
    <div className="grid grid-cols-[13ch_1fr] gap-x-[1ch]">
      <dt className="dim">{label}</dt>
      <dd className={`${tone} m-0 min-w-0 break-words`}>{value}</dd>
    </div>
  );
}
