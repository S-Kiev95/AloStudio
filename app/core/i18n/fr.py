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
    # Why a conversation closed (F17): the default categories, and the
    # title of the private note a closing leaves
    "closing.default.answered": "Question répondue",
    "closing.default.enrolled": "S'est inscrit",
    "closing.default.not_interested": "Pas intéressé",
    "closing.default.no_reply": "Le client n'a pas répondu",
    "closing.default.spam": "Spam ou mauvais numéro",
    "closing.note_title": "Note de clôture",
    # Contact lifecycle (F17): the default stages, and the line a move
    # leaves in the conversation
    "lifecycle.default.new_lead.name": "Nouveau prospect",
    "lifecycle.default.new_lead.description": "A écrit pour la première fois.",
    "lifecycle.default.hot_lead.name": "Prospect chaud",
    "lifecycle.default.hot_lead.description": "Veut avancer.",
    "lifecycle.default.payment.name": "Paiement",
    "lifecycle.default.payment.description": "Paie ou va payer.",
    "lifecycle.default.customer.name": "Client",
    "lifecycle.default.customer.description": "A acheté.",
    "lifecycle.default.cold_lead.name": "Prospect froid",
    "lifecycle.default.cold_lead.description": "Ne répond plus ou n'est plus intéressé.",
    "lifecycle.activity": "{name} a passé le contact à {stage}",
    "lifecycle.activity_cleared": "{name} a retiré l'étape du contact",
    "lifecycle.someone": "Quelqu'un",
    "agent.tool.read_done": "A consulté le compte",
    "agent.tool.write_done": "Fait",
    "agent.tool.failed": "Impossible de terminer",
    "agent.pending.title": "Confirmez cette action",
    "agent.pending.confirm": "Confirmer",
    "agent.yes": "Oui",
    "agent.no": "Non",
    "agent.args.conversation_id": "Conversation",
    "agent.args.contact_id": "Contact",
    "agent.args.inbox_id": "Boîte de réception",
    "agent.args.team_id": "Équipe",
    "agent.args.assignee_id": "Assignée à",
    "agent.args.agent_id": "Agent",
    "agent.args.owner_id": "Responsable",
    "agent.args.content": "Message",
    "agent.args.message": "Message",
    "agent.args.private": "Note privée",
    "agent.args.status": "Statut",
    "agent.args.priority": "Priorité",
    "agent.args.labels": "Étiquettes",
    "agent.args.name": "Nom",
    "agent.args.title": "Titre",
    "agent.args.description": "Description",
    "agent.args.notes": "Notes",
    "agent.args.email": "Email",
    "agent.args.phone_number": "Téléphone",
    "agent.args.value": "Valeur",
    "agent.args.currency": "Devise",
    "agent.args.starts_at": "Du",
    "agent.args.ends_at": "Au",
    "agent.args.due_at": "Échéance",
    "agent.args.scheduled_at": "Date",
    "agent.args.product_id": "Produit",
    "agent.args.product_ids": "Produits",
    "agent.args.stage_id": "Étape",
    "agent.args.active": "Actif",
    "agent.args.enabled": "Activé",
    "agent.status.pending": "En attente de votre confirmation",
    "agent.status.invalid": "La proposition n’a pas passé la vérification",
    "agent.status.rejected": "Vous avez écarté la proposition",
    "agent.tool.list_publication_channels.done": "A consulté vos canaux",
    "agent.tool.list_publication_channels.failed": "Impossible de consulter vos canaux",
    "agent.tool.list_media.done": "A parcouru votre médiathèque",
    "agent.tool.list_media.failed": "Impossible de parcourir la médiathèque",
    "agent.tool.list_publications.done": "A consulté votre calendrier",
    "agent.tool.list_publications.failed": "Impossible de consulter le calendrier",
    "agent.tool.get_publishing_analytics.done": "A consulté les statistiques",
    "agent.tool.get_publishing_analytics.failed": "Impossible de consulter les statistiques",
    "agent.tool.create_publication.done": "A programmé la publication",
    "agent.tool.create_publication.failed": "Impossible de programmer la publication",
    "agent.tool.cancel_publication.done": "A supprimé la publication",
    "agent.tool.cancel_publication.failed": "Impossible de supprimer la publication",
    "agent.pending.cancel_publication.title": "Supprimer la publication",
    "agent.pending.cancel_publication.confirm": "Supprimer",
    "agent.pending.create_publication.title": "Programmer la publication",
    "agent.pending.create_publication.confirm": "Programmer",
    "agent.pending.create_publication.confirm_now": "Publier maintenant",
    "agent.args.macro_id": "Macro",
    "agent.args.conversation_ids": "Conversations",
    "handoff.activity.contact": "Transférée au responsable de ce chat",
    "handoff.activity.label": "Transférée selon l'étiquette {label}",
    "handoff.activity.account": "Transférée au responsable par défaut",
    "ai_agent.activity.took": "Transférée à l'IA d'AloStudio",
    "ai_agent.note.summary": "IA, résumé pour l'équipe : {summary}",
    "ai_agent.note.failed": "L'IA n'a pas pu répondre et a transmis la conversation à l'équipe.",
    "ai_agent.activity.released": "Une personne a répondu : l'IA cesse de répondre dans cette conversation",
    "ai_agent.done": "L'IA a fait : {action}",
    "ai_agent.action.book": "Rendez-vous « {title} » le {when}",
    "ai_agent.action.contact": "Données du contact : {fields}",
    "ai_agent.action.stage": "Étape : {stage}",
    "ai_agent.action.label": "Étiquette : {label}",
    "ai_agent.action.opportunity": "Opportunité « {title} »",
    "ai_agent.appointment_title": "Rendez-vous",
    "ai_agent.appointment_note": "Pris par l'IA depuis la conversation #{n}",
}
