# AloStudio — Design System

The single source of truth for the frontend UI. Synthesised by applying
the **ui-ux-pro-max** skill to AloStudio's product type, and paired with
the **next-best-practices** skill for implementation. Every screen
(F.1+) must follow this.

> Skills (installed via `npx skills add`, in `.agents/skills/`, gitignored):
> - **ui-ux-pro-max** — design decisions (style, color, type, a11y, UX).
> - **next-best-practices** — Next.js conventions (RSC, async APIs, etc.).

## Product profile (drives every choice)
- **Type:** B2B SaaS / admin **dashboard** — data-dense (conversation
  inboxes, tables, forms) + a content composer (Instagram publishing).
- **Tone:** professional, calm, content-first. Not playful, not flashy.
- **Style:** **Binance-style** — a single high-voltage yellow accent
  (`#fcd535`, black text on it) over a near-black canvas (dark-first); flat
  color-block separation, no glassmorphism / atmospheric gradients. See the
  `binance-design` skill for the full token set + component specs.
- **Must-haves:** dark **and** light mode (dark is the default — Binance is
  dark-first), accessibility-first, responsive (sidebar desktop ≥1024 → drawer mobile).

---

## 1. Color — semantic tokens (never raw hex in components)

Define as CSS variables in `app/globals.css`, mapped to Tailwind via
`tailwind.config.ts`. Use `bg-surface`, `text-fg`, `text-primary`, etc.
**Both themes meet WCAG AA (4.5:1 body, 3:1 large/UI).**

| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg` | `#fafafa` | `#0b0e11` | app background (Binance canvas) |
| `--surface` | `#ffffff` | `#1e2329` | cards, panels |
| `--surface-2` | `#f5f5f5` | `#2b3139` | subtle fills, hover, elevated |
| `--fg` | `#181a20` | `#eaecef` | primary text |
| `--fg-muted` | `#707a8a` | `#848e9c` | secondary text (≥3:1) |
| `--border` | `#eaecef` | `#2b3139` | dividers, inputs (hairline) |
| `--primary` | `#fcd535` | `#fcd535` | Binance Yellow — brand / primary CTA |
| `--primary-fg` | `#181a20` | `#181a20` | text on primary (black on yellow) |
| `--success` | `#0b9d63` | `#0ecb81` | published, online (trading-up green) |
| `--warning` | `#c2520c` | `#ff9f43` | pending, scheduled |
| `--danger` | `#d9344a` | `#f6465d` | failed, destructive (trading-down red) |
| `--info` | `#2563eb` | `#3b82f6` | info, links, focus ring |

Rules: dark mode uses **desaturated/lighter tonal variants** (not
inverted); functional color **always** pairs with icon/text (color is
never the only signal); status chips (post state, availability) use
token + label.

## 2. Typography
- **Font:** `Inter` via `next/font/google` (self-hosted, `display: swap`),
  CSS var `--font-sans`. Monospace `ui-monospace` for ids/tokens.
- **Tabular numbers** (`font-variant-numeric: tabular-nums`) on every
  data column, count, price, timestamp → no layout shift.
- **Scale (px):** 12 · 14 · 16(base) · 18 · 20 · 24 · 30. Body 16,
  line-height 1.5; headings 600–700; labels 500.
- Line length 60–75ch for long text; truncate with tooltip for ids.

## 3. Spacing, layout, radius, elevation
- **4 / 8 spacing rhythm** (Tailwind default). Section tiers 16/24/32/48.
- Container `max-w-7xl`; content gutters scale up on wide screens.
- Radius (Binance scale): `sm 4 · md 6 · lg 8 · xl 12 · pill 9999`.
  Inputs/buttons `md` (6px); cards `lg`/`xl`; pill for top-of-page CTAs.
- **Elevation scale** (don't invent shadows): `e0` flat border · `e1`
  cards · `e2` dropdowns/popovers · `e3` modals. Dark mode leans on
  border + `surface-2`, lighter shadows.
- `z-index` scale: `base 0 · sticky 10 · dropdown 20 · overlay 40 ·
  modal 50 · toast 60`.

## 4. Components (shadcn/ui + Lucide)
- **shadcn/ui** (Radix) for primitives — accessible by default; own the
  code. **Lucide** icons only (SVG; **no emoji as icons**), one size
  scale (`16/20/24`), consistent stroke (`1.5`).
- **Buttons:** one **primary CTA per screen**; variants
  primary/secondary/ghost/destructive; disabled = reduced opacity +
  `disabled` attr + no pointer; async = spinner + disabled.
- **Forms:** visible `<label>` (not placeholder-only), required `*`,
  helper text persistent, **validate on blur**, error **below field** +
  `role="alert"`/`aria-live`, focus first invalid on submit; semantic
  input types; password show/hide; confirm destructive actions.
- **Tables** (conversations, posts, products): sortable headers with
  `aria-sort`; tabular nums; sticky header; **empty / loading (skeleton)
  / error** states always; virtualize ≥50 rows.
- **Status chips:** post state (pending/publishing/published/failed/
  deleted), agent availability — token color + text + icon.
- **Toasts:** `aria-live="polite"`, don't steal focus, auto-dismiss 3–5s,
  offer undo on destructive/bulk.

## 5. Interaction & accessibility (CRITICAL — non-negotiable)
- Visible **focus rings** (2px) on all interactive elements — never
  remove. Tab order matches visual order. Keyboard-operable everything.
- Hit targets **≥44×44** (use padding/`hitSlop`-equivalent on icon btns).
- `aria-label` on icon-only buttons; sequential headings; skip-to-content.
- Transitions **150–300ms**, `transform`/`opacity` only; honour
  `prefers-reduced-motion`. No layout-shifting press states.
- Loading >300ms → skeleton, not a bare spinner. Reserve space → CLS<0.1.

## 6. Charts (reports, F.8)
Match type to data (trend→line, comparison→bar, proportion→donut ≤5);
legends + tooltips (keyboard-reachable); accessible palette + patterns
(not color-only); empty/loading/error states; tabular/locale number
formatting; provide a table alternative for a11y.

---

## 7. Next.js conventions (next-best-practices)
- **Server Components by default**; `'use client'` only for interactive
  leaves (forms, realtime widgets). Keep client bundles small.
- **Async APIs (Next 15):** `await cookies()/headers()`, `await params`,
  `await searchParams` (already done in the BFF proxy).
- `next/font` for fonts, `next/image` for images (never `<img>`).
- **Route handlers** for the BFF proxy + auth; **Server Actions** for
  mutations where they fit; data-fetch with `Promise.all`/Suspense (no
  waterfalls).
- `error.tsx` / `not-found.tsx` per segment; wrap `useSearchParams` users
  in `<Suspense>`. `output: 'standalone'` for the Docker build.
- Metadata via `generateMetadata`; OG images via `next/og` for the public
  help center.

## 8. Per-screen checklist (run before each F.x merge)
- [ ] Semantic tokens only (no raw hex); light **and** dark verified.
- [ ] Body contrast ≥4.5:1, secondary ≥3:1, in both themes.
- [ ] Keyboard-operable; visible focus; icon buttons have `aria-label`.
- [ ] Touch targets ≥44px; one primary CTA; clear disabled/loading.
- [ ] Forms: labels, blur-validation, error below field + aria-live.
- [ ] Empty / loading (skeleton) / error states for every async view.
- [ ] No emoji icons; Lucide only; consistent size/stroke.
- [ ] `prefers-reduced-motion` respected; no CLS on load.
- [ ] Responsive at 375 / 768 / 1024 / 1440; no horizontal scroll.
