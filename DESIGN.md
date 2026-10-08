---
name: Tellerline
description: A real bank call, replayed as flight progress strips on an air traffic control strip board.
colors:
  board: "#e7eaed"
  well: "#dde2e7"
  rail: "#c3cad2"
  strip: "#ffffff"
  scale-track: "#f3f5f7"
  rule: "#cdd3da"
  ink: "#16191d"
  ink-2: "#46505a"
  ink-3: "#5b646e"
  axis-grey: "#9aa3ad"
  amber: "#f2c14e"
  amber-trace: "#d9a21f"
  amber-ink: "#7a5a00"
  blue: "#2f6fd6"
  blue-ink: "#1f57b5"
  red: "#d93a2b"
  red-ink: "#c2301f"
typography:
  display:
    fontFamily: "Mona Sans, ui-sans-serif, system-ui, sans-serif"
    fontSize: "clamp(2.5rem, 1.2rem + 4.5vw, 4.5rem)"
    fontWeight: 800
    lineHeight: 0.95
    letterSpacing: "-0.01em"
    fontVariation: "'wdth' 75"
  headline:
    fontFamily: "Mona Sans, ui-sans-serif, system-ui, sans-serif"
    fontSize: "clamp(2rem, 1.25rem + 2.6vw, 3.5rem)"
    fontWeight: 760
    lineHeight: 1.02
    letterSpacing: "-0.012em"
    fontVariation: "'wdth' 78"
  title:
    fontFamily: "Mona Sans, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.6rem"
    fontWeight: 760
    lineHeight: 1.02
    letterSpacing: "-0.012em"
    fontVariation: "'wdth' 78"
  body:
    fontFamily: "Mona Sans, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 400
    lineHeight: 1.55
    fontVariation: "'wdth' 100"
  label:
    fontFamily: "Mona Sans, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.6875rem"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "0.1em"
    fontVariation: "'wdth' 125"
  print:
    fontFamily: "Martian Mono, ui-monospace, SF Mono, Menlo, monospace"
    fontSize: "1.05rem"
    fontWeight: 400
    letterSpacing: "-0.01em"
    fontFeature: "'tnum' 1"
    fontVariation: "'wdth' 87.5"
rounded:
  tick: "1px"
  strip: "3px"
  plate: "4px"
  holder: "5px"
  key: "6px"
  well: "10px"
spacing:
  gutter-phone: "16px"
  gutter: "32px"
  strip-gap: "10px"
  box: "6px 11px 7px"
  holder-edge: "3px"
  holder-end: "10px"
  bay: "clamp(4.5rem, 3rem + 6vw, 8.5rem)"
  page-max: "90rem"
components:
  key:
    backgroundColor: "{colors.strip}"
    textColor: "{colors.ink}"
    rounded: "{rounded.key}"
    padding: "0.6rem 1.15rem"
    height: "2.75rem"
  key-hover:
    backgroundColor: "#f6f7f8"
    textColor: "{colors.ink}"
  key-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.strip}"
    rounded: "{rounded.key}"
    padding: "0.6rem 1.15rem"
    height: "2.75rem"
  key-primary-hover:
    backgroundColor: "#262b31"
  strip:
    backgroundColor: "{colors.strip}"
    textColor: "{colors.ink}"
    rounded: "{rounded.strip}"
  holder-caller:
    backgroundColor: "{colors.amber}"
    rounded: "{rounded.holder}"
    padding: "3px 3px 3px 10px"
  holder-agent:
    backgroundColor: "{colors.blue}"
    rounded: "{rounded.holder}"
    padding: "3px 3px 3px 10px"
  holder-plain:
    backgroundColor: "{colors.rail}"
    rounded: "{rounded.holder}"
    padding: "3px 3px 3px 10px"
  strip-box-label:
    textColor: "{colors.ink-3}"
    typography: "{typography.label}"
    padding: "{spacing.box}"
  well:
    backgroundColor: "{colors.well}"
    rounded: "{rounded.well}"
    padding: "12px"
  plate:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.strip}"
    rounded: "{rounded.plate}"
    size: "2.25rem"
  bay-tab:
    textColor: "{colors.ink-2}"
    rounded: "{rounded.holder}"
    padding: "6px 8px"
  bay-tab-current:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.strip}"
  command-line:
    backgroundColor: "{colors.strip}"
    textColor: "{colors.ink}"
    typography: "{typography.print}"
    rounded: "{rounded.key}"
    height: "2.5rem"
---

# Design System: Tellerline

## Overview

**Creative North Star: "The Strip Board"**

