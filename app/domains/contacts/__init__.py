"""Contact domain — contacts, contact_inboxes, notes.

Ported from:
  reference/chatwoot/app/models/{contact,contact_inbox,note}.rb
  reference/chatwoot/app/controllers/api/v1/accounts/contacts_controller.rb
  reference/chatwoot/app/controllers/api/v1/accounts/contacts/{notes,contact_inboxes}_controller.rb
  reference/chatwoot/app/actions/{contact_identify,contact_merge}_action.rb
  reference/chatwoot/app/builders/contact_inbox_builder.rb

Phase 3 scope:
  * Contact CRUD + search.
  * ContactInbox create (API-channel only; other channels land in Phase 5).
  * Note CRUD.
  * Identify + merge flows — merge is *partial* pending Phase 4 (we move
    ContactInbox and Note rows but skip the Conversation/Message passes
    because those tables don't exist yet; flagged in ContactMergeAction).
"""
