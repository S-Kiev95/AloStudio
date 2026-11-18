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
    "notif.subject.crm_activity_due": "\"{title}\" 작업의 기한이 되었습니다",
    "notif.subject.usage_limit": "지출 한도: {title}",
    "notif.subject.default": "새 알림",
    "notif.lead.conversation_creation": "내가 속한 받은편지함에 새 대화가 생성되었습니다.",
    "notif.lead.conversation_assignment": "대화가 배정되었습니다.",
    "notif.lead.assigned_conversation_new_message": "나에게 배정된 대화에 새 메시지가 도착했습니다.",
    "notif.lead.conversation_bot_handoff": (
        "봇이 대화를 팀에 넘겼습니다. 누군가 답장해야 합니다."
    ),
    "notif.lead.crm_activity_due": "담당 작업의 기한이 되었습니다: {title}.",
    "notif.lead.usage_limit": "월간 지출 한도에 도달했습니다: {title}. 100%가 되면 다음 달까지 또는 한도를 올릴 때까지 WhatsApp 템플릿이나 AI가 멈춥니다.",
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
    "push.title.crm_activity_due": "작업 기한",
    "push.title.usage_limit": "지출 한도",
    "push.title.default": "알림",
    "push.body": "대화 #{n}",
    "whatsapp.contact_fallback": "연락처",
    # A WhatsApp call in a conversation (F7)
    "calls.message": "WhatsApp 통화",
    # What Meta reads to both sides before recording a call (F7)
    "calls.default_purpose": "품질 관리 및 문의 후속 조치",
    # Who said what, in a call's transcript
    "calls.speaker.business": "상담원",
    "calls.speaker.customer": "고객",
    # Asking a customer whether the business may call them (F7)
    "calls.permission.request": "문의하신 내용으로 WhatsApp으로 전화드려도 될까요?",
    "calls.permission.accepted": "WhatsApp 통화를 허락했습니다(7일 동안)",
    "calls.permission.accepted_always": "WhatsApp 통화를 허락했습니다(항상)",
    "calls.permission.accepted_by_calling": "전화를 걸어 7일 동안 회신 통화를 허락했습니다",
    "calls.permission.rejected": "WhatsApp 통화를 원하지 않습니다",
    # A call nobody answered (F7): what the customer reads, and the label
    # that marks the conversation to call back
    "calls.missed.reply": "안녕하세요! 전화를 받지 못했어요. 몇 분 안에 다시 전화드릴게요.",
    "calls.missed.label": "부재중-전화",
    # Why a conversation closed (F17): the default categories, and the
    # title of the private note a closing leaves
    "closing.default.answered": "문의 답변 완료",
    "closing.default.enrolled": "등록함",
    "closing.default.not_interested": "관심 없음",
    "closing.default.no_reply": "고객 응답 없음",
    "closing.default.spam": "스팸 또는 잘못된 번호",
    "closing.note_title": "종료 메모",
    # Contact lifecycle (F17): the default stages, and the line a move
    # leaves in the conversation
    "lifecycle.default.new_lead.name": "신규 리드",
    "lifecycle.default.new_lead.description": "처음 연락했어요.",
    "lifecycle.default.hot_lead.name": "유망 리드",
    "lifecycle.default.hot_lead.description": "진행하고 싶어 해요.",
    "lifecycle.default.payment.name": "결제 중",
    "lifecycle.default.payment.description": "결제 중이거나 곧 결제해요.",
    "lifecycle.default.customer.name": "고객",
    "lifecycle.default.customer.description": "구매했어요.",
    "lifecycle.default.cold_lead.name": "식은 리드",
    "lifecycle.default.cold_lead.description": "응답이 없거나 관심을 잃었어요.",
    "lifecycle.activity": "{name}님이 단계를 {stage}(으)로 바꿨어요",
    "lifecycle.activity_cleared": "{name}님이 연락처의 단계를 뺐어요",
    "lifecycle.someone": "누군가",
    "agent.tool.read_done": "계정을 조회했습니다",
    "agent.tool.write_done": "완료",
    "agent.tool.failed": "완료할 수 없습니다",
    "agent.pending.title": "이 작업을 확인하세요",
    "agent.pending.confirm": "확인",
    "agent.yes": "예",
    "agent.no": "아니요",
    "agent.args.conversation_id": "대화",
    "agent.args.contact_id": "연락처",
    "agent.args.inbox_id": "받은편지함",
    "agent.args.team_id": "팀",
    "agent.args.assignee_id": "담당자",
    "agent.args.agent_id": "상담원",
    "agent.args.owner_id": "책임자",
    "agent.args.content": "메시지",
    "agent.args.message": "메시지",
    "agent.args.private": "비공개 메모",
    "agent.args.status": "상태",
    "agent.args.priority": "우선순위",
    "agent.args.labels": "라벨",
    "agent.args.name": "이름",
    "agent.args.title": "제목",
    "agent.args.description": "설명",
    "agent.args.notes": "메모",
    "agent.args.email": "이메일",
    "agent.args.phone_number": "전화번호",
    "agent.args.value": "금액",
    "agent.args.currency": "통화",
    "agent.args.starts_at": "시작",
    "agent.args.ends_at": "종료",
    "agent.args.due_at": "기한",
    "agent.args.scheduled_at": "날짜",
    "agent.args.product_id": "상품",
    "agent.args.product_ids": "상품",
    "agent.args.stage_id": "단계",
    "agent.args.active": "활성",
    "agent.args.enabled": "사용",
    "agent.status.pending": "확인 대기 중",
    "agent.status.invalid": "제안이 검토를 통과하지 못했습니다",
    "agent.status.rejected": "제안을 취소했습니다",
    "agent.tool.list_publication_channels.done": "채널을 조회했습니다",
    "agent.tool.list_publication_channels.failed": "채널을 조회할 수 없습니다",
    "agent.tool.list_media.done": "미디어 라이브러리를 확인했습니다",
    "agent.tool.list_media.failed": "미디어 라이브러리를 확인할 수 없습니다",
    "agent.tool.list_publications.done": "캘린더를 확인했습니다",
    "agent.tool.list_publications.failed": "캘린더를 확인할 수 없습니다",
    "agent.tool.get_publishing_analytics.done": "통계를 조회했습니다",
    "agent.tool.get_publishing_analytics.failed": "통계를 조회할 수 없습니다",
    "agent.tool.create_publication.done": "게시물을 예약했습니다",
    "agent.tool.create_publication.failed": "게시물을 예약할 수 없습니다",
    "agent.tool.cancel_publication.done": "게시물을 삭제했습니다",
    "agent.tool.cancel_publication.failed": "게시물을 삭제할 수 없습니다",
    "agent.pending.cancel_publication.title": "게시물 삭제",
    "agent.pending.cancel_publication.confirm": "삭제",
    "agent.pending.create_publication.title": "게시물 예약",
    "agent.pending.create_publication.confirm": "예약",
    "agent.pending.create_publication.confirm_now": "지금 게시",
    "agent.args.macro_id": "매크로",
    "agent.args.conversation_ids": "대화",
    "handoff.activity.contact": "이 채팅의 담당자에게 넘겼습니다",
    "handoff.activity.label": "라벨 {label}에 따라 넘겼습니다",
    "handoff.activity.account": "기본 담당자에게 넘겼습니다",
    "ai_agent.activity.took": "AloStudio AI에게 넘겼습니다",
    "ai_agent.note.summary": "AI, 팀을 위한 요약: {summary}",
    "ai_agent.note.failed": "AI가 답변하지 못해 대화를 팀에 넘겼습니다.",
    "ai_agent.activity.released": "담당자가 답장하여 이 대화에서 AI가 더 이상 답하지 않습니다",
}