Tellerline's world is an air traffic control strip board. The page is a flat, brushed-aluminium board; every fact on it is a white paper strip seated in a coloured plastic holder, ruled into boxes with tiny printed field labels above their values. A real call replays as strips feeding into a recessed well, one per turn, printing box by box as the voices play. Colour is coding, not decoration: amber holders belong to the caller, blue holders to Tellerline, grey holders to plain fact. One red pen marks the turn that is live, then settles to ink.

The density is that of a working board: compact strips, small labels, many measured values, but laid out in generous bays with wide gutters so the board never reads as crowded. Type does two jobs. Mona Sans pulled condensed and heavy is the printed callsign; the same family at normal width carries prose; Martian Mono is what the strip printer prints, every measured time, code and command. Motion is mechanical: strips snap one step and settle, text prints in steps, pen strokes draw on once. Nothing glides.

The world refuses the voice-AI orb, gradient glass, icon grids and the dark terminal it replaced. Depth is physical and shallow: strips lift a millimetre off the board, wells sink into it, keys have a lip.

**Key Characteristics:**
- Flat aluminium board (no grain, no gradient) with recessed wells and rails as the only structure.
- Every fact sits in a white strip inside a coloured holder; the holder's thick end carries the colour code.
- Ruled boxes: a tiny wide uppercase label above a value, separated by hairline rules.
- One red pen, only on the live turn, settling to ink once the turn passes.
- Condensed heavy Mona Sans for print, normal-width Mona Sans for prose, Martian Mono for every measured value.
- Every timing sits on one ruled 0 to 1.5 s scale.
- Strips snap with a short overshoot; nothing glides.

## Colors

A cool aluminium neutral field carrying three coding colours (amber, blue, red), each with a darker ink twin for text.

