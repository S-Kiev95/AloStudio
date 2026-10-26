---
name: AloStudio
description: One workspace for social publishing, the omnichannel inbox and the CRM, rendered as a dark room of cobalt glass where only the sign, the place you are and the thing you act on are lit.
colors:
  night-ground: "#060912"
  panel: "#0b1020"
  panel-raised: "#0f1528"
  settings-surface: "#131a30"
  backdrop: "#01030a"
  field: "#070b16"
  unlit-glass: "#1c2644"
  glass-highlight: "rgba(127, 160, 255, 0.10)"
  ambient-spill: "rgba(61, 107, 255, 0.10)"
  separator: "#2a3660"
  hover-glass: "#111834"
  focused-glass: "#101a3d"
  button-simple: "rgba(24, 33, 61, 0.55)"
  text-primary: "#e7ecff"
  text-secondary: "#8d97b8"
  menu-dots: "#6c7699"
  cobalt-core: "#3d6bff"
  cobalt-core-hover: "#5a82ff"
  lit-text: "#dbe4ff"
  table-text-focused: "#7fa0ff"
  electrode: "#ff6a3d"
  daylight-ground: "#eef1f8"
  daylight-panel: "#ffffff"
  daylight-field: "#f7f9fe"
  daylight-glass: "#d6dcef"
  daylight-border: "#e3e7f3"
  daylight-focused-glass: "#e6ecff"
  daylight-text: "#0c1124"
  daylight-text-secondary: "#5f6987"
  daylight-cobalt-core: "#2f5bf0"
  daylight-cobalt-core-hover: "#1f47d6"
  daylight-lit-text: "#1a3bb8"
  daylight-electrode: "#e5512a"
typography:
  wordmark:
    fontFamily: "Neonderthaw, cursive"
    fontSize: "36px"
    fontWeight: 400
    lineHeight: 1
  display:
    fontFamily: "Tilt Neon, sans-serif"
    fontSize: "34px"
    fontWeight: 400
    lineHeight: 1.2
    letterSpacing: "0.01em"
  tab:
    fontFamily: "Tilt Neon, sans-serif"
    fontSize: "17px"
    fontWeight: 400
  nav:
    fontFamily: "Tilt Neon, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1
  title:
    fontFamily: "Geologica, sans-serif"
    fontSize: "16px"
    fontWeight: 500
    lineHeight: 1.4
  body:
    fontFamily: "Geologica, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.45
  label:
    fontFamily: "Geologica, sans-serif"
    fontSize: "12px"
    fontWeight: 500
    lineHeight: 1.3
  table-header:
    fontFamily: "Geologica, sans-serif"
    fontSize: "11px"
    fontWeight: 500
    letterSpacing: "0.08em"
  numeric:
    fontFamily: "Geologica, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    fontFeature: "tnum"
rounded:
  sm: "4px"
  md: "8px"
  control: "10px"
  panel: "16px"
  pill: "100px"
spacing:
  shell: "12px"
  shell-mobile: "8px"
  sidebar: "236px"
  button-x: "24px"
  nav-item-x: "14px"
  nav-item-gap: "12px"
components:
  button-primary:
    backgroundColor: "{colors.cobalt-core}"
    textColor: "#ffffff"
    rounded: "{rounded.control}"
    padding: "0 24px"
    height: "40px"
  button-primary-hover:
    backgroundColor: "{colors.cobalt-core-hover}"
  button-secondary:
    backgroundColor: "{colors.panel-raised}"
    textColor: "{colors.text-primary}"
    padding: "0 24px"
    height: "40px"
  button-simple:
    backgroundColor: "{colors.button-simple}"
    textColor: "{colors.text-primary}"
  nav-item:
    textColor: "{colors.text-secondary}"
    typography: "{typography.nav}"
    rounded: "{rounded.control}"
    padding: "0 14px"
    height: "44px"
  nav-item-hover:
    backgroundColor: "{colors.hover-glass}"
    textColor: "{colors.lit-text}"
  nav-item-active:
    backgroundColor: "{colors.focused-glass}"
    textColor: "{colors.lit-text}"
    rounded: "{rounded.control}"
  tab:
    textColor: "{colors.text-secondary}"
    typography: "{typography.tab}"
    padding: "10px 14px"
  tab-active:
    textColor: "{colors.lit-text}"
  input:
    backgroundColor: "{colors.field}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.control}"
    height: "44px"
  subnav-item-active:
    backgroundColor: "{colors.focused-glass}"
    textColor: "{colors.lit-text}"
    rounded: "{rounded.md}"
  toggle-on:
    backgroundColor: "{colors.focused-glass}"
    rounded: "{rounded.pill}"
    width: "57px"
    height: "34px"
  toggle-knob-on:
    backgroundColor: "{colors.cobalt-core}"
    rounded: "{rounded.pill}"
    size: "24px"
