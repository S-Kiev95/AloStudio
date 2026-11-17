"""German, with "du", like the dashboard."""

MESSAGES: dict[str, str] = {
    "mail.greeting": "Hallo {name},",
    "mail.signoff": "— AloStudio",
    "confirm.subject": "Bestätige deine E-Mail bei AloStudio",
    "confirm.body": (
        "Um deine E-Mail zu bestätigen und AloStudio zu nutzen, klick hier:\n\n"
        "    {link}\n\n"
        "Wenn du kein Konto erstellt hast, kannst du diese E-Mail ignorieren."
    ),
    "reset.subject": "Wähle dein AloStudio-Passwort",
    "reset.body": (
        "Wir haben eine Anfrage erhalten, ein neues Passwort für dein AloStudio-Konto zu wählen.\n"
        "Klick hier, um es zu wählen:\n\n"
        "    {link}\n\n"
        "Der Link läuft in 6 Stunden ab. Wenn du das nicht angefordert hast, kannst du diese E-Mail ignorieren:\n"
        "dein Passwort bleibt gleich."
    ),
    "invite.subject": "Du wurdest zu {account} bei AloStudio eingeladen",
    "invite.body": (
        "{inviter} hat dich eingeladen, dem Konto „{account}“ bei AloStudio beizutreten.\n\n"
        "Um dein Konto fertig einzurichten und ein Passwort zu wählen, klick hier:\n\n"
        "    {link}\n\n"
        "Der Link läuft in 7 Tagen ab. Wenn du diese Einladung nicht erwartet hast, kannst du diese E-Mail ignorieren."
    ),
    "notif.subject.conversation_creation": "Neue Konversation #{n}",
    "notif.subject.conversation_assignment": "Dir wurde die Konversation #{n} zugewiesen",
    "notif.subject.assigned_conversation_new_message": "Neue Nachricht in Konversation #{n}",
    "notif.subject.conversation_bot_handoff": "Konversation #{n} braucht eine Person",
    "notif.subject.crm_activity_due": "Die Aufgabe „{title}“ ist fällig",
    "notif.subject.usage_limit": "Ausgabenlimit: {title}",
    "notif.subject.default": "Neue Benachrichtigung",
    "notif.lead.conversation_creation": (
        "In einem Posteingang, in dem du Mitglied bist, wurde eine neue Konversation erstellt."
    ),
    "notif.lead.conversation_assignment": "Dir wurde eine Konversation zugewiesen.",
    "notif.lead.assigned_conversation_new_message": (
        "Du hast eine neue Nachricht in einer dir zugewiesenen Konversation erhalten."
    ),
    "notif.lead.conversation_bot_handoff": (
        "Der Bot hat eine Konversation ans Team übergeben: Jemand muss antworten."
    ),
    "notif.lead.crm_activity_due": "Eine Aufgabe, für die du verantwortlich bist, ist fällig: {title}.",
    "notif.lead.usage_limit": "Ein monatliches Ausgabenlimit wurde erreicht: {title}. Bei 100 % stoppen WhatsApp-Vorlagen oder die KI bis zum nächsten Monat oder bis du das Limit erhöhst.",
    "notif.lead.default": "Du hast eine neue Benachrichtigung bei AloStudio.",
    "notif.body": (
        "{lead}\n\n"
        "Hier ansehen:\n\n"
        "    {link}\n\n"
        "Welche Benachrichtigungen du per E-Mail bekommst, stellst du unter\n"
        "Einstellungen → Benachrichtigungen ein."
    ),
    "push.title.conversation_creation": "Neue Konversation",
    "push.title.conversation_assignment": "Konversation zugewiesen",
    "push.title.assigned_conversation_new_message": "Neue Nachricht",
    "push.title.participating_conversation_new_message": "Neue Nachricht",
    "push.title.conversation_mention": "Du wurdest erwähnt",
    "push.title.sla_missed_first_response": "SLA verfehlt",
    "push.title.sla_missed_next_response": "SLA verfehlt",
    "push.title.sla_missed_resolution": "SLA verfehlt",
    "push.title.conversation_bot_handoff": "Eine Person wird gebraucht",
    "push.title.crm_activity_due": "Aufgabe fällig",
    "push.title.usage_limit": "Ausgabenlimit",
    "push.title.default": "Benachrichtigung",
    "push.body": "Konversation #{n}",
    "whatsapp.contact_fallback": "Ein Kontakt",
    # A WhatsApp call in a conversation (F7)
    "calls.message": "WhatsApp-Anruf",
    # What Meta reads to both sides before recording a call (F7)
    "calls.default_purpose": "Qualitätssicherung und Nachverfolgung Ihres Anliegens",
    # Who said what, in a call's transcript
    "calls.speaker.business": "Agent",
    "calls.speaker.customer": "Kunde",
    # Asking a customer whether the business may call them (F7)
    "calls.permission.request": "Dürfen wir Sie über WhatsApp anrufen, um Ihnen bei Ihrem Anliegen zu helfen?",
    "calls.permission.accepted": "Hat zugestimmt, über WhatsApp angerufen zu werden (7 Tage)",
    "calls.permission.accepted_always": "Hat zugestimmt, über WhatsApp angerufen zu werden (immer)",
    "calls.permission.accepted_by_calling": "Hat mit dem Anruf einen Rückruf für 7 Tage erlaubt",
    "calls.permission.rejected": "Möchte nicht über WhatsApp angerufen werden",
    # A call nobody answered (F7): what the customer reads, and the label
    # that marks the conversation to call back
    "calls.missed.reply": "Hallo! Wir haben deinen Anruf gesehen, konnten aber nicht rangehen. Wir rufen dich in ein paar Minuten zurück.",
    "calls.missed.label": "verpasster-anruf",
}