### Primary
- **Controller Blue** (#2f6fd6): Tellerline's holder colour, the agent half of the waveform, scale fills and the hatched tail of a spread, and the focus ring. Blue means "the agent did this".
- **Controller Blue Ink** (#1f57b5): Blue-coded text on white: "Tellerline said" labels, printed ACTION lines, the active histogram column.

### Secondary
- **Strip Amber** (#f2c14e): The caller's holder colour, text selection, and the selected call designator's number tile. Amber means "the caller".
- **Trace Amber** (#d9a21f): The caller half of the waveform and the caller swatch in legends, where Strip Amber is too pale to read as a thin mark on white.
- **Amber Ink** (#7a5a00): Amber-coded text: "caller said" labels and "Caller:" in the transcript.

### Tertiary
- **Red Pen** (#d93a2b): The pen stroke circling the live turn's wait, and the input caret.
- **Red Pen Figure** (#c2301f): The live turn's written wait figure.

### Neutral
- **Brushed Aluminium** (#e7eaed): The board, the page ground, the header and the browser theme colour. Flat.
- **Bay Well** (#dde2e7): Recessed wells where strips sit, the footer, hover ground for bay tabs, unselected number tiles.
- **Rail** (#c3cad2): Rails and rules on the board (bay borders, header border, footer list rules), plain holders, link underlines at rest, scale ticks, the idle waveform.
- **Strip Paper** (#ffffff): Every strip, secondary keys, the command line.
- **Scale Track** (#f3f5f7): The ruled track under every timing and memory scale.
- **Strip Rule** (#cdd3da): Hairlines between boxes on a strip.
- **Print Ink** (#16191d): Text, primary keys, plates, the current bay tab, settled pen marks, the waveform playhead.
- **Ink 2** (#46505a): Secondary prose and quiet controls (6.8:1 on the board).
- **Ink 3** (#5b646e): Labels, timings and placeholders; the lowest-contrast text, still 4.6:1 in a well.
- **Axis Grey** (#9aa3ad): The waveform's dashed axis and the second print line in the strip mark and favicon. Never text.

### Named Rules
**The Holder Code Rule.** Amber holder = the caller, blue holder = Tellerline, grey holder = plain fact. A strip that carries both sides sits in a split holder, amber left and blue right. Never use amber or blue as decoration where it does not mean a side.

**The One Hot Ink Rule.** Red appears only on the turn that is live: the pen circle and its figure. When the turn is no longer live, the pen settles to Print Ink. Done/not-done marks are drawn in ink, never red.

**The Ink Twin Rule.** Coding colours never set body text at their holder value; text uses the ink twin (Amber Ink, Controller Blue Ink, Red Pen Figure).

## Typography

**Display Font:** Mona Sans (variable width axis, with ui-sans-serif, system-ui)
**Body Font:** Mona Sans at normal width
**Label/Mono Font:** Martian Mono (variable width, at 87.5) with ui-monospace, SF Mono, Menlo

**Character:** One family pulled two ways: condensed and heavy it is the strip's printed callsign, wide and spaced it is the ruled field label, and at normal width it is calm prose. Martian Mono is the printer: tabular, slightly narrowed, for anything measured.

### Hierarchy
- **Display / Callsign** (800, width 75, clamp(2.5rem, 1.2rem + 4.5vw, 4.5rem), narrowing to clamp(2.2rem, 4vw - 0.4rem, 3.2rem) beside the board on desktop, line-height 0.95, uppercase): the hero claim, the wordmark (1.35rem in the header, 2rem in the footer) and the call's title on its header strip.
- **Headline** (760, width 78, clamp(2rem, 1.25rem + 2.6vw, 3.5rem), line-height 1.02, sentence case): a bay's title, beside its plate.
- **Title** (760, width 78, 1.6rem): sub-heads inside a bay.
- **Body** (400, width 100, 1.0625rem on phones, 1.125rem from 768px, line-height 1.55): prose, capped near 62ch (hero lede 40ch, footer 46ch). Strip text runs smaller (0.84 to 0.98rem, leading-snug).
- **Label** (600, width 125, 0.6875rem, letter-spacing 0.1em, uppercase, Ink 3): field labels above values on strips, the "from" line under bay titles, table column heads.
- **Print** (Martian Mono, width 87.5, tabular figures, -0.01em): times, waits, commands, call ids, ACTION lines, plate numbers, the command line. Inline `code` uses the same face at 0.9em.

### Named Rules
**The Printer Rule.** Every measured value, time, code or command is set in Martian Mono with tabular figures. Prose numbers that are not measurements stay in Mona Sans.

**The Width Axis Rule.** Hierarchy is made with Mona Sans's width axis as much as weight: condensed (75 to 78) for print and titles, 100 for prose, 125 for labels. Do not substitute a second display family.

## Layout

The page is one board divided into bays. Each bay is full width with a rail line above it, block padding clamp(4.5rem, 3rem + 6vw, 8.5rem), inline gutter 1rem on phones and 2rem from 768px, and content capped at 90rem. A bay opens with its plate (a numbered key, also its keyboard shortcut) beside the headline and a "from <command>" provenance line, then 3 to 3.5rem of space before its strips.

The first viewport splits roughly one third claim to two thirds call board on desktop (0.82fr / 1.55fr, gap 3.5rem), and stacks claim then board on phones. The sticky board header is 3.5rem tall (3.75rem from 768px) with the wordmark, a horizontally scrolling row of bay tabs and the GitHub key.

Strips stack with 0.5 to 0.625rem between them. Inside a strip, a label column (4.75 to 8.5rem) sits beside the value column; below 640px a fact strip moves its label above its value. Breakpoints are Tailwind's: 640px, 768px, 1024px.

**The One Scale Rule.** Every reply timing on the page sits on the same ruled 0 to 1.5 s scale (six ticks), so a wait in a strip, a turn's anatomy and a run's spread can be compared by eye.

## Elevation & Depth

Depth is physical and shallow: strips are paper lifted barely off the board, wells are pressed into it, keys have a lip. There is no ambient glow and no floating card.

### Shadow Vocabulary
- **Lift** (`box-shadow: 0 1px 0 rgb(22 25 29 / 0.05), 0 2px 6px -1px rgb(22 25 29 / 0.12)`): every strip at rest, the command line, unselected call designators.
- **Lift High** (`box-shadow: 0 2px 0 rgb(22 25 29 / 0.05), 0 14px 28px -10px rgb(22 25 29 / 0.32)`): a strip pulled out of its holder (an open trace, an opened log entry), with a 2px rise.
- **Well** (`box-shadow: inset 0 1px 2px rgb(22 25 29 / 0.12), inset 0 0 0 1px rgb(22 25 29 / 0.05)`): recessed bays where strips sit.
- **Holder Edge** (`inset 0 0 0 1px` in a darkened tint of the holder colour): the moulded edge of a plastic holder.
- **Key Lip** (`0 1px 0` ink at rest, `0 2px 0` on hover, `0` when pressed; the primary key adds `0 8px 18px -8px rgb(22 25 29 / 0.6)`): the physical edge of a console key.

### Named Rules
**The Pull Rule.** A strip rises only when it is pulled (its trace opened); nothing lifts on mere hover.

**The Lip Is Vertical Rule.** A key's lip is 1 to 2px straight down. Never a diagonal offset, never a block shadow.

## Shapes

Small, machined corners everywhere: scale ticks and bars 1 to 2px, strips 3px, plates 4px, holders and bay tabs 5px, keys and the command line 6px, wells 10px. A holder shows 3px round its strip and 10px at its coloured end, so the colour reads as a tab on the left; a turn's split holder shows 10px at both ends. Inside strips, boxes are divided by 1px Strip Rule hairlines, never by gaps or fills.

Pen marks (tick, cross, hand-off hook, circle) are hand-drawn SVG strokes, loose like a pen, round caps and joins, 2.1 to 2.25 stroke on a 20-unit grid. UI icons are drawn at 1.75 stroke on the same 20-unit grid. The Tellerline mark is one strip in a split amber/blue holder.

## Components

### Keys (buttons)
Console keys: solid, square-shouldered, with a lip.
- **Shape:** gently squared (6px), minimum 2.75rem tall, 1px Print Ink border, 0.95rem semibold Mona Sans, icon at 1.05em.
- **Primary:** Print Ink fill, Strip Paper text (View the code, Play the call, GitHub).
- **Secondary:** Strip Paper fill, ink text and border.
- **Hover / Active:** rises 1px with a 2px lip (secondary goes to #f6f7f8, primary to #262b31); pressed sinks 1px with no lip. 120ms on Settle easing. Disabled at 50% opacity.
- **Focus:** the global 2px Controller Blue outline, offset 3px.

### Strips and holders (cards)
The page's one container.
- **Corner Style:** strip 3px inside a 5px holder.
- **Background:** Strip Paper in an amber, blue, grey or split amber/blue holder (see the Holder Code Rule).
- **Shadow Strategy:** Lift at rest, Lift High when pulled.
- **Internal structure:** ruled boxes, label above value, padding 0.4rem 0.7rem 0.45rem; label column left of value on wide screens, above it on phones.

### Turn strip (signature)
One caller turn: the time (click to play from there), what the caller said, four stage boxes (heard, routed, decided, bank or held back) with their milliseconds, what Tellerline said, and the wait box with a mini scale. It feeds in from the top of the well (420ms Snap overshoot) while the strips below snap down one step; stage values print in by six steps (260ms). When Tellerline answers, the red pen draws a loop round the wait figure (480ms) and the figure turns Red Pen Figure; when the turn stops being live, both settle to ink (380ms). "Pull the trace" lifts the strip and opens a ruled list of everything the agent recorded.

### Plates
Bay designators: Print Ink squares (2.25rem, 4px) with a Martian Mono semibold number in Strip Paper. The number is the bay's keyboard shortcut.

### Inputs / Fields
- **Style:** the command line is a strip (Strip Paper, 6px, Lift) with a Martian Mono › prompt and input at 0.86rem, labelled by a Label above.
- **Focus:** the Lift is replaced by a 2px Controller Blue ring.

### Navigation
The board header: the strip mark and callsign wordmark, then bay tabs in 0.8rem semibold uppercase with 0.07em tracking, each preceded by its Martian Mono number. Current tab: Print Ink fill, Strip Paper text, Amber number. Others: Ink 2, Bay Well on hover. On phones the row scrolls sideways with a fade mask and the numbers hide. Call designators above the board follow the same pattern, with a numbered tile (amber when selected) and a Lift or Key Lip.

### Scales
The ruled 0 to 1.5 s track (Scale Track with Rail ticks every sixth): solid Controller Blue to the median, blue hatching (135deg, 1.5px lines every 4.5px) on to nine in ten, an ink tick for the caller's own timing.

## Do's and Don'ts

### Do:
- **Do** put every fact in a white strip inside a holder, ruled into label-over-value boxes.
- **Do** code holders by side: amber for the caller, blue for Tellerline, grey for plain fact.
- **Do** keep the board flat Brushed Aluminium (#e7eaed); make depth only with Lift, Well and Key Lip.
- **Do** set every measured value in Martian Mono with tabular figures.
- **Do** place every timing on the one 0 to 1.5 s scale.
- **Do** draw marks (tick, cross, hand-off, circle) as loose SVG pen strokes in ink.
- **Do** use Snap (cubic-bezier(0.3, 1.45, 0.55, 1)) only for a strip feeding into or stepping down a well; use Settle (cubic-bezier(0.2, 0.8, 0.2, 1)) for every other transition.
- **Do** print instantly under reduced motion: no feed, no print-in, no pen draw.

### Don't:
- **Don't** use red anywhere but the live turn's pen and figure.
- **Don't** add grain, noise, gradients or glass to the board.
- **Don't** let anything glide: no long eases, no parallax, no fades that drift into place.
- **Don't** set body text in a holder colour; use its ink twin.
- **Don't** use rubber stamps or filled badges for status; mark it with the pen.
- **Don't** give a key a diagonal or block offset shadow; its lip is 1 to 2px straight down.
- **Don't** introduce a second display family or a system display face; hierarchy comes from Mona Sans's width axis.
