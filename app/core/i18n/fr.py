"""French, with "vous"."""

MESSAGES: dict[str, str] = {
    "mail.greeting": "Bonjour {name},",
    "mail.signoff": "— AloStudio",
    "confirm.subject": "Confirmez votre e-mail sur AloStudio",
    "confirm.body": (
        "Pour confirmer votre e-mail et commencer à utiliser AloStudio, cliquez ici :\n\n"
        "    {link}\n\n"
        "Si vous n’avez pas créé de compte, vous pouvez ignorer cet e-mail."
    ),
    "reset.subject": "Choisissez votre mot de passe AloStudio",
    "reset.body": (
        "Nous avons reçu une demande pour choisir un nouveau mot de passe pour votre compte AloStudio.\n"
        "Cliquez ici pour le choisir :\n\n"
        "    {link}\n\n"
        "Le lien expire dans 6 heures. Si vous ne l’avez pas demandé, vous pouvez ignorer cet e-mail :\n"
        "votre mot de passe ne change pas."
    ),
    "invite.subject": "Vous êtes invité à {account} sur AloStudio",
    "invite.body": (
        "{inviter} vous a invité à rejoindre le compte « {account} » sur AloStudio.\n\n"
        "Pour finir de configurer votre compte et choisir un mot de passe, cliquez ici :\n\n"
        "    {link}\n\n"
        "Le lien expire dans 7 jours. Si vous n’attendiez pas cette invitation, vous pouvez ignorer cet e-mail."
    ),
    "notif.subject.conversation_creation": "Nouvelle conversation #{n}",
    "notif.subject.conversation_assignment": "La conversation #{n} vous a été attribuée",
    "notif.subject.assigned_conversation_new_message": "Nouveau message dans la conversation #{n}",
    "notif.subject.conversation_bot_handoff": "La conversation #{n} a besoin d’une personne",
    "notif.subject.crm_activity_due": "La tâche « {title} » est échue",
    "notif.subject.usage_limit": "Plafond de dépenses : {title}",
    "notif.subject.default": "Nouvelle notification",
    "notif.lead.conversation_creation": (
        "Une nouvelle conversation a été créée dans une boîte de réception dont vous êtes membre."
    ),
    "notif.lead.conversation_assignment": "Une conversation vous a été attribuée.",
    "notif.lead.assigned_conversation_new_message": (
        "Vous avez reçu un nouveau message dans une conversation qui vous est attribuée."
    ),
    "notif.lead.conversation_bot_handoff": (
        "Le bot a transféré une conversation à l’équipe : quelqu’un doit y répondre."
    ),
    "notif.lead.crm_activity_due": "Une tâche dont vous êtes responsable est échue : {title}.",
    "notif.lead.usage_limit": (
        "Un plafond de dépenses mensuel a été atteint : {title}. À 100 %, les "
        "modèles WhatsApp ou l'IA s'arrêtent jusqu'au mois prochain ou jusqu'à "
        "ce que vous augmentiez le plafond."
    ),
    "notif.lead.default": "Vous avez une nouvelle notification sur AloStudio.",
    "notif.body": (
        "{lead}\n\n"
        "La voir ici :\n\n"
        "    {link}\n\n"
        "Vous pouvez choisir les notifications reçues par e-mail dans\n"
        "Paramètres → Notifications."
    ),
    "push.title.conversation_creation": "Nouvelle conversation",
    "push.title.conversation_assignment": "Conversation attribuée",
    "push.title.assigned_conversation_new_message": "Nouveau message",
    "push.title.participating_conversation_new_message": "Nouveau message",
    "push.title.conversation_mention": "On vous a mentionné",
    "push.title.sla_missed_first_response": "SLA non respecté",
    "push.title.sla_missed_next_response": "SLA non respecté",
    "push.title.sla_missed_resolution": "SLA non respecté",
    "push.title.conversation_bot_handoff": "Une personne est demandée",
    "push.title.crm_activity_due": "Tâche échue",
    "push.title.usage_limit": "Plafond de dépenses",
    "push.title.default": "Notification",
    "push.body": "Conversation #{n}",
    "whatsapp.contact_fallback": "Un contact",
    # A WhatsApp call in a conversation (F7)
    "calls.message": "Appel WhatsApp",
    # What Meta reads to both sides before recording a call (F7)
    "calls.default_purpose": "contrôle qualité et suivi de votre demande",
    # Who said what, in a call's transcript
    "calls.speaker.business": "Agent",
    "calls.speaker.customer": "Client",
    # Asking a customer whether the business may call them (F7)
    "calls.permission.request": "Pouvons-nous vous appeler sur WhatsApp pour vous aider avec votre demande ?",
    "calls.permission.accepted": "A accepté d’être appelé sur WhatsApp (pendant 7 jours)",
    "calls.permission.accepted_always": "A accepté d’être appelé sur WhatsApp (toujours)",
    "calls.permission.accepted_by_calling": "En appelant, a permis d’être rappelé pendant 7 jours",
    "calls.permission.rejected": "Ne veut pas être appelé sur WhatsApp",
    # A call nobody answered (F7): what the customer reads, and the label
    # that marks the conversation to call back
    "calls.missed.reply": "Bonjour ! Nous avons vu votre appel sans pouvoir répondre. Nous vous rappelons dans quelques minutes.",
    "calls.missed.label": "appel-manque",
}
