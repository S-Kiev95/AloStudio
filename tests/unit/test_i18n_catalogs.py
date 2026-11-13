"""Backend texts in the recipient's language (F13)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.i18n import (
    CATALOGS,
    DEFAULT_LOCALE,
    LOCALES,
    has_locale,
    mail_text,
    normalize_locale,
    placeholders,
    t,
    user_locale,
)
from app.domains.notifications.push import _push_payload


@pytest.mark.parametrize("locale", [loc for loc in LOCALES if loc != DEFAULT_LOCALE])
def test_every_language_has_the_spanish_keys_and_placeholders(locale: str) -> None:
    source = CATALOGS[DEFAULT_LOCALE]
    catalog = CATALOGS[locale]
    assert set(catalog) == set(source)
    for key, text in source.items():
        assert placeholders(catalog[key]) == placeholders(text), key


def test_locale_comes_from_the_profile_and_falls_back_to_spanish() -> None:
    assert user_locale(SimpleNamespace(ui_settings={"locale": "pt"})) == "pt"
    assert user_locale(SimpleNamespace(ui_settings={"locale": "xx"})) == "es"
    assert user_locale(SimpleNamespace(ui_settings={})) == "es"
    assert user_locale(SimpleNamespace(ui_settings=None)) == "es"
    assert user_locale(None) == "es"
    assert has_locale(SimpleNamespace(ui_settings={"locale": "ja"}))
    assert not has_locale(SimpleNamespace(ui_settings={}))
    assert normalize_locale("pt-BR") == "pt"
    assert normalize_locale("en_US") == "en"


def test_t_fills_values_and_falls_back() -> None:
    assert t("en", "push.body", n=7) == "Conversation #7"
    assert t("es", "push.body", n=7) == "Conversación #7"
    assert t("zz", "push.body", n=7) == "Conversación #7"
    assert t("en", "no.such.key") == "no.such.key"


def test_spanish_mail_keeps_its_wording() -> None:
    body = mail_text("es", name="Ana", body=t("es", "reset.body", link="https://x/r"))
    assert body.startswith("Hola Ana,\n\nRecibimos un pedido")
    assert "    https://x/r\n" in body
    assert body.endswith("— AloStudio\n")


def test_push_payload_in_the_recipients_language() -> None:
    notification = SimpleNamespace(notification_type=0, account_id=1)
    conversation = SimpleNamespace(display_id=42, account_id=1)
    import json

    en = json.loads(_push_payload(notification, conversation, "en"))  # type: ignore[arg-type]
    es = json.loads(_push_payload(notification, conversation))  # type: ignore[arg-type]
    assert en["body"] == "Conversation #42"
    assert es["body"] == "Conversación #42"
    assert en["title"] != es["title"]


def test_a_crm_task_notification_points_to_the_task_list() -> None:
    import json

    from app.domains.notifications.mailer import build_notification_email

    notification = SimpleNamespace(
        notification_type=10,
        account_id=7,
        primary_actor_type="CrmActivity",
        meta={"title": "Mandar presupuesto"},
    )
    push = json.loads(_push_payload(notification, None, "en"))  # type: ignore[arg-type]
    assert push == {
        "title": "Task due",
        "body": "Mandar presupuesto",
        "url": push["url"],
    }
    assert push["url"].endswith("/accounts/7/tasks")

    user = SimpleNamespace(name="Ana", email="ana@x.test", ui_settings={})
    mail = build_notification_email(
        notification=notification,  # type: ignore[arg-type]
        user=user,  # type: ignore[arg-type]
        conversation=None,
    )
    assert mail["Subject"] == 'La tarea "Mandar presupuesto" venció'
    assert "/accounts/7/tasks" in mail.get_content()
