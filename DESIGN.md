---
name: Tellerline
description: A real bank call, replayed as an operator's green-phosphor terminal session.
colors:
  tube-ground: "#020805"
  deep-glass: "#07210f"
  scanline-dim: "#0b331e"
  afterimage: "#176e3a"
  faint-phosphor: "#1d8c4a"
  dim-phosphor: "#23a14b"
  p1-phosphor: "#33ff66"
  bloom: "#b6ffb6"
typography:
  display:
    fontFamily: "IBM 3270, ui-monospace, SF Mono, Menlo, monospace"
    fontSize: "clamp(2.25rem, 1.2rem + 3.3vw, 3.9rem)"
    fontWeight: 400
    lineHeight: 1.05
    letterSpacing: "0.01em"
  headline:
    fontFamily: "IBM 3270 Semi-Condensed, ui-monospace, SF Mono, Menlo, monospace"
    fontSize: "clamp(1.25rem, 1rem + 1vw, 1.75rem)"
    fontWeight: 400
    lineHeight: 1.25
  body:
    fontFamily: "IBM 3270 Semi-Condensed, ui-monospace, SF Mono, Menlo, monospace"
    fontSize: "1.125rem"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "IBM 3270 Semi-Condensed, ui-monospace, SF Mono, Menlo, monospace"
    fontSize: "1em"
    fontWeight: 400
    lineHeight: 1
    letterSpacing: "0.06em"
rounded:
  none: "0px"
spacing:
  gutter-phone: "1rem"
  gutter: "2rem"
  window: "clamp(4rem, 3rem + 5vw, 7.5rem)"
  status-bar: "2.25rem"
components:
  key:
    backgroundColor: "transparent"
    textColor: "{colors.p1-phosphor}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "0.55em 1.2ch"
  key-hover:
    backgroundColor: "{colors.deep-glass}"
    textColor: "{colors.p1-phosphor}"
  key-primary:
    backgroundColor: "{colors.p1-phosphor}"
    textColor: "{colors.tube-ground}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "0.55em 1.2ch"
  key-primary-hover:
    backgroundColor: "{colors.bloom}"
    textColor: "{colors.tube-ground}"
  status-bar:
    backgroundColor: "{colors.p1-phosphor}"
    textColor: "{colors.tube-ground}"
    height: "{spacing.status-bar}"
  prompt-input:
    backgroundColor: "transparent"
    textColor: "{colors.bloom}"
    typography: "{typography.body}"
    rounded: "{rounded.none}"
  prompt-input-focus:
    backgroundColor: "{colors.deep-glass}"
    textColor: "{colors.bloom}"
---

# Design System: Tellerline

## Overview

**Creative North Star: "The call prints itself."**

The page is an operator's terminal in a midnight machine room. A real recorded call replays as
a tmux-style session: every line the caller said, every route, ACTION line and millisecond
prints as it happened while both voices play. Everything else on the page continues the same
session: a heading is a shell comment, under it the real command that produced what follows,
then that command's output. The page is read and played, never decorated; it refuses the
voice-AI defaults of a glowing orb, gradient glass, an icon feature grid and invented metrics.

The world is one phosphor at several intensities on a black-green tube, behind curved CRT
glass with scanlines, a fine grain and an edge fade. One dot-matrix monospace face (IBM 3270)
carries everything, from the display headline to the per-stage timings; hierarchy comes from
size steps, case, indentation, a timestamp gutter and dashed rules. What is active is in
inverse video. States print themselves (`playing dispute`, `command not found`, `replied after
0.50 s`). Density is a working terminal's: generous between windows, tight inside them.

**Key Characteristics:**
- One colour, P1 phosphor, at six text and surface intensities; nothing else exists.
- One face, IBM 3270, in two widths: Regular for display, Semi-Condensed for everything else.
- Square everything: no radius, no cards, no drop shadows; frames are 1 px lines.
- Commands are bracketed keys; the active one is inverse.
- Every number shown is read from exported run data, and its source command is printed above it.

## Colors

A single phosphor hue, from the dark tube through decoration and three text intensities to the
bloom of whatever is live.

