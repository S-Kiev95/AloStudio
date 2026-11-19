"""The help assistant's knowledge: real screens, a well-formed help, and the
check that catches menus the panel does not have."""

from __future__ import annotations

import pathlib

import pytest

from app.domains.help_assistant import knowledge
from app.domains.help_assistant.screens import SCREENS
from app.domains.help_assistant.service import screen_for

PAGES = (
    pathlib.Path(__file__).resolve().parents[2] / "frontend" / "app" / "accounts" / "[accountId]"
)


def _routes() -> set[str]:
    """Every page under /accounts/[accountId]/, as its URL path. Route
    groups like ``(crm)`` do not show in the URL."""
    routes = set()
    for page in PAGES.rglob("page.tsx"):
        parts = [p for p in page.parent.relative_to(PAGES).parts if not p.startswith("(")]
        routes.add("/".join(parts))
    return routes


@pytest.mark.parametrize("key", sorted(SCREENS))
def test_every_screen_is_a_real_page(key):
    assert SCREENS[key].path in _routes(), f"{key} → /{SCREENS[key].path} is not a page"


def test_the_help_parses_and_names_only_real_screens():
    sections = knowledge.sections()
    assert len(sections) >= 30
    assert all(s.screens and s.text for s in sections)
    prompt = knowledge.system_prompt()
    assert all(f"{key}: {screen.label}" in prompt for key, screen in SCREENS.items())


def test_the_answer_can_only_name_real_screens():
    schema = knowledge.response_schema()
    answer = schema["anyOf"][1]["properties"]
    assert set(answer["pantalla"]["enum"]) == {*SCREENS, knowledge.NO_SCREEN}
    assert schema["anyOf"][0]["properties"] == {"sabe": {"const": False}}


def test_the_prefix_is_always_the_same():
    """llama-server reuses it only if it does not change between questions."""
    assert knowledge.prefix_messages() == knowledge.prefix_messages()
    assert knowledge.prefix_messages()[0]["role"] == "system"


@pytest.mark.parametrize(
    ("answer", "invented"),
    [
        ('Entrá a Ajustes → Notas de cierre y marcá "Obligatorio".', []),
        ("Andá a Estadísticas → Gastos.", []),
        ("Ajustes → Bandejas de entrada, entrando a la de WhatsApp.", []),
        (
            "Andá a Ajustes → Exportaciones y bajá el archivo.",
            ["Ajustes → Exportaciones y bajá el archivo"],
        ),
        ("En CRM → Reportes de ventas.", ["CRM → Reportes de ventas"]),
        ("Tocá Respuestas rápidas → Nueva respuesta.", ["… → Nueva respuesta"]),
        ("Andá a Estadísticas → Notificaciones → Reportes.", ["Estadísticas → Notificaciones"]),
        ("Entrá a Ajustes → Instalación → Llamadas y prendelo.", []),
        ("En Campañas → Nueva campaña elegí WhatsApp.", []),
        ("Andá a Reportes → Motivos de cierre.", []),
    ],
)
def test_menus_the_panel_does_not_have_are_caught(answer, invented):
    assert knowledge.invented_menus(answer) == invented


@pytest.mark.parametrize(
    ("page", "key"),
    [
        ("/accounts/1/settings/lifecycle", "ajustes_etapas"),
        ("/accounts/1/conversations/42", "bandeja"),
        ("/accounts/1/publications/analytics/costs", "gastos"),
        ("/accounts/1/publications/analytics", "estadisticas"),
        ("/accounts/1", "inicio"),
        ("/accounts/1/algo-que-no-existe", None),
        (None, None),
    ],
)
def test_the_page_names_the_screen(page, key):
    assert screen_for(page) == key


@pytest.mark.parametrize(
    ("answer", "invented"),
    [
        ('Tocá "Nueva cita" en CRM → Agenda.', []),
        ('En Ajustes → Mi perfil tocá "Conectar Google Calendar".', []),
        (
            'Activá "Reportes" y elegí "Enviar por correo todos los lunes".',
            ["Enviar por correo todos los lunes"],
        ),
    ],
)
def test_quoted_names_must_be_in_the_help(answer, invented):
    assert knowledge.invented_quotes(answer) == invented
