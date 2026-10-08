import { data } from "@/lib/data";

import { CopyCommand } from "../CopyCommand";
import { ArrowIcon, GitHubIcon } from "../icons";
import { REPO } from "../links";
import { Section } from "./Section";

const SETUP = [
  { command: `git clone ${REPO}.git && cd Tellerline` },
  { command: "make setup", note: "a Python 3.12 environment with the agent installed" },
  { command: "make download", note: "Gemma 4, Parakeet, Kokoro: about 12.6 GB, once" },
  { command: "python -m tellerline.agent", note: "starts the bank, the models and the call page" },
  { command: "open http://localhost:7860", note: "allow the microphone, press Call, and wear headphones" },
];

const PHONE = [
  { command: "colima start --vm-type vz --port-forwarder grpc", note: "a Linux VM for the container; Docker Desktop works too" },
  {
    command: "docker compose -f telephony/asterisk/compose.yaml up -d --build",
    note: "Asterisk on 127.0.0.1:5060, user caller, password tellerline",
  },
];

export function RunSection({ number }: { number: number }) {
  return (
    <Section id="run" number={number} title="Run it on your own Mac" command={`git clone ${REPO}`}>
      <div className="grid gap-x-14 gap-y-20 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
        <div>
          <p className="prose-width text-[1.05rem] leading-relaxed">
            You need an Apple Silicon Mac with 16 GB of memory, <a href="https://docs.astral.sh/uv/">uv</a>,
            and about 12.6 GB of disk for the models. It was built and measured on a MacBook Air M5.
          </p>
          <ol className="mt-7 flex flex-col gap-1.5">
            {SETUP.map((item, index) => (
              <li key={item.command}>
                <CopyCommand step={index + 1} command={item.command} note={item.note} />
              </li>
            ))}
          </ol>

          <h3 className="headline mt-16 text-[1.6rem]">Or ring it from a phone</h3>
          <p className="prose-width mt-3 text-[0.95rem] leading-relaxed text-ink-2">
            Asterisk 23 takes the SIP call and hands it to the same agent. Run it in a container,
            then dial 2000 from a softphone on the Mac.
          </p>
          <ol className="mt-6 flex flex-col gap-1.5">
            {PHONE.map((item, index) => (
              <li key={item.command}>
                <CopyCommand step={index + 1} command={item.command} note={item.note} />
              </li>
            ))}
          </ol>

          <div className="mt-12 flex flex-wrap gap-3">
            <a className="key" data-primary="" href={REPO}>
              <GitHubIcon />
              View the code
            </a>
            <a className="key" href={`${REPO}/blob/main/docs/RUNNING.md`}>
              Read the guide
              <ArrowIcon />
            </a>
            <a className="key" href={`${REPO}/blob/main/docs/PHONE.md`}>
              Phone setup
              <ArrowIcon />
            </a>
          </div>
        </div>

        <div>
          <h3 className="headline text-[1.6rem]">Ring as one of these customers</h3>
          <p className="prose-width mt-3 text-[0.95rem] leading-relaxed text-ink-2">
            Tellerline Bank is fictional and every customer is made up. Say the customer number digit
            by digit, then the date of birth.
          </p>
          <ul className="mt-6 flex flex-col gap-1.5">
            {data.customers.map((customer) => (
              <li key={customer.number} className="holder-caller">
                <dl className="strip grid grid-cols-3 sm:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_minmax(0,0.9fr)_minmax(0,0.8fr)]">
                  <div className="box col-span-3 border-b border-rule sm:col-span-1 sm:border-b-0">
                    <dt className="sr-only">name</dt>
                    <dd className="m-0 font-semibold">{customer.name}</dd>
                  </div>
                  <div className="box border-l-0 sm:border-l">
                    <dt className="label">customer number</dt>
                    <dd className="print m-0 text-[0.92rem] font-semibold">{customer.number}</dd>
                  </div>
                  <div className="box">
                    <dt className="label">born</dt>
                    <dd className="print m-0 text-[0.84rem]">{formatBorn(customer.born)}</dd>
                  </div>
                  <div className="box">
                    <dt className="label">cards</dt>
                    <dd className="print m-0 text-[0.84rem]">{customer.cards.join(" ")}</dd>
                  </div>
                </dl>
              </li>
            ))}
          </ul>
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
