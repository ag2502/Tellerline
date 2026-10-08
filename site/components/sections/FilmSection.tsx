import { data } from "@/lib/data";

import { Section } from "./Section";

export function FilmSection({ number }: { number: number }) {
  // The film is rendered from a recorded call by scripts/render_film.py; the section appears once
  // it has been made and exported.
  const film = data.film;
  if (!film) return null;
  return (
    <Section id="film" number={number} title="A whole call, start to finish" command="open tellerline.mp4">
      <figure className="mx-auto max-w-[72rem]">
        <div className="holder-turn">
          <div className="strip overflow-hidden p-1.5 sm:p-2">
            <video
              controls
              preload="none"
              playsInline
              poster={film.poster}
              className="block aspect-video w-full rounded-[2px] bg-well"
            >
              <source src={film.video} type="video/mp4" />
              <track kind="captions" src={film.captions} srcLang="en" label="English" default />
            </video>
          </div>
        </div>
        <figcaption className="prose-width mt-5 text-[0.95rem] leading-relaxed text-ink-2">
          Made frame by frame from one recorded call: the sound is the call itself, and each frame
          is this page&apos;s strip board at that moment. Captions are the transcript.
          <span className="print ml-2 text-[0.8rem] text-ink-3">{film.megabytes} MB</span>
        </figcaption>
      </figure>
    </Section>
  );
}
