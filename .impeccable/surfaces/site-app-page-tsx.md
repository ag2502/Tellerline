---
version: 1
slug: "site-app-page-tsx"
primary_target: "site/app/page.tsx"
related_targets: ["site"]
---

# Surface brief: Tellerline website (site/)

Scope: the public launch site for Tellerline, one long page plus generated OG images, deployed
on Vercel at tellerline.vercel.app. Visitor mode: Persuade. Redesign (6 October 2026): the
green-phosphor terminal world is replaced; product truth, content and functions stay.

Audience and job: engineers and hiring managers judging the project in one or two minutes; they
must hear a real call first, believe the measured numbers, and open the GitHub repository
(primary action). Watching the film is the secondary action.

Proof on hand: real recorded calls (both voices, transcripts, per-stage timings) exported from
the agent's recorder; benchmark results under results/; the decision log; live repository data
from GitHub. Nothing else may be claimed.

Must survive, in the new form: the call replay with real audio and per-stage timings, the typed
command prompt, the decision log, the film, the run guide and the credits.

Constraints: every number on the page is read from exported run data at build time, never typed
in by hand; caller voices in recordings are synthetic and must be labelled so; model credits
and licences stay visible; works at 390 px; keyboard-first; reduced motion prints instantly.
The owner rejected: dark and techy, the generic AI startup look, static and plain, busy and
dense.

## Direction contract

THESIS: Every turn is a flight strip. A real call replays on an air-traffic strip board: each
caller turn feeds a printed strip that fills box by box (heard, routed, decided, bank) as both
voices play, and moves down the bay. It refuses the voice-AI orb, gradient glass, icon grids
and the terminal it replaces.

OWN-WORLD: Brushed aluminium board #E7EAED, white strips #FFFFFF in coloured holders: amber
#F2C14E for the caller's side, blue #2F6FD6 for Tellerline's; print ink #16191D; red pen #D93A2B
only on the live turn. Mona Sans (width axis: condensed for strip print, normal for prose) and
Martian Mono for measured values. Ruled boxes with tiny labels, bay designators, pen circles and
ticks drawn as SVG strokes. Raised lines: one clock (the call's timecode drives the board;
pause freezes every strip), one hot ink (red only on the live turn), nothing glides (strips snap
one step, overshoot, settle), one scale (every timing on the same ruled 0-1.5 s scale), one pull
(pulling a strip opens its trace).

STORY: The visitor presses Play and hears Aoife's call while strips print and fill in sync, the
red pen circling each reply time. Scrolling moves through bays on the same board: one strip
pulled out (a turn's anatomy on the scale), the measured numbers (the gate as a histogram on
that scale, capacity as parallel bays, the phone line), what an unverified caller can reach,
memory, the decision log as filed strips, the film, and the run guide, ending at GitHub.

FIRST VIEWPORT: A board header with the wordmark, bay tabs and the GitHub key. Left third: the
headline over two lines, one sentence, three measured proof strips, GitHub key and film key.
Right two-thirds: the call board: four call designators, a header strip with the two-voice
waveform and clock, the greeting strip already printed, and a large Play key. Phones: claim,
then board.

FORM: Air traffic control flight progress strips, candidate 3 of my ordered seven; seed key
21b97a7f.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Memorable moment

Pressing Play: a strip snaps down out of the printer, "Hi, I think my bank card has been
stolen." prints in its caller box, ROUTE and DECIDE fill in, `ACTION freeze card=4217
reason=stolen` prints, and the red pen circles "0.50 s" as Tellerline answers.

## Unresolved

- The command prompt's form in this world (a scratchpad entry line under the board).
- OG image and favicon redrawn in the new world.
