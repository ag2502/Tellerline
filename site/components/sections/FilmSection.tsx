import { data } from "@/lib/data";

import { Section } from "./Section";

export function FilmSection() {
  // The film is rendered from a recorded call by scripts/render_film.py; the section appears
  // once it has been made and exported.
  const film = data.film;
  if (!film) return null;
  return (
    <Section id="film" title="A whole call, start to finish" command="open tellerline.mp4">
      <figure className="mx-auto max-w-[68rem]">
        <div className="border border-scan bg-glass p-2 sm:p-3">
          <video
            controls
            preload="none"
            playsInline
            poster={film.poster}
            className="block aspect-video w-full bg-tube"
          >
            <source src={film.video} type="video/mp4" />
            <track kind="captions" src={film.captions} srcLang="en" label="English" default />
          </video>
        </div>
        <figcaption className="dim mt-4 max-w-[64ch] text-[0.95em]">
          Made frame by frame from one recorded call: the sound is the call itself, and each frame
          is this page&apos;s replay at that moment. Captions are the transcript.
        </figcaption>
      </figure>
    </Section>
  );
}
