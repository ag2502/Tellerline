import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { FilmFrame } from "@/components/FilmFrame";
import { data, loadCall } from "@/lib/data";

// The film's frames, for scripts/render_film.py. Not a page for visitors.
export const metadata: Metadata = { robots: { index: false, follow: false } };
export const dynamicParams = false;

export function generateStaticParams() {
  return data.calls.map((call) => ({ slug: call.slug }));
}

export default async function RenderFilm({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const call = await loadCall(slug).catch(() => null);
  if (!call) notFound();
  const gate = data.live.gate;
  const numbers = gate?.latency_s
    ? { p50: gate.latency_s.p50, p90: gate.latency_s.p90, turns: gate.measured }
    : null;
  return <FilmFrame call={call} numbers={numbers} />;
}
