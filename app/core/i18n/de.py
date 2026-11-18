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
    # Why a conversation closed (F17): the default categories, and the
    # title of the private note a closing leaves
    "closing.default.answered": "Frage beantwortet",
    "closing.default.enrolled": "Angemeldet",
    "closing.default.not_interested": "Kein Interesse",
    "closing.default.no_reply": "Kunde hat nicht geantwortet",
    "closing.default.spam": "Spam oder falsche Nummer",
    "closing.note_title": "Abschlussnotiz",
    # Contact lifecycle (F17): the default stages, and the line a move
    # leaves in the conversation
    "lifecycle.default.new_lead.name": "Neuer Lead",
    "lifecycle.default.new_lead.description": "Hat zum ersten Mal geschrieben.",
    "lifecycle.default.hot_lead.name": "Heißer Lead",
    "lifecycle.default.hot_lead.description": "Will weitermachen.",
    "lifecycle.default.payment.name": "Zahlung",
    "lifecycle.default.payment.description": "Zahlt gerade oder bald.",
    "lifecycle.default.customer.name": "Kunde",
    "lifecycle.default.customer.description": "Hat gekauft.",
    "lifecycle.default.cold_lead.name": "Kalter Lead",
    "lifecycle.default.cold_lead.description": "Antwortet nicht mehr oder hat kein Interesse mehr.",
    "lifecycle.activity": "{name} hat den Kontakt auf {stage} gesetzt",
    "lifecycle.activity_cleared": "{name} hat die Phase des Kontakts entfernt",
    "lifecycle.someone": "Jemand",
    "agent.tool.read_done": "Hat das Konto abgefragt",
    "agent.tool.write_done": "Erledigt",
    "agent.tool.failed": "Konnte nicht abgeschlossen werden",
    "agent.pending.title": "Bestätige diese Aktion",
    "agent.pending.confirm": "Bestätigen",
    "agent.yes": "Ja",
    "agent.no": "Nein",
    "agent.args.conversation_id": "Unterhaltung",
    "agent.args.contact_id": "Kontakt",
    "agent.args.inbox_id": "Posteingang",
    "agent.args.team_id": "Team",
    "agent.args.assignee_id": "Zugewiesen an",
    "agent.args.agent_id": "Agent",
    "agent.args.owner_id": "Verantwortlich",
    "agent.args.content": "Nachricht",
    "agent.args.message": "Nachricht",
    "agent.args.private": "Private Notiz",
    "agent.args.status": "Status",
    "agent.args.priority": "Priorität",
    "agent.args.labels": "Labels",
    "agent.args.name": "Name",
    "agent.args.title": "Titel",
    "agent.args.description": "Beschreibung",
    "agent.args.notes": "Notizen",
    "agent.args.email": "E-Mail",
    "agent.args.phone_number": "Telefon",
    "agent.args.value": "Wert",
    "agent.args.currency": "Währung",
    "agent.args.starts_at": "Von",
    "agent.args.ends_at": "Bis",
    "agent.args.due_at": "Fällig",
    "agent.args.scheduled_at": "Datum",
    "agent.args.product_id": "Produkt",
    "agent.args.product_ids": "Produkte",
    "agent.args.stage_id": "Phase",
    "agent.args.active": "Aktiv",
    "agent.args.enabled": "Aktiviert",
    "agent.status.pending": "Wartet auf deine Bestätigung",
    "agent.status.invalid": "Der Vorschlag hat die Prüfung nicht bestanden",
    "agent.status.rejected": "Du hast den Vorschlag verworfen",
    "agent.tool.list_publication_channels.done": "Hat deine Kanäle abgefragt",
    "agent.tool.list_publication_channels.failed": "Konnte deine Kanäle nicht abfragen",
    "agent.tool.list_media.done": "Hat deine Mediathek durchsucht",
    "agent.tool.list_media.failed": "Konnte die Mediathek nicht durchsuchen",
    "agent.tool.list_publications.done": "Hat deinen Kalender geprüft",
    "agent.tool.list_publications.failed": "Konnte den Kalender nicht prüfen",
    "agent.tool.get_publishing_analytics.done": "Hat die Statistiken abgefragt",
    "agent.tool.get_publishing_analytics.failed": "Konnte die Statistiken nicht abfragen",
    "agent.tool.create_publication.done": "Hat den Beitrag geplant",
    "agent.tool.create_publication.failed": "Der Beitrag konnte nicht geplant werden",
    "agent.tool.cancel_publication.done": "Hat den Beitrag gelöscht",
    "agent.tool.cancel_publication.failed": "Der Beitrag konnte nicht gelöscht werden",
    "agent.pending.cancel_publication.title": "Beitrag löschen",
    "agent.pending.cancel_publication.confirm": "Löschen",
    "agent.pending.create_publication.title": "Beitrag planen",
    "agent.pending.create_publication.confirm": "Planen",
    "agent.pending.create_publication.confirm_now": "Jetzt veröffentlichen",
    "agent.args.macro_id": "Makro",
    "agent.args.conversation_ids": "Unterhaltungen",
}
