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
    "push.title.default": "Notification",
    "push.body": "Conversation #{n}",
    "whatsapp.contact_fallback": "A contact",
}
