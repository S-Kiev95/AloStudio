# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Two audiences, both confirmed:

- **Small and mid-sized businesses** (beauty salons, insurers, shops) whose owners and small teams answer customers on WhatsApp, Instagram and Messenger, publish on social networks and keep a client list and appointment book.
- **Agencies and community managers** who run several brands or clients at once and resell or operate the tool on their behalf.

They use it during the working day, often switching between replying to a customer, checking the agenda and scheduling a post.

## Product Purpose

One workspace for a business's social presence and its customer conversations: schedule and publish posts to 30+ channels, answer every inbound message (WhatsApp, Instagram DM and comments, Messenger, email, Telegram) in one inbox, and keep customers, products and appointments in a built-in CRM. Success is a business that stops juggling separate apps for publishing, messaging and bookings.

## Positioning

- **All in one:** publishing (from Postiz), omnichannel inbox (from AloStudio, a Chatwoot port) and CRM/agenda live in one product and one frontend.
- **AI agents as operators:** agents can reply, find or create customers, book appointments and publish through MCP tools, not only draft text.
- **LATAM first:** Spanish-first product, WhatsApp as the central channel.

## Operating Context

- Web app (Next.js, Tailwind 3) in the `apps/frontend` of the Postiz monorepo; the inbox data comes from the AloStudio sidecar API through a backend proxy.
- Main areas: calendar/launches (post scheduling), media library, analytics, inbox (conversations, contacts, reports), CRM (customers, products, weekly agenda), settings, team.
- Integrates with Meta (Facebook Pages, Instagram, Threads, WhatsApp Cloud API) and many other networks; Meta App Review requires real screencasts of the flows.

## Capabilities and Constraints

- Fork of Postiz (AGPL-3.0): source must stay public if offered as a service; the "Postiz" name cannot be used as the brand.
- Upstream Postiz is merged regularly into `fork-main`, so restyling should go through tokens and shared components rather than rewriting every screen.
- Existing CSS custom properties `--color-custom*` are deprecated.
- Open decision: logo and app icon are still being designed by the owner.

## Brand Commitments

- Product name: **AloStudio** (confirmed by the owner, 2026-10-16).
- Primary language Spanish (Rioplatense voice is used in existing legal pages: "podés", "escribí").

## Evidence on Hand

- Legal pages live: privacy, terms and data deletion at the AloStudio deployment.
- No customer testimonials, metrics or case studies exist yet; do not fabricate them.

## Product Principles

1. One place for the whole customer relationship: a conversation, the customer record and the next appointment are never more than one step apart.
2. Fast daily operation beats showmanship inside the app; expression lives in identity details, not in friction.
3. WhatsApp-first and Spanish-first, without breaking the many other channels.
4. Agents are first-class operators, so every action an agent can take must be visible and reversible for the human.
