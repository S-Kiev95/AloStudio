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
    "notif.subject.usage_limit": "支出上限: {title}",
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
    "notif.lead.usage_limit": "月間の支出上限に達しました: {title}。100% になると、翌月または上限を引き上げるまで WhatsApp テンプレートまたは AI が停止します。",
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
    "push.title.usage_limit": "支出上限",
    "push.title.default": "通知",
    "push.body": "会話 #{n}",
    "whatsapp.contact_fallback": "連絡先",
    # A WhatsApp call in a conversation (F7)
    "calls.message": "WhatsApp通話",
    # What Meta reads to both sides before recording a call (F7)
    "calls.default_purpose": "品質管理とお問い合わせへの対応",
    # Who said what, in a call's transcript
    "calls.speaker.business": "担当者",
    "calls.speaker.customer": "顧客",
    # Asking a customer whether the business may call them (F7)
    "calls.permission.request": "お問い合わせの件でWhatsAppからお電話してもよろしいですか?",
    "calls.permission.accepted": "WhatsAppでの電話を許可しました(7日間)",
    "calls.permission.accepted_always": "WhatsAppでの電話を許可しました(常に)",
    "calls.permission.accepted_by_calling": "電話をかけたことで、7日間の折り返しを許可しました",
    "calls.permission.rejected": "WhatsAppでの電話を希望していません",
    # A call nobody answered (F7): what the customer reads, and the label
    # that marks the conversation to call back
    "calls.missed.reply": "こんにちは。お電話に出られず申し訳ありません。数分後にこちらからおかけ直しします。",
    "calls.missed.label": "不在着信",
    # Why a conversation closed (F17): the default categories, and the
    # title of the private note a closing leaves
    "closing.default.answered": "問い合わせに回答",
    "closing.default.enrolled": "申し込み済み",
    "closing.default.not_interested": "興味なし",
    "closing.default.no_reply": "お客様から返信なし",
    "closing.default.spam": "スパム・番号違い",
    "closing.note_title": "クローズメモ",
    # Contact lifecycle (F17): the default stages, and the line a move
    # leaves in the conversation
    "lifecycle.default.new_lead.name": "新規リード",
    "lifecycle.default.new_lead.description": "初めて連絡してきた。",
    "lifecycle.default.hot_lead.name": "有望リード",
    "lifecycle.default.hot_lead.description": "前に進みたい。",
    "lifecycle.default.payment.name": "支払い中",
    "lifecycle.default.payment.description": "支払い中、またはこれから支払う。",
    "lifecycle.default.customer.name": "顧客",
    "lifecycle.default.customer.description": "購入済み。",
    "lifecycle.default.cold_lead.name": "冷えたリード",
    "lifecycle.default.cold_lead.description": "返信がない、または興味を失った。",
    "lifecycle.activity": "{name}がステージを{stage}に変更しました",
    "lifecycle.activity_cleared": "{name}が連絡先のステージを外しました",
    "lifecycle.someone": "誰か",
    "decisions.priority_set": "AI（{model}）が優先度を{level}にしました",
    "decisions.priority_set_because": "AI（{model}）が優先度を{level}にしました: {reason}",
    "decisions.level.low": "低",
    "decisions.level.medium": "中",
    "decisions.level.high": "高",
    "decisions.level.urgent": "緊急",
}
