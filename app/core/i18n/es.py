"""Spanish (the source). Rioplatense, with "vos", like the dashboard."""

MESSAGES: dict[str, str] = {
    # Shared pieces of every mail
    "mail.greeting": "Hola {name},",
    "mail.signoff": "— AloStudio",
    # Email confirmation
    "confirm.subject": "Confirmá tu email en AloStudio",
    "confirm.body": (
        "Para confirmar tu email y empezar a usar AloStudio, hacé clic acá:\n\n"
        "    {link}\n\n"
        "Si no creaste una cuenta, podés ignorar este email."
    ),
    # Password reset
    "reset.subject": "Elegí tu contraseña de AloStudio",
    "reset.body": (
        "Recibimos un pedido para elegir una contraseña nueva para tu cuenta de AloStudio.\n"
        "Hacé clic acá para elegirla:\n\n"
        "    {link}\n\n"
        "El enlace vence en 6 horas. Si no lo pediste, podés ignorar este email:\n"
        "tu contraseña no cambia."
    ),
    # Agent invitation
    "invite.subject": "Te invitaron a {account} en AloStudio",
    "invite.body": (
        '{inviter} te invitó a unirte a la cuenta "{account}" en AloStudio.\n\n'
        "Para terminar de configurar tu cuenta y elegir una contraseña, hacé clic acá:\n\n"
        "    {link}\n\n"
        "El enlace vence en 7 días. Si no esperabas esta invitación podés ignorar este email."
    ),
    # Notification mail
    "notif.subject.conversation_creation": "Nueva conversación #{n}",
    "notif.subject.conversation_assignment": "Se te asignó la conversación #{n}",
    "notif.subject.assigned_conversation_new_message": "Nuevo mensaje en la conversación #{n}",
    "notif.subject.conversation_bot_handoff": "La conversación #{n} pide atención de una persona",
    "notif.subject.crm_activity_due": "La tarea \"{title}\" venció",
    "notif.subject.default": "Nueva notificación",
    "notif.lead.conversation_creation": (
        "Se creó una nueva conversación en una bandeja de la que sos miembro."
    ),
    "notif.lead.conversation_assignment": "Se te asignó una conversación.",
    "notif.lead.assigned_conversation_new_message": (
        "Recibiste un nuevo mensaje en una conversación asignada a vos."
    ),
    "notif.lead.conversation_bot_handoff": (
        "El bot derivó una conversación al equipo: alguien tiene que responderla."
    ),
    "notif.lead.crm_activity_due": "Venció una tarea que tenés a cargo: {title}.",
    "notif.lead.default": "Tenés una nueva notificación en AloStudio.",
    "notif.body": (
        "{lead}\n\n"
        "Verla acá:\n\n"
        "    {link}\n\n"
        "Podés ajustar qué notificaciones recibís por email desde\n"
        "Ajustes → Notificaciones."
    ),
    # Web-push
    "push.title.conversation_creation": "Nueva conversación",
    "push.title.conversation_assignment": "Conversación asignada",
    "push.title.assigned_conversation_new_message": "Nuevo mensaje",
    "push.title.participating_conversation_new_message": "Nuevo mensaje",
    "push.title.conversation_mention": "Te mencionaron",
    "push.title.sla_missed_first_response": "SLA incumplido",
    "push.title.sla_missed_next_response": "SLA incumplido",
    "push.title.sla_missed_resolution": "SLA incumplido",
    "push.title.conversation_bot_handoff": "Piden atención de una persona",
    "push.title.crm_activity_due": "Tarea vencida",
    "push.title.default": "Notificación",
    "push.body": "Conversación #{n}",
    # WhatsApp notice: what goes in the template when the contact has no name
    "whatsapp.contact_fallback": "Un contacto",
}
