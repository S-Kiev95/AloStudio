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
    "notif.subject.usage_limit": "Limite de gasto: {title}",
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
    "notif.lead.usage_limit": "Um limite de gasto mensal foi atingido: {title}. Em 100 %, os modelos do WhatsApp ou a IA param até o próximo mês ou até você aumentar o limite.",
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
    "push.title.usage_limit": "Limite de gasto",
    "push.title.default": "Notificação",
    "push.body": "Conversa #{n}",
    "whatsapp.contact_fallback": "Um contato",
    # A WhatsApp call in a conversation (F7)
    "calls.message": "Chamada do WhatsApp",
    # What Meta reads to both sides before recording a call (F7)
    "calls.default_purpose": "controle de qualidade e acompanhamento da sua solicitação",
    # Who said what, in a call's transcript
    "calls.speaker.business": "Atendente",
    "calls.speaker.customer": "Cliente",
    # Asking a customer whether the business may call them (F7)
    "calls.permission.request": "Podemos ligar para você pelo WhatsApp para ajudar com a sua solicitação?",
    "calls.permission.accepted": "Aceitou receber ligações pelo WhatsApp (por 7 dias)",
    "calls.permission.accepted_always": "Aceitou receber ligações pelo WhatsApp (sempre)",
    "calls.permission.accepted_by_calling": "Ao ligar, permitiu receber retorno por 7 dias",
    "calls.permission.rejected": "Não quer receber ligações pelo WhatsApp",
    # A call nobody answered (F7): what the customer reads, and the label
    # that marks the conversation to call back
    "calls.missed.reply": "Olá! Vimos sua ligação e não conseguimos atender. Ligamos para você em alguns minutos.",
    "calls.missed.label": "chamada-perdida",
    # Why a conversation closed (F17): the default categories, and the
    # title of the private note a closing leaves
    "closing.default.answered": "Dúvida respondida",
    "closing.default.enrolled": "Se inscreveu",
    "closing.default.not_interested": "Não teve interesse",
    "closing.default.no_reply": "O cliente não respondeu",
    "closing.default.spam": "Spam ou número errado",
    "closing.note_title": "Nota de encerramento",
    # Contact lifecycle (F17): the default stages, and the line a move
    # leaves in the conversation
    "lifecycle.default.new_lead.name": "Novo interessado",
    "lifecycle.default.new_lead.description": "Escreveu pela primeira vez.",
    "lifecycle.default.hot_lead.name": "Muito interessado",
    "lifecycle.default.hot_lead.description": "Quer avançar.",
    "lifecycle.default.payment.name": "Em pagamento",
    "lifecycle.default.payment.description": "Está pagando ou vai pagar.",
    "lifecycle.default.customer.name": "Cliente",
    "lifecycle.default.customer.description": "Já comprou.",
    "lifecycle.default.cold_lead.name": "Esfriou",
    "lifecycle.default.cold_lead.description": "Parou de responder ou perdeu o interesse.",
    "lifecycle.activity": "{name} mudou a etapa para {stage}",
    "lifecycle.activity_cleared": "{name} tirou a etapa do contato",
    "lifecycle.someone": "Alguém",
}
