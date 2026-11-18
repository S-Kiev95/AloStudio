"""English."""

MESSAGES: dict[str, str] = {
    "mail.greeting": "Hi {name},",
    "mail.signoff": "— AloStudio",
    "confirm.subject": "Confirm your email on AloStudio",
    "confirm.body": (
        "To confirm your email and start using AloStudio, click here:\n\n"
        "    {link}\n\n"
        "If you didn't create an account, you can ignore this email."
    ),
    "reset.subject": "Choose your AloStudio password",
    "reset.body": (
        "We got a request to choose a new password for your AloStudio account.\n"
        "Click here to choose it:\n\n"
        "    {link}\n\n"
        "The link expires in 6 hours. If you didn't ask for it, you can ignore this email:\n"
        "your password doesn't change."
    ),
    "invite.subject": "You were invited to {account} on AloStudio",
    "invite.body": (
        '{inviter} invited you to join the "{account}" account on AloStudio.\n\n'
        "To finish setting up your account and choose a password, click here:\n\n"
        "    {link}\n\n"
        "The link expires in 7 days. If you weren't expecting this invitation, you can ignore this email."
    ),
    "notif.subject.conversation_creation": "New conversation #{n}",
    "notif.subject.conversation_assignment": "Conversation #{n} was assigned to you",
    "notif.subject.assigned_conversation_new_message": "New message in conversation #{n}",
    "notif.subject.conversation_bot_handoff": "Conversation #{n} needs a person",
    "notif.subject.crm_activity_due": "The task \"{title}\" is due",
    "notif.subject.usage_limit": "Spend cap: {title}",
    "notif.subject.default": "New notification",
    "notif.lead.conversation_creation": "A new conversation was created in an inbox you belong to.",
    "notif.lead.conversation_assignment": "A conversation was assigned to you.",
    "notif.lead.assigned_conversation_new_message": (
        "You got a new message in a conversation assigned to you."
    ),
    "notif.lead.conversation_bot_handoff": (
        "The bot handed a conversation to the team: someone needs to reply."
    ),
    "notif.lead.crm_activity_due": "A task you own is due: {title}.",
    "notif.lead.usage_limit": "A monthly spend cap was reached: {title}. At 100 %, WhatsApp templates or the AI stop until next month or until you raise the cap.",
    "notif.lead.default": "You have a new notification on AloStudio.",
    "notif.body": (
        "{lead}\n\n"
        "See it here:\n\n"
        "    {link}\n\n"
        "You can choose which notifications you get by email in\n"
        "Settings → Notifications."
    ),
    "push.title.conversation_creation": "New conversation",
    "push.title.conversation_assignment": "Conversation assigned",
    "push.title.assigned_conversation_new_message": "New message",
    "push.title.participating_conversation_new_message": "New message",
    "push.title.conversation_mention": "You were mentioned",
    "push.title.sla_missed_first_response": "SLA missed",
    "push.title.sla_missed_next_response": "SLA missed",
    "push.title.sla_missed_resolution": "SLA missed",
    "push.title.conversation_bot_handoff": "A person is needed",
    "push.title.crm_activity_due": "Task due",
    "push.title.usage_limit": "Spend cap",
    "push.title.default": "Notification",
    "push.body": "Conversation #{n}",
    "whatsapp.contact_fallback": "A contact",
    # A WhatsApp call in a conversation (F7)
    "calls.message": "WhatsApp call",
    # What Meta reads to both sides before recording a call (F7)
    "calls.default_purpose": "quality assurance and follow-up of your request",
    # Who said what, in a call's transcript
    "calls.speaker.business": "Agent",
    "calls.speaker.customer": "Customer",
    # Asking a customer whether the business may call them (F7)
    "calls.permission.request": "Can we call you on WhatsApp to help with your request?",
    "calls.permission.accepted": "Agreed to be called on WhatsApp (for 7 days)",
    "calls.permission.accepted_always": "Agreed to be called on WhatsApp (always)",
    "calls.permission.accepted_by_calling": "By calling, allowed a call back for 7 days",
    "calls.permission.rejected": "Does not want to be called on WhatsApp",
    # A call nobody answered (F7): what the customer reads, and the label
    # that marks the conversation to call back
    "calls.missed.reply": "Hi! We saw your call and couldn't take it. We'll call you back in a few minutes.",
    "calls.missed.label": "missed-call",
    # Why a conversation closed (F17): the default categories, and the
    # title of the private note a closing leaves
    "closing.default.answered": "Question answered",
    "closing.default.enrolled": "Signed up",
    "closing.default.not_interested": "Not interested",
    "closing.default.no_reply": "Customer didn't reply",
    "closing.default.spam": "Spam or wrong number",
    "closing.note_title": "Closing note",
    # Contact lifecycle (F17): the default stages, and the line a move
    # leaves in the conversation
    "lifecycle.default.new_lead.name": "New lead",
    "lifecycle.default.new_lead.description": "Wrote for the first time.",
    "lifecycle.default.hot_lead.name": "Hot lead",
    "lifecycle.default.hot_lead.description": "Wants to move forward.",
    "lifecycle.default.payment.name": "Payment",
    "lifecycle.default.payment.description": "Paying or about to pay.",
    "lifecycle.default.customer.name": "Customer",
    "lifecycle.default.customer.description": "Has bought.",
    "lifecycle.default.cold_lead.name": "Cold lead",
    "lifecycle.default.cold_lead.description": "Stopped answering or lost interest.",
    "lifecycle.activity": "{name} moved the contact to {stage}",
    "lifecycle.activity_cleared": "{name} took the contact out of their stage",
    "lifecycle.someone": "Someone",
    "agent.tool.read_done": "Looked up the account",
    "agent.tool.write_done": "Done",
    "agent.tool.failed": "Couldn't complete it",
    "agent.pending.title": "Confirm this action",
    "agent.pending.confirm": "Confirm",
    "agent.yes": "Yes",
    "agent.no": "No",
    "agent.args.conversation_id": "Conversation",
    "agent.args.contact_id": "Contact",
    "agent.args.inbox_id": "Inbox",
    "agent.args.team_id": "Team",
    "agent.args.assignee_id": "Assigned to",
    "agent.args.agent_id": "Agent",
    "agent.args.owner_id": "Owner",
    "agent.args.content": "Message",
    "agent.args.message": "Message",
    "agent.args.private": "Private note",
    "agent.args.status": "Status",
    "agent.args.priority": "Priority",
    "agent.args.labels": "Labels",
    "agent.args.name": "Name",
    "agent.args.title": "Title",
    "agent.args.description": "Description",
    "agent.args.notes": "Notes",
    "agent.args.email": "Email",
    "agent.args.phone_number": "Phone",
    "agent.args.value": "Value",
    "agent.args.currency": "Currency",
    "agent.args.starts_at": "From",
    "agent.args.ends_at": "To",
    "agent.args.due_at": "Due",
    "agent.args.scheduled_at": "Date",
    "agent.args.product_id": "Product",
    "agent.args.product_ids": "Products",
    "agent.args.stage_id": "Stage",
    "agent.args.active": "Active",
    "agent.args.enabled": "Enabled",
    "agent.status.pending": "Waiting for your confirmation",
    "agent.status.invalid": "The proposal didn't pass the check",
    "agent.status.rejected": "You discarded the proposal",
    "agent.tool.list_publication_channels.done": "Looked up your channels",
    "agent.tool.list_publication_channels.failed": "Couldn't look up your channels",
    "agent.tool.list_media.done": "Checked your media library",
    "agent.tool.list_media.failed": "Couldn't check the media library",
    "agent.tool.list_publications.done": "Checked your calendar",
    "agent.tool.list_publications.failed": "Couldn't check the calendar",
    "agent.tool.get_publishing_analytics.done": "Looked up the stats",
    "agent.tool.get_publishing_analytics.failed": "Couldn't look up the stats",
    "agent.tool.create_publication.done": "Scheduled the post",
    "agent.tool.create_publication.failed": "Couldn't schedule the post",
    "agent.tool.cancel_publication.done": "Deleted the post",
    "agent.tool.cancel_publication.failed": "Couldn't delete the post",
    "agent.pending.cancel_publication.title": "Delete post",
    "agent.pending.cancel_publication.confirm": "Delete",
    "agent.pending.create_publication.title": "Schedule post",
    "agent.pending.create_publication.confirm": "Schedule",
    "agent.pending.create_publication.confirm_now": "Publish now",
    "agent.args.macro_id": "Macro",
    "agent.args.conversation_ids": "Conversations",
    "handoff.activity.contact": "Handed off to this chat's responsible",
    "handoff.activity.label": "Handed off by the label {label}",
    "handoff.activity.account": "Handed off to the default responsible",
}
