"""Custom attribute definition domain.

Ported from:
  reference/chatwoot/app/models/custom_attribute_definition.rb
  reference/chatwoot/app/controllers/api/v1/accounts/custom_attribute_definitions_controller.rb

This is an account-scoped registry of user-defined attribute schemas
that then show up as keys on ``Contact.custom_attributes`` and
(eventually, Phase 4) ``Conversation.custom_attributes``. Phase 3 ships
the full CRUD endpoint set — nothing about it depends on Conversation,
so we can close this domain end-to-end right now.
"""
