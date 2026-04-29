# Phase 5b — Channel: Email (IMAP/SMTP)

**Why this phase:** the Email channel is the second most-used channel
after the website widget. Every Chatwoot deployment with a real
helpdesk workload — support@, info@, billing@ — uses it.

**Reference anchors (verbatim paths under `reference/chatwoot/`):**

* `app/models/channel/email.rb`
* `app/services/imap/{base_fetch,fetch,google_fetch,microsoft_fetch}_email_service.rb`
* `app/jobs/inboxes/fetch_imap_emails_job.rb`
* `app/jobs/inboxes/fetch_imap_email_inboxes_job.rb`
* `app/services/mailbox/imap_mailbox.rb`
* `app/mailers/conversation_reply_mailer.rb`
* `app/jobs/conversation_reply_email_worker.rb` (SendReplyJob)

---

## Scope decision: IMAP/SMTP password only

We port the password-auth path. **OAuth2 (Gmail / Microsoft Entra) is
deferred to Phase 9** — Greenmail can't simulate the consent flow,
and OAuth lands together with the other OAuth integrations (Slack,
Dialogflow). Password auth covers:

* Gmail accounts with 2FA + an App Password.
* Microsoft 365 with App Password (when the tenant allows them).
* Any standard IMAP/SMTP server (Postfix/Dovecot, Exim, Zimbra,
  Exchange, Sendmail, Courier, Cyrus, etc.).

That's >90% of the inboxes Chatwoot deploys actually serve. The OAuth
gap is documented in PLAN.md so a deployment that ONLY supports
"Sign in with Google" workflows knows when to expect it.

## Test infrastructure: Greenmail

`docker-compose.yml` gains a ``greenmail`` service exposing IMAP
(3143/3993), SMTP (3025/3465/3587), and an HTTP control API on
port 8081. Tests use:

* The HTTP API (POST /api/user/...) to seed agent inboxes with
  pre-existing messages → IMAP ingest tests.
* The HTTP API (GET /api/messages) to assert outbound mails landed
  → SMTP send tests.

Greenmail accepts any user/password the test creates on the fly,
so fixtures need no out-of-band auth setup.

---

## Milestones

### 5b.1 — Email channel model + migration + InboxBuilder branch

**Tasks:**
- [ ] `app/domains/inboxes/models.py::EmailChannel` — `channel_email`
      table mirroring Chatwoot's schema (the IMAP/SMTP password
      columns + ``provider``/``provider_config`` JSONB for the
      eventual OAuth fields).
- [ ] Alembic migration creating the table + the unique indexes on
      `email` and `forward_to_email`.
- [ ] InboxBuilder ``email`` branch validating ``email``,
      ``forward_to_email``, plus the SMTP/IMAP host triplets when
      either side is enabled.
- [ ] Add ``CHANNEL_TYPE_EMAIL = 'Channel::Email'`` constant.
- [ ] Unit tests for the builder + an integration test that round-trips
      an Email inbox through the existing inboxes router.

### 5b.2 — Threading parser (Message-ID + In-Reply-To + References)

Pure parsing. Resolves an inbound email to either an existing
conversation (if any of the references match a Message we sent) or
``None`` (start new conversation).

**Tasks:**
- [ ] `app/domains/email/threading.py` —
      `find_conversation_by_thread(session, account_id, headers) ->
      Conversation | None`. Looks for ``In-Reply-To`` and
      ``References`` ``Message-ID`` values matching messages our
      side sent (we'll have stamped ``Message-ID`` on outbound).
- [ ] Helper to extract ``message-id`` values from raw header strings
      (RFC-2822 angle-bracket parsing).
- [ ] Unit tests covering: simple In-Reply-To match, nested
      References chain, malformed headers, mixed-case header names.

### 5b.3 — SMTP outbound: ConversationReplyMailer (next session)

Sends agent replies as proper email. Stamps a ``Message-ID`` we can
match on inbound for threading.

**Tasks:**
- [ ] `app/domains/email/mailer.py` — Pythonic equivalent of
      ``ConversationReplyMailer``. Builds a MIMEMultipart message
      with: From, To, Subject ("Re: <conversation subject>"),
      In-Reply-To + References pointing at the previous outbound,
      Message-ID we generate, plain-text + HTML body.
- [ ] Integrates with the existing ``send_message`` outbound path
      (currently a no-op for non-API channels) — when the
      conversation's inbox is ``Channel::Email``, route the message
      through the mailer.
- [ ] Tests against Greenmail SMTP — POST /widget/messages on an
      Email inbox results in a Greenmail-received mail with the
      correct headers.

### 5b.4 — IMAP ingest job (next session)

Polls each Email inbox's IMAP server, parses incoming mails into
Messages on the matching conversation (or a new one).

**Tasks:**
- [ ] `app/jobs/fetch_imap_emails.py` — ARQ task that iterates all
      Email channels with ``imap_enabled``, runs the fetch, processes
      each inbound message via the threading parser.
- [ ] `app/domains/email/inbound.py` — converts a parsed `email.message
      .EmailMessage` to a Message + Contact pair, looking up or
      creating both.
- [ ] Mutex per inbox (Redis SETNX with TTL) so two cron ticks don't
      double-fetch.
- [ ] Tests: seed Greenmail with a mail addressed to the inbox,
      run the task, assert a Message + Conversation exist on our
      side. Reply (5b.3) → seed Greenmail with a reply mail
      threaded by the original Message-ID, assert it appends to
      the existing conversation.

### 5b.5 — Parity tests + mark 5b done (next session)

- [ ] Cross-backend 4xx assertions on the Email-inbox CRUD endpoints
      (auth gates already covered by 5a-style parity tests).
- [ ] Update `PLAN.md` to mark 5b done.

---

## Deferred

* **OAuth2 (Gmail / Microsoft 365)** — Phase 9. Needs Google Cloud /
  Microsoft Entra app registration + a callback UI. The
  ``provider`` + ``provider_config`` columns ship empty in 5b so the
  schema is forward-compatible.
* **Re-authorization detection** (Chatwoot's `Reauthorizable`
  concern) — token-rotation infrastructure that's only meaningful
  with OAuth. Lands with OAuth in Phase 9.
* **Inline images / multipart attachments** — only plain-text + HTML
  bodies in 5b. MIME-attachment ingest comes with Phase 10.
* **`forward_to_email` ingestion** (the catch-all alias Chatwoot
  generates so inbound mails to a Chatwoot-hosted address work
  without IMAP) — needs SES/SendGrid inbound webhooks (Phase 8b).
* **Bounce handling / SPF-DMARC** — Phase 9 hardening.

---

## Commit style

`phase5b: <area>: <short summary>` — one commit per milestone.