---

# Design System: AloStudio

## Overview

**Creative North Star: "The Hand-Bent Neon Room"**

The workspace is a dark room of hand-bent cobalt glass. Every surface is glass that has not been switched on: night-navy panels with a hairline edge that catches a little light along the top, and a faint cobalt spill washing the room from the top-left corner, as if from the signs. Current flows only into what orients you and what you act on: the brand wordmark, the page title hung as a glowing sign, the row of the section you are in, the tube under the open tab, the primary action, and a field while you type into it. Everything else stays quiet glass. The system exists to refuse the category default of a grey dashboard with one purple accent.

The shell is a wide glass sidebar (236px) with labelled rows set in a bent-tube monoline face, beside one large rounded work panel. Density inside the panel is that of a working tool used all day: Geologica carries the working text, tables and forms at 14px, and the neon lettering is reserved for signs, navigation and tabs. Expression lives in the light, not in friction: one quick ignition when a state switches on, never a loop.

A daylight rendition exists for the light theme: the same glass, unlit on a cool white ground. The sign and wordmark keep their cobalt colour but lose their glow; lit tubes use a deeper cobalt and a tighter halo so they still read without glare.

**Key Characteristics:**
- Night-navy ground with a cobalt light spill top-left; glass panels stepped by tone, edged by a 1px hairline, never lifted by drop shadow.
- Light means "current": the sign, the active nav row, the active tab tube, the primary action, the focused field. Nothing decorative glows.
- Three faces with fixed jobs: Tilt Neon for signs, navigation and tabs; Geologica for everything you read and enter; Neonderthaw only for the wordmark.
- Electrode orange is reserved for AI actions.
- Tabular numerals and tracked uppercase column labels in tables.

## Colors

A monochrome cobalt-on-navy world with a single warm counter-note held back for AI.

### Primary
- **Cobalt Tube Core** (cobalt-core): the body of the primary button, the outline of the lit nav row, the 2px tube under the active tab, a focused field's border, the toggle knob when on, focus rings, caret and native accent color. Also the glow source behind the sign and wordmark. In daylight it deepens to Daylight Cobalt (daylight-cobalt-core), which is also the unglowing colour of the daylight sign and wordmark.
- **Struck Cobalt** (cobalt-core-hover): the primary button's hover body; the tube brightens rather than darkens.
- **Lit Text** (lit-text): lettering that is lit or sits on a lit element: the sign, the wordmark, the active nav row and the active tab.

### Secondary
- **Electrode Orange** (electrode): the AI action color (the `ai` button token, `--new-ai-btn`). It is the electrode at the end of the tube, used only where an agent or AI acts.

