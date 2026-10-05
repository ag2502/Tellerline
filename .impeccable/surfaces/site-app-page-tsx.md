---
version: 1
slug: "site-app-page-tsx"
primary_target: "site/app/page.tsx"
related_targets: ["site"]
---

# Surface brief: Tellerline website (site/)

Scope: the public launch site for Tellerline, one long page plus generated OG images, deployed
on Vercel. Visitor mode: Persuade.

Audience and job: engineers and hiring managers judging the project in one or two minutes; they
must hear a real call, believe the measured numbers, and open the GitHub repository (primary
action). Watching the film is the secondary action.

Proof on hand: real recorded calls (both voices, transcripts, per-stage timings) exported from
the agent's recorder; benchmark results under results/; the decision log; live repository data
from GitHub. Nothing else may be claimed.

Constraints: every number on the page is read from exported run data at build time, never typed
in by hand; caller voices in recordings are synthetic and must be labelled so; model credits
and licences stay visible; works at 390 px; keyboard-first; reduced motion prints instantly.

## Direction contract

THESIS: The call prints itself. A real Tellerline call replays as an operator's terminal
session: every line the caller said, every route, ACTION line and millisecond prints as it
happened while both voices play. It refuses the voice-AI default of a glowing orb, gradient
glass, an icon feature grid and invented metrics.

OWN-WORLD: P1 phosphor #33ff66 on tube ground #020805 inside curved CRT glass with scanlines,
fine grain and edge fade; afterimage #176e3a for history, bloom #b6ffb6 for the live line and
cursor, deep glass #07210f for panes, scanline dim #0b331e for rules. One dot-matrix monospace
face does everything; hierarchy is size steps of that face, case, indentation, a line-number
gutter and dashed full-width rules. Commands are bracketed; active is inverse video; states print
themselves. No other colour exists. Voices are braille-dot waveforms drawn from the real audio.

STORY: The visitor lands inside a tmux-style session where a real call waits. They press RUN and
hear Tellerline answer while each turn prints what was heard, where it was routed, the ACTION
line, the bank's answer and every stage's milliseconds. Scrolling continues the same session
(how a turn works, the gate's numbers, safety by construction, what fits in 16 GB, the decision
log, the film), and it ends at git clone and the GitHub link.

FIRST VIEWPORT: Full-viewport CRT. Left pane, about 58%: the call session, header printed, the
greeting already on screen and a waveform beneath it, waiting on RUN. Right pane: a dot-matrix
display headline over three lines, one plain sentence, real numbers as prompt lines, then the
actions: inverse [ RUN THE CALL ] and outlined [ GITHUB ]. Bottom: an inverse tmux status bar
whose window list is the navigation. On phones the right pane leads and the call pane follows.

FORM: Green-phosphor terminal in a midnight machine room (catalog challenger
signals-instruments-phosphor-terminal-midnight, chosen over the assigned The Scope in re-roll
round 1). Seed key b67b08be. Signature interaction: RUN replays a real recorded call with sound,
printing each turn and its stage timings in sync; a typed prompt accepts real commands.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Memorable moment

Pressing RUN: the caller speaks, the gutter counts, `ACTION freeze card=4217 reason=stolen`
prints in bloom, and Tellerline answers in a British voice about a second later, with the reply
gap printed underneath in milliseconds.

## Unresolved

- Final latency and accuracy figures arrive from this phase's benchmark runs.
- Whether the phone-line (Asterisk) path gets its own section depends on the telephony build.
