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
    "agent.tool.read_done": "アカウントを確認しました",
    "agent.tool.write_done": "完了",
    "agent.tool.failed": "完了できませんでした",
    "agent.pending.title": "この操作を確認してください",
    "agent.pending.confirm": "確認",
    "agent.yes": "はい",
    "agent.no": "いいえ",
    "agent.args.conversation_id": "会話",
    "agent.args.contact_id": "連絡先",
    "agent.args.inbox_id": "受信箱",
    "agent.args.team_id": "チーム",
    "agent.args.assignee_id": "担当者",
    "agent.args.agent_id": "エージェント",
    "agent.args.owner_id": "責任者",
    "agent.args.content": "メッセージ",
    "agent.args.message": "メッセージ",
    "agent.args.private": "非公開メモ",
    "agent.args.status": "ステータス",
    "agent.args.priority": "優先度",
    "agent.args.labels": "ラベル",
    "agent.args.name": "名前",
    "agent.args.title": "タイトル",
    "agent.args.description": "説明",
    "agent.args.notes": "メモ",
    "agent.args.email": "メール",
    "agent.args.phone_number": "電話番号",
    "agent.args.value": "金額",
    "agent.args.currency": "通貨",
    "agent.args.starts_at": "開始",
    "agent.args.ends_at": "終了",
    "agent.args.due_at": "期限",
    "agent.args.scheduled_at": "日付",
    "agent.args.product_id": "商品",
    "agent.args.product_ids": "商品",
    "agent.args.stage_id": "ステージ",
    "agent.args.active": "有効",
    "agent.args.enabled": "オン",
    "agent.status.pending": "確認待ち",
    "agent.status.invalid": "提案がチェックを通りませんでした",
    "agent.status.rejected": "提案を破棄しました",
    "agent.tool.list_publication_channels.done": "チャネルを確認しました",
    "agent.tool.list_publication_channels.failed": "チャネルを確認できませんでした",
    "agent.tool.list_media.done": "メディアライブラリを確認しました",
    "agent.tool.list_media.failed": "メディアライブラリを確認できませんでした",
    "agent.tool.list_publications.done": "カレンダーを確認しました",
    "agent.tool.list_publications.failed": "カレンダーを確認できませんでした",
    "agent.tool.get_publishing_analytics.done": "統計を確認しました",
    "agent.tool.get_publishing_analytics.failed": "統計を確認できませんでした",
    "agent.tool.create_publication.done": "投稿を予約しました",
    "agent.tool.create_publication.failed": "投稿を予約できませんでした",
    "agent.tool.cancel_publication.done": "投稿を削除しました",
    "agent.tool.cancel_publication.failed": "投稿を削除できませんでした",
    "agent.pending.cancel_publication.title": "投稿を削除",
    "agent.pending.cancel_publication.confirm": "削除",
    "agent.pending.create_publication.title": "投稿を予約",
    "agent.pending.create_publication.confirm": "予約",
    "agent.pending.create_publication.confirm_now": "今すぐ公開",
    "agent.args.macro_id": "マクロ",
    "agent.args.conversation_ids": "会話",
    "handoff.activity.contact": "このチャットの担当者に引き継ぎました",
    "handoff.activity.label": "ラベル「{label}」により引き継ぎました",
    "handoff.activity.account": "全体の担当者に引き継ぎました",
    "agent.free.busy": "Freeモードは別の質問に対応中です。少し待ってからもう一度お試しください。",
    "agent.free.failed": "Freeモードは回答できませんでした。もう一度試すか、Fastを使ってください。",
    "agent.free.fast_hint": "Freeでは手順の説明のみです。実行してほしい場合はFastに切り替えてください。",
    "ai_agent.activity.took": "AloStudio AIに引き継ぎました",
    "ai_agent.note.summary": "AI、チーム向けの要約: {summary}",
    "ai_agent.note.failed": "AIが応答できなかったため、会話をチームに引き継ぎました。",
    "ai_agent.activity.released": "担当者が返信したため、この会話ではAIは応答しません",
    "ai_agent.done": "AIが実行: {action}",
    "ai_agent.action.book": "予約「{title}」{when}",
    "ai_agent.action.contact": "連絡先の情報: {fields}",
    "ai_agent.action.stage": "ステージ: {stage}",
    "ai_agent.action.label": "ラベル: {label}",
    "ai_agent.action.opportunity": "商談「{title}」",
    "ai_agent.appointment_title": "予約",
    "ai_agent.appointment_note": "会話 #{n} からAIが予約",
}
