"""Japanese, in です/ます."""

MESSAGES: dict[str, str] = {
    "mail.greeting": "{name} 様",
    "mail.signoff": "— AloStudio",
    "confirm.subject": "AloStudio のメールアドレスを確認してください",
    "confirm.body": (
        "メールアドレスを確認して AloStudio を使い始めるには、こちらをクリックしてください:\n\n"
        "    {link}\n\n"
        "アカウントを作成した覚えがない場合は、このメールを無視してください。"
    ),
    "reset.subject": "AloStudio のパスワードを設定してください",
    "reset.body": (
        "AloStudio アカウントの新しいパスワード設定のリクエストを受け付けました。\n"
        "こちらをクリックして設定してください:\n\n"
        "    {link}\n\n"
        "リンクの有効期限は 6 時間です。心当たりがない場合はこのメールを無視してください。\n"
        "パスワードは変わりません。"
    ),
    "invite.subject": "AloStudio の {account} に招待されました",
    "invite.body": (
        "{inviter} さんから AloStudio のアカウント「{account}」への招待が届いています。\n\n"
        "アカウントの設定を完了してパスワードを決めるには、こちらをクリックしてください:\n\n"
        "    {link}\n\n"
        "リンクの有効期限は 7 日間です。心当たりがない場合はこのメールを無視してください。"
    ),
    "notif.subject.conversation_creation": "新しい会話 #{n}",
    "notif.subject.conversation_assignment": "会話 #{n} が割り当てられました",
    "notif.subject.assigned_conversation_new_message": "会話 #{n} に新しいメッセージ",
    "notif.subject.conversation_bot_handoff": "会話 #{n} に担当者の対応が必要です",
    "notif.subject.crm_activity_due": "タスク「{title}」の期限が来ました",
    "notif.subject.default": "新しい通知",
    "notif.lead.conversation_creation": "あなたがメンバーの受信箱で新しい会話が作成されました。",
    "notif.lead.conversation_assignment": "会話が割り当てられました。",
    "notif.lead.assigned_conversation_new_message": (
        "あなたに割り当てられた会話に新しいメッセージが届きました。"
    ),
    "notif.lead.conversation_bot_handoff": (
        "ボットが会話をチームに引き継ぎました。誰かが返信する必要があります。"
    ),
    "notif.lead.crm_activity_due": "担当しているタスクの期限が来ました: {title}。",
    "notif.lead.default": "AloStudio に新しい通知があります。",
    "notif.body": (
        "{lead}\n\n"
        "こちらで確認できます:\n\n"
        "    {link}\n\n"
        "メールで受け取る通知は\n"
        "設定 → 通知 で変更できます。"
    ),
    "push.title.conversation_creation": "新しい会話",
    "push.title.conversation_assignment": "会話が割り当てられました",
    "push.title.assigned_conversation_new_message": "新しいメッセージ",
    "push.title.participating_conversation_new_message": "新しいメッセージ",
    "push.title.conversation_mention": "メンションされました",
    "push.title.sla_missed_first_response": "SLA 未達",
    "push.title.sla_missed_next_response": "SLA 未達",
    "push.title.sla_missed_resolution": "SLA 未達",
    "push.title.conversation_bot_handoff": "担当者の対応が必要です",
    "push.title.crm_activity_due": "タスクの期限",
    "push.title.default": "通知",
    "push.body": "会話 #{n}",
    "whatsapp.contact_fallback": "連絡先",
}