### Neutral
- **Night Ground** (night-ground): the room behind the shell, carrying the Ambient Spill (ambient-spill) as a fixed radial wash at the top-left.
- **Panel Navy** (panel) and **Raised Panel** (panel-raised): the sidebar and work panel, table headers and the shared secondary button.
- **Recessed Field** (field): the well of every text input and select; darker than the panel so fields read as set into the glass.
- **Unlit Glass** (unlit-glass): every 1px hairline, card border, table border, tab rail and panel edge; the "off" state of the tube. **Glass Highlight** (glass-highlight) is the 1px top edge where a panel catches light.
- **Hover Glass** (hover-glass) and **Focused Glass** (focused-glass): the fill of a hovered row and of a selected-but-unlit item.
- **Simple Glass** (button-simple): the translucent fill of quiet utility buttons, always paired with an Unlit Glass outline.
- **Cold White** (text-primary) and **Smoke Blue** (text-secondary): body text; secondary text and inactive tabs. Inactive sidebar rows use Unlit Neon Text (`--neon-unlit-text`, #9eb0e6) with a hum glow.
- **Separator** (separator): the stronger divider used between grouped controls.

### Named Rules
**The Lit-Means-Current Rule.** Light marks only where you are, what you act on, or what you are typing into: the sign, the active nav row, the active tab's tube, the primary action, a focused field. Selected rows, toggles, the settings sub-nav, filters and hover states show selection with Focused Glass and Lit Text, never with a halo.

**The Humming Sidebar Exception.** The main sidebar's lettering is neon at three currents: unlit rows hum (Unlit Neon Text `--neon-unlit-text` with a low `--neon-hum` glow on text and icon), hover brings the tube up to Lit Text with a halo, and the current row is white-hot inside its lit outline with no fill behind it, so the glow reads against the night. This applies only to the main sidebar (`.neon-nav`, `.neon-nav-lit`); daylight drops every glow.

**The Electrode Rule.** Electrode Orange appears only on AI actions. It is never a warning, a badge or decoration.

**The Token-First Rule.** Color reaches components through the `--neon-*` and `--new-*` custom properties (Tailwind `neon`, `neonHover`, `neonLit`, `neonGlass`, `electrode`, `boxFocused`, `boxHover`, `newBorder`) and the world's component classes. The `--color-custom*` properties are deprecated and are not part of this system.

## Typography

**Display Font:** Tilt Neon (via next/font, CSS variable `--font-display`, Tailwind `font-display`)
**Body Font:** Geologica (via next/font, weights 300-700, latin and latin-ext)
**Wordmark Font:** Neonderthaw (CSS variable `--font-script`, Tailwind `font-script`)

**Character:** Tilt Neon is a monoline drawn like bent tube, so the lettering that names places reads as signage; Geologica is a calm, slightly geometric grotesque that keeps dense tables and forms legible all day; Neonderthaw is a looping neon script used once, for the brand. All three load once from `fonts.ts`, with latin-ext for Spanish-first copy.

### Hierarchy
- **Display / Sign** (400, 34px; 24px on mobile, 0.01em tracking): the page title in the top bar, lit with its own glow.
- **Tab** (400, 17px, Tilt Neon): section tabs inside a page (CRM, Inbox).
- **Nav** (400, 16px, Tilt Neon): sidebar row labels.
- **Title** (500, 16px): section and card titles inside panels, settings sub-nav entries.
- **Body** (400, 14px): table cells, form values, descriptions.
- **Label** (500, 12px): field captions, secondary lines under a setting.
- **Table Header** (11px, uppercase, 0.08em tracking): column labels, applied globally to `thead th`.
- **Wordmark** (400, 36px, Neonderthaw): the AloStudio name at the top of the sidebar, nowhere else.

### Named Rules
**The Three Faces Rule.** Tilt Neon names places (sign, nav, tabs); Geologica carries everything read or entered; Neonderthaw is the wordmark only. Never set body copy, buttons or table content in Tilt Neon, and never use the script anywhere but the brand.

**The Counting Rule.** Tables use tabular numerals (`font-variant-numeric: tabular-nums`) so times, counts and prices align in columns.

## Layout

A 12px outer gutter (8px on mobile, with 80px bottom padding for the mobile tab bar) holds two rounded glass panels: a 236px sidebar on the left (wordmark on top at 14px inset, a 28px gap, then nav rows with the settings row pinned to the bottom) and the work panel. The work panel stacks a top bar (80px, 64px on mobile; the sign left, theme, language and notifications right) above the page body. Pages with sections add a tab rail under the top bar: tabs on a 1px Unlit Glass bottom rule, 4px apart, 20px panel inset. Pages recompose Postiz's panels: Calendar puts the calendar first with the channels panel on the right and Create post next to the filters; Analytics turns channels into a horizontal strip above full-width charts; Settings uses a top tab rail (wrapping on desktop, scrolling on mobile) over a centred 960px column; Agent puts conversation history left and channels right. On mobile the sidebar becomes a full-height drawer opened from the top bar. Breakpoints are max-width queries: mobile at 1025px, tablet at 1300px, maxMedia at 1400px, iconBreak at 1560px. Inside panels, rhythm is 8px-based with 20-24px panel padding.

## Elevation & Depth

Depth is tonal, not shadowed: ground, panel and raised panel step up in navy value, fields step down into the glass, and each panel is outlined with a 1px Unlit Glass hairline plus a 1px Glass Highlight along its top edge. Every other glow is light, not lift: the core edge and halo of a lit tube, the short glowing tube under an active tab, the halo ring of a focused field, and the text glow of the sign and wordmark. Menus and popovers use a single soft, dark drop.

### Shadow Vocabulary
- **Glass panel edge** (`box-shadow: inset 0 0 0 1px var(--neon-glass), inset 0 1px 0 0 var(--neon-glass-highlight)`): the sidebar and the work panel.
- **Lit tube outline** (`box-shadow: inset 0 0 0 1px var(--neon-core), inset 0 0 12px -2px var(--neon-halo), 0 0 0 1px var(--neon-halo-far), 0 2px 14px -2px var(--neon-halo)`): the active nav row.
- **Lit tube solid** (`box-shadow: inset 0 0 0 1px var(--neon-edge), inset 0 0 14px -4px rgba(255,255,255,0.35), 0 0 0 1px var(--neon-halo), 0 2px 22px -2px var(--neon-halo)`): the primary button; on hover the halo widens to `0 4px 30px 0`.
- **Tab tube** (`box-shadow: 0 0 6px var(--neon-halo), 0 0 14px var(--neon-halo-far)` on a 2px Cobalt Tube Core bar): the active tab.
- **Field focus ring** (`box-shadow: 0 0 0 3px var(--neon-halo-far)` with a Cobalt Tube Core border): a field holding focus.
- **Sign glow** (`text-shadow: 0 0 2px var(--neon-lit-text), 0 0 8px var(--neon-core), 0 0 22px var(--neon-halo), 0 0 44px var(--neon-halo)`): the page title. Removed in daylight.
- **Menu drop** (`box-shadow: 0 12px 32px -8px rgba(1,3,10,0.8)`): dropdown menus and popovers.

### Named Rules
**The Light-Not-Lift Rule.** A glow means "this is lit", never "this floats". Do not add halos to cards, modals, rows or hover states.

**The Ignition Rule.** A lit state switches on once, with a 360ms ease-out from an unlit glass outline (`cubic-bezier(0.16, 1, 0.3, 1)`); transitions between lit states take 220ms (180ms for fields) on the same curve. Never pulse, flicker or loop. Under `prefers-reduced-motion` all of it is off.

## Shapes

Soft rectangles throughout. Small chips use 4px corners; cards, tables and the settings sub-nav 8px; every control you press or type into (buttons, nav rows, inputs, selects) shares 10px; the two shell panels 16px; toggles are full pills (100px). Borders are always 1px Unlit Glass; the lit state replaces the border with a cobalt line of the same 1px weight, so lighting never shifts geometry. The tab tube is the one exception to the 1px line: a 2px bar with rounded 2px ends, inset 14px from the tab edges and sitting on the rail.

## Components

### Buttons
Bent glass carrying current.
- **Shape:** gently rounded (10px), 40px tall, 24px horizontal padding.
- **Primary:** Cobalt Tube Core body, white text, the lit-tube-solid core edge and halo. This is the default of the shared `<Button>`.
- **Hover / Focus:** body brightens to Struck Cobalt and the halo widens; keyboard focus adds the global 2px cobalt outline at 2px offset.
- **Secondary:** shared `<Button secondary>`: Raised Panel fill, Cold White text, no light.
- **Simple:** quiet utility buttons: translucent Simple Glass fill with a 1px Unlit Glass outline; hover lowers opacity. Never lit.
- **Caller-painted (destructive, ghost):** when a caller supplies its own background class, the button drops the lit tube entirely and keeps only white text, so a red delete never glows cobalt.
- **AI:** Electrode Orange fill via the `ai` token.

### Navigation (sidebar)
- **Wordmark:** the AloStudio name in Neonderthaw at 36px, Lit Text with a cobalt glow, left-aligned at the top. A typographic placeholder until the owner's logo exists.
- **Rows:** icon then label in a row, 44px tall (38px on short viewports), 14px horizontal padding, 12px gap, 10px corners, Tilt Neon 16px; rows sit 6px apart (2px on short viewports).
- **Default:** Smoke Blue, no fill. **Hover:** Hover Glass fill, Lit Text.
- **Active:** Focused Glass fill, Lit Text, lit-tube outline, ignition on arrival. The signature move of the system.
- **Mobile:** the same panel as a full-height drawer behind a menu button in the top bar.

### Page sign
The page title is the shop sign: Tilt Neon at 34px (24px mobile) in Lit Text with the sign glow, left of the top bar. Its glow is allowed to overflow the title box. In daylight it is plain Daylight Cobalt lettering.

### Tabs
- **Rail:** tabs sit on a 1px Unlit Glass bottom rule spanning the panel.
- **Default:** Tilt Neon 17px, Smoke Blue, 10px by 14px padding; hover raises the text to Cold White. No fill, no chip.
- **Active:** Lit Text over the 2px glowing tab tube on the rail.

### Inputs / Fields
- **Style:** recessed field: Recessed Field fill, 1px Unlit Glass border, 10px corners, 44px tall, 14px Geologica text. Shared `<Input>` and `<Select>` and the CRM and Inbox search fields all use it.
- **Focus:** the border switches to Cobalt Tube Core and a 3px far-halo ring appears (180ms); caret and native accents are Cobalt Tube Core.

### Sub-navigation (settings)
Text list; the selected entry gets Focused Glass and Lit Text, hover gets Hover Glass. No side bar, no glow.

### Toggles
- **Off:** 57x34px pill with a faint 1px line border (the `fifth` line token) and a neutral knob.
- **On:** Focused Glass track with an Unlit Glass border and a 24px Cobalt Tube Core knob. The track is never lit.

### Cards / Containers
- **Corner Style:** 8px for content cards and tables, 16px for the shell panels.
- **Background:** Panel Navy or Raised Panel.
- **Shadow Strategy:** glass panel edge on the shell only; cards have none (see Elevation & Depth).
- **Border:** 1px Unlit Glass.
- **Internal Padding:** 20-24px.

### Tables
Raised Panel header row with 11px uppercase tracked column labels, 1px Unlit Glass row rules, tabular numerals, Smoke Blue empty state centered in the body.

## Do's and Don'ts

### Do:
- **Do** limit light to the sign, the active nav row, the active tab tube, the primary action and a focused field.
- **Do** express selection everywhere else with Focused Glass and Lit Text (`bg-boxFocused text-neonLit`).
- **Do** reach color through `--neon-*` / `--new-*` tokens and the world's classes (sign, tab, glass field, glass panel) so the daylight theme follows automatically.
- **Do** use the shared `<Button>`, `<Input>` and `<Select>` so the lit tube, the recessed field and their opt-outs stay in one place.
- **Do** set signs, nav rows and tabs in Tilt Neon (`font-display`) and everything else in Geologica.
- **Do** keep tabular numerals in any table or column of numbers.
- **Do** honor `prefers-reduced-motion`: ignition and tube transitions switch off.

### Don't:
- **Don't** add halos to toggles, cards, rows, modals, the settings sub-nav or hover states; a glow means lit, not elevated.
- **Don't** set body text, buttons or data in Tilt Neon, or use Neonderthaw for anything but the wordmark.
- **Don't** use Electrode Orange for anything but AI actions.
- **Don't** reintroduce the Postiz purple (#612bd3 family) or the `--color-custom*` tokens in new work.
- **Don't** animate light in loops; ignition fires once.
