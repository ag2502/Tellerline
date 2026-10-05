import { data } from "@/lib/data";

import { CopyCommand } from "../CopyCommand";
import { REPO } from "../links";
import { Section } from "./Section";

export function RunSection() {
  return (
    <Section id="run" title="Run it on your own Mac" command={`git clone ${REPO}`}>
      <div className="grid gap-16 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
        <div>
          <p className="mb-6 max-w-[60ch] leading-relaxed">
            You need an Apple Silicon Mac with 16 GB of memory, <a href="https://docs.astral.sh/uv/">uv</a>,
            and about 12.6 GB of disk for the models. It was built and measured on a MacBook Air
            M5.
          </p>
          <div className="border-y border-scan py-3">
            <CopyCommand command={`git clone ${REPO}.git && cd Tellerline`} />
            <CopyCommand command="make setup" note="a Python 3.12 environment with the agent installed" />
            <CopyCommand command="make download" note="Gemma 4, Parakeet, Kokoro: about 12.6 GB, once" />
            <CopyCommand command="python -m tellerline.agent" note="starts the bank, the models and the call page" />
            <CopyCommand command="open http://localhost:7860" note="allow the microphone, press Call, and wear headphones" />
          </div>
          <div className="mt-10 flex flex-wrap gap-4">
            <a className="key" data-primary="" href={REPO}>
              View the code
            </a>
            <a className="key" href={`${REPO}/blob/main/docs/RUNNING.md`}>
              Read the guide
            </a>
          </div>
        </div>

        <div>
          <h3 className="bloom mb-2">Ring as one of these customers</h3>
          <p className="dim mb-5 max-w-[56ch] text-[0.95em]">
            Tellerline Bank is fictional and every customer is made up. Say the customer number
            digit by digit, then the date of birth.
          </p>
          <table className="w-full border-collapse text-[0.92em] tabular">
            <thead>
              <tr className="dim text-left">
                <th scope="col" className="pb-2 font-normal">name</th>
                <th scope="col" className="pb-2 font-normal">customer number</th>
                <th scope="col" className="pb-2 font-normal">born</th>
                <th scope="col" className="pb-2 font-normal">cards</th>
              </tr>
            </thead>
            <tbody>
              {data.customers.map((customer) => (
                <tr key={customer.number} className="border-t border-scan">
                  <td className="py-1.5 pr-[1ch]">{customer.name}</td>
                  <td className="bloom">{customer.number}</td>
                  <td className="dim">{formatBorn(customer.born)}</td>
                  <td className="dim">{customer.cards.join(", ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </Section>
  );
}

function formatBorn(iso: string): string {
  return new Date(`${iso}T12:00:00Z`).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}