### Primary
- **P1 Phosphor** (#33ff66): body text (15:1 on the tube), the outline of keys, the inverse
  ground of the active key and the status bar. Text carries a faint glow of itself.
- **Bloom** (#b6ffb6): the display type, the live line of the replay, the cursor and caret, the
  primary key's hover and the focus ring. The brightest thing on screen is always the thing
  happening now.

### Neutral
- **Tube Ground** (#020805): the page, and the text colour of anything in inverse.
- **Deep Glass** (#07210f): panes, a key under the pointer, the focused prompt.
- **Scanline Dim** (#0b331e): rules between windows and table rows, pane-title lines.
- **Afterimage** (#176e3a): decoration only (3.2:1): dashed rules, the waveform's unplayed
  bars, link underlines at rest, scrollbars, tree glyphs.
- **Faint Phosphor** (#1d8c4a): the dimmest text (4.7:1): timestamps, per-stage timings, the
  call id, the prompt's history, licences.
- **Dim Phosphor** (#23a14b): secondary text (6.0:1): notes, labels, captions, prompts' `$`.

### Named Rules
**The One Phosphor Rule.** No colour outside this scale appears anywhere, not even for errors or
status. Meaning comes from intensity, inverse video and words.

**The Text Floor Rule.** Text is never drawn in Afterimage. The dimmest text is Faint Phosphor
(4.7:1); Afterimage is for lines, bars and glyphs that carry no reading.

## Typography

**Display Font:** IBM 3270 (Regular), with ui-monospace, SF Mono, Menlo
**Body Font:** IBM 3270 Semi-Condensed, with the same fallbacks
**Label/Mono Font:** the same face; this is a monospace world, so the face is the voice, not a
costume for code.

**Character:** a 1970s terminal's dot-matrix lettering, self-hosted under BSD-3-Clause:
mechanical, legible at small sizes, and honest about being a machine.

### Hierarchy
- **Display** (400, clamp(2.25rem, 1.2rem + 3.3vw, 3.9rem), 1.05, uppercase, Bloom with a
  strong glow): the hero headline and the footer's name only; balanced, at most 20ch.
- **Headline** (400, clamp(1.25rem, 1rem + 1vw, 1.75rem), 1.25, Bloom): each window's title,
  written as a shell comment (`# Measured by phoning it, not projected`).
- **Body** (400, 1.125rem desktop / 1.0625rem phone, 1.5): prose at 58-62ch, transcripts and
  tables; numbers that matter in Bloom inside it.
- **Label** (400, inherits size, 0.06em tracking, uppercase): keys (`[ VIEW THE CODE ]`) and the
  status bar's window list.
- **Small print** (0.85-0.95em, Dim or Faint): captions, sources, notes under commands.

### Named Rules
**The Tabular Numbers Rule.** Every timing, count and timestamp is set with tabular numerals, so
columns of milliseconds line up as a terminal's would.

## Layout

A long single page of windows. Each window is a full-width band with a 1 px Scanline Dim top
rule, padded `clamp(4rem, 3rem + 5vw, 7.5rem)` top and bottom, its content held to 80rem with a
1rem gutter on phones and 2rem from 768px. The first viewport is a split session: the call pane
(about 58%) on the left and the claim pane on the right; on phones the claim pane leads and the
call follows. Sections lay out as two columns on wide screens (from the lg or xl breakpoint, by section)
and stack below it.

A fixed inverse status bar (2.25rem) sits at the bottom of every screen, listing the windows
(`0:call 1:turn 2:numbers ...`) as the navigation; the active window is inverse within the
inverse bar. Anchors scroll with the bar's height kept clear. Nothing scrolls sideways at 390px:
long commands wrap only between words, and only words longer than a phone line may break.

## Elevation & Depth

Flat, with light instead of shadow. Depth is the CRT itself (scanlines, a radial edge fade with
an inset vignette, and a 7% grain, all fixed above the page and never catching the pointer) and
phosphor glow on text: a soft glow on body text, a stronger bloom on display type, the live line
and the primary key. There are no drop shadows and no lifted surfaces.

### Shadow Vocabulary
- **Glow** (`text-shadow: 0 0 1px rgb(51 255 102 / 0.55), 0 0 7px rgb(51 255 102 / 0.22)`):
  default text.
- **Strong glow** (`text-shadow: 0 0 2px rgb(182 255 182 / 0.85), 0 0 14px rgb(51 255 102 /
  0.5), 0 0 40px rgb(51 255 102 / 0.22)`): display type, Bloom text, the cursor.
- **Key halo** (`box-shadow: 0 0 1.25rem rgb(51 255 102 / 0.32)`, 1.75rem Bloom on hover): the
  primary key only.

### Named Rules
**The Light-Not-Lift Rule.** Emphasis is brightness. A surface never rises off the page; a line
glows harder.

## Shapes

Square corners everywhere (0px). Frames, rules and key outlines are 1 px; a terminal draws
rules as dashes (`0.45em` dash, `0.3em` gap) or as box-drawing characters. Keys are bracketed in
text (`[` and `]` generated around the label), never rounded. Charts are drawn in text: bars of
`▬`, waveforms of braille-like dot columns.

## Components

### Keys (buttons and button-like links)
- **Shape:** square (0px), 1 px P1 outline, padding 0.55em by 1.2ch, label uppercase with
  0.06em tracking, wrapped in generated brackets.
- **Primary:** inverse, P1 ground with Tube text and a soft phosphor halo; Bloom ground on hover.
  One per view: `[ VIEW THE CODE ]`, `[ RUN THE CALL ]`.
- **Secondary:** transparent with the P1 outline; Deep Glass on hover.
- **Hover / Focus / Active:** colour transitions 120-160ms ease-out; pressed keys move down 1px;
  keyboard focus is a 2px Bloom outline offset 3px; disabled keys sit at 45% and don't move.

### Prompt
- **Style:** `tellerline:~$` in Dim, then a borderless input in Bloom with a Bloom caret; the
  placeholder is Dim. The last few answers print above it and are read out politely.
- **Focus:** the line takes Deep Glass, and the site's 2px Bloom focus ring.
- **Behaviour:** real commands (help, calls, run [call], pause, goto, clone, github, clear);
  unknown ones answer `command not found: <word>. Try help.`

### Navigation (status bar)
- **Style:** fixed to the bottom, inverse P1 ground, `[tellerline]` in the display width, then
  the numbered windows; the current window is reversed back (Tube ground, P1 text). On phones
  only the numbers show, except for the current window's name. Digits 0-7 jump between windows.

### Call replay (signature)
The first viewport's left pane: a call's header (`replay call-90095d9d`), its numbered calls as
inverse-on-active tabs, a two-voice waveform drawn from the real audio (caller above the line,
Tellerline below, gaps bracketed), then the transcript printing in step with the audio. Each
line is a timestamp in Faint, the speaker in Dim, and the words revealed as they're spoken with
the Bloom cursor at the reading point. Under each caller line the turn's stages print as they
happened (`heard`, `exact`, `routed`, `decided`, `bank`, each with its milliseconds) and the wait
prints in Bloom (`replied after 0.50 s`), with the caller's own timing beside it in Dim.

### Tables
Plain rows divided by Scanline Dim rules, headings in Dim lower case, numbers tabular and right
where they compare. No zebra stripes and no boxes.

## Do's and Don'ts

### Do:
- **Do** print the command that produced a number above it, and link its result file.
- **Do** keep every colour on the phosphor scale above; express state with intensity, inverse
  video and words.
- **Do** keep text at Faint Phosphor (4.7:1) or brighter, and set timings in tabular numerals.
- **Do** wrap commands only between words, and keep all eight windows reachable from the status
  bar and the 0-7 keys.
- **Do** print motion-free under `prefers-reduced-motion`: the replay, cursor and smooth scroll
  all have still equivalents.

### Don't:
- **Don't** add a colour, a gradient, a rounded corner, a card or a drop shadow.
- **Don't** use an orb, glass panels, an icon feature grid or an invented metric: the page's
  proof is a recorded call and measured runs.
- **Don't** draw text in Afterimage (#176e3a); it is for lines and unplayed bars.
- **Don't** type a number into the page by hand; it is read from the exported results.
