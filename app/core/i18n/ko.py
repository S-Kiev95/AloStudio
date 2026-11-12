"""Korean."""

MESSAGES: dict[str, str] = {
    "mail.greeting": "{name} 님, 안녕하세요.",
    "mail.signoff": "— AloStudio",
    "confirm.subject": "AloStudio 이메일을 확인해 주세요",
    "confirm.body": (
        "이메일을 확인하고 AloStudio를 사용하려면 여기를 클릭하세요:\n\n"
        "    {link}\n\n"
        "계정을 만든 적이 없다면 이 이메일은 무시하셔도 됩니다."
    ),
    "reset.subject": "AloStudio 비밀번호를 설정하세요",
    "reset.body": (
        "AloStudio 계정의 새 비밀번호 설정 요청을 받았습니다.\n"
        "여기를 클릭해 설정하세요:\n\n"
        "    {link}\n\n"
        "링크는 6시간 뒤 만료됩니다. 요청하지 않았다면 이 이메일은 무시하셔도 됩니다.\n"
        "비밀번호는 바뀌지 않습니다."
    ),
    "invite.subject": "AloStudio의 {account}에 초대되었습니다",
    "invite.body": (
        '{inviter} 님이 AloStudio의 "{account}" 계정에 초대했습니다.\n\n'
        "계정 설정을 마치고 비밀번호를 정하려면 여기를 클릭하세요:\n\n"
        "    {link}\n\n"
        "링크는 7일 뒤 만료됩니다. 예상하지 못한 초대라면 이 이메일은 무시하셔도 됩니다."
    ),
    "notif.subject.conversation_creation": "새 대화 #{n}",
    "notif.subject.conversation_assignment": "대화 #{n}이(가) 배정되었습니다",
    "notif.subject.assigned_conversation_new_message": "대화 #{n}에 새 메시지",
    "notif.subject.conversation_bot_handoff": "대화 #{n}에 사람의 응대가 필요합니다",
    "notif.subject.default": "새 알림",
    "notif.lead.conversation_creation": "내가 속한 받은편지함에 새 대화가 생성되었습니다.",
    "notif.lead.conversation_assignment": "대화가 배정되었습니다.",
    "notif.lead.assigned_conversation_new_message": "나에게 배정된 대화에 새 메시지가 도착했습니다.",
    "notif.lead.conversation_bot_handoff": (
        "봇이 대화를 팀에 넘겼습니다. 누군가 답장해야 합니다."
    ),
    "notif.lead.default": "AloStudio에 새 알림이 있습니다.",
    "notif.body": (
        "{lead}\n\n"
        "여기에서 보기:\n\n"
        "    {link}\n\n"
        "이메일로 받을 알림은\n"
        "설정 → 알림에서 바꿀 수 있습니다."
    ),
    "push.title.conversation_creation": "새 대화",
    "push.title.conversation_assignment": "대화 배정됨",
    "push.title.assigned_conversation_new_message": "새 메시지",
    "push.title.participating_conversation_new_message": "새 메시지",
    "push.title.conversation_mention": "나를 언급했습니다",
    "push.title.sla_missed_first_response": "SLA 미준수",
    "push.title.sla_missed_next_response": "SLA 미준수",
    "push.title.sla_missed_resolution": "SLA 미준수",
    "push.title.conversation_bot_handoff": "사람의 응대가 필요합니다",
    "push.title.default": "알림",
    "push.body": "대화 #{n}",
    "whatsapp.contact_fallback": "연락처",
}
