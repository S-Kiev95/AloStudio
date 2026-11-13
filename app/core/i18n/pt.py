"""Portuguese (Brazil), with "você"."""

MESSAGES: dict[str, str] = {
    "mail.greeting": "Olá, {name},",
    "mail.signoff": "— AloStudio",
    "confirm.subject": "Confirme seu email no AloStudio",
    "confirm.body": (
        "Para confirmar seu email e começar a usar o AloStudio, clique aqui:\n\n"
        "    {link}\n\n"
        "Se você não criou uma conta, pode ignorar este email."
    ),
    "reset.subject": "Escolha sua senha do AloStudio",
    "reset.body": (
        "Recebemos um pedido para escolher uma nova senha para sua conta do AloStudio.\n"
        "Clique aqui para escolhê-la:\n\n"
        "    {link}\n\n"
        "O link vence em 6 horas. Se você não pediu, pode ignorar este email:\n"
        "sua senha não muda."
    ),
    "invite.subject": "Você foi convidado para {account} no AloStudio",
    "invite.body": (
        '{inviter} convidou você para entrar na conta "{account}" no AloStudio.\n\n'
        "Para terminar de configurar sua conta e escolher uma senha, clique aqui:\n\n"
        "    {link}\n\n"
        "O link vence em 7 dias. Se você não esperava este convite, pode ignorar este email."
    ),
    "notif.subject.conversation_creation": "Nova conversa #{n}",
    "notif.subject.conversation_assignment": "A conversa #{n} foi atribuída a você",
    "notif.subject.assigned_conversation_new_message": "Nova mensagem na conversa #{n}",
    "notif.subject.conversation_bot_handoff": "A conversa #{n} precisa de uma pessoa",
    "notif.subject.crm_activity_due": "A tarefa \"{title}\" venceu",
    "notif.subject.default": "Nova notificação",
    "notif.lead.conversation_creation": (
        "Uma nova conversa foi criada em uma caixa de entrada da qual você é membro."
    ),
    "notif.lead.conversation_assignment": "Uma conversa foi atribuída a você.",
    "notif.lead.assigned_conversation_new_message": (
        "Você recebeu uma nova mensagem em uma conversa atribuída a você."
    ),
    "notif.lead.conversation_bot_handoff": (
        "O bot passou uma conversa para a equipe: alguém precisa respondê-la."
    ),
    "notif.lead.crm_activity_due": "Venceu uma tarefa sob sua responsabilidade: {title}.",
    "notif.lead.default": "Você tem uma nova notificação no AloStudio.",
    "notif.body": (
        "{lead}\n\n"
        "Veja aqui:\n\n"
        "    {link}\n\n"
        "Você pode ajustar quais notificações recebe por email em\n"
        "Ajustes → Notificações."
    ),
    "push.title.conversation_creation": "Nova conversa",
    "push.title.conversation_assignment": "Conversa atribuída",
    "push.title.assigned_conversation_new_message": "Nova mensagem",
    "push.title.participating_conversation_new_message": "Nova mensagem",
    "push.title.conversation_mention": "Mencionaram você",
    "push.title.sla_missed_first_response": "SLA descumprido",
    "push.title.sla_missed_next_response": "SLA descumprido",
    "push.title.sla_missed_resolution": "SLA descumprido",
    "push.title.conversation_bot_handoff": "Precisam de uma pessoa",
    "push.title.crm_activity_due": "Tarefa vencida",
    "push.title.default": "Notificação",
    "push.body": "Conversa #{n}",
    "whatsapp.contact_fallback": "Um contato",
}
