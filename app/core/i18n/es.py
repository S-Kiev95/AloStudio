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
    "notif.subject.usage_limit": "Tope de gasto: {title}",
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
    "notif.lead.usage_limit": "Se llegó a un tope de gasto mensual: {title}. Al 100 % se frenan las plantillas de WhatsApp o la IA hasta el mes que viene o hasta que subas el tope.",
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
    "notif.lead.usage_limit_plan": "Tope de IA de tu plan: {title}. Al 100 %, la IA sigue solo con créditos de IA (se descuentan solos); sin créditos se frena hasta el mes que viene o hasta que pases a un plan mayor.",
    "push.title.usage_limit": "Tope de gasto",
    "push.title.default": "Notificación",
    "push.body": "Conversación #{n}",
    # WhatsApp notice: what goes in the template when the contact has no name
    "whatsapp.contact_fallback": "Un contacto",
    # A WhatsApp call in a conversation (F7)
    "calls.message": "Llamada de WhatsApp",
    # What Meta reads to both sides before recording a call (F7)
    "calls.default_purpose": "control de calidad y seguimiento de tu consulta",
    # Who said what, in a call's transcript
    "calls.speaker.business": "Agente",
    "calls.speaker.customer": "Cliente",
    # Asking a customer whether the business may call them (F7)
    "calls.permission.request": "¿Te podemos llamar por WhatsApp para ayudarte con tu consulta?",
    "calls.permission.accepted": "Aceptó que lo llamen por WhatsApp (por 7 días)",
    "calls.permission.accepted_always": "Aceptó que lo llamen por WhatsApp (siempre)",
    "calls.permission.accepted_by_calling": "Al llamar, dejó que lo llamen de vuelta por 7 días",
    "calls.permission.rejected": "No quiere que lo llamen por WhatsApp",
    # A call nobody answered (F7): what the customer reads, and the label
    # that marks the conversation to call back
    "calls.missed.reply": "¡Hola! Vimos tu llamada y no pudimos atenderla. Te llamamos en unos minutos.",
    "calls.missed.label": "llamada-perdida",
    # Why a conversation closed (F17): the default categories, and the
    # title of the private note a closing leaves
    "closing.default.answered": "Consulta respondida",
    "closing.default.enrolled": "Se inscribió",
    "closing.default.not_interested": "No le interesó",
    "closing.default.no_reply": "El cliente no respondió",
    "closing.default.spam": "Spam o número equivocado",
    "closing.note_title": "Nota de cierre",
    # Contact lifecycle (F17): the default stages, and the line a move
    # leaves in the conversation
    "lifecycle.default.new_lead.name": "Nuevo interesado",
    "lifecycle.default.new_lead.description": "Escribió por primera vez.",
    "lifecycle.default.hot_lead.name": "Muy interesado",
    "lifecycle.default.hot_lead.description": "Quiere avanzar.",
    "lifecycle.default.payment.name": "En pago",
    "lifecycle.default.payment.description": "Está pagando o por pagar.",
    "lifecycle.default.customer.name": "Cliente",
    "lifecycle.default.customer.description": "Ya compró.",
    "lifecycle.default.cold_lead.name": "Se enfrió",
    "lifecycle.default.cold_lead.description": "Dejó de responder o ya no le interesa.",
    "lifecycle.activity": "{name} cambió la etapa a {stage}",
    "lifecycle.activity_cleared": "{name} le sacó la etapa al contacto",
    "lifecycle.someone": "Alguien",
    "decisions.priority_set": "La IA ({model}) puso la prioridad {level}",
    "decisions.priority_set_because": "La IA ({model}) puso la prioridad {level}: {reason}",
    "decisions.level.low": "Baja",
    "decisions.level.medium": "Media",
    "decisions.level.high": "Alta",
    "decisions.level.urgent": "Urgente",
}
