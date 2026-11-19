"""Every screen the help assistant may send someone to.

The model can only answer with one of these keys (the response grammar lists
them), and ``tests/unit/test_help_screens.py`` checks that each ``path`` is a
real page of the panel, so it never points to a screen that does not exist.
``label`` is what the menus say, in the order you click them.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Screen:
    label: str
    # Under ``/accounts/{account_id}/``; "" is the account's home.
    path: str
    # Only administrators can open or change it.
    admin: bool = False


SCREENS: dict[str, Screen] = {
    "inicio": Screen("Inicio", ""),
    "calendario": Screen("Calendario", "publications"),
    "agente": Screen("Agente", "agent"),
    "estadisticas": Screen("Estadísticas", "publications/analytics"),
    "gastos": Screen("Estadísticas → Gastos", "publications/analytics/costs", admin=True),
    "medios": Screen("Medios", "publications/media"),
    "bandeja": Screen("Bandeja", "conversations"),
    "bandeja_reportes": Screen("Bandeja → Reportes", "conversations/reports"),
    "bandeja_canales": Screen("Bandeja → Canales", "conversations/channels"),
    "contactos": Screen("CRM → Contactos", "contacts"),
    "agenda": Screen("CRM → Agenda", "agenda"),
    "tareas": Screen("CRM → Tareas", "tasks"),
    "oportunidades": Screen("CRM → Oportunidades", "opportunities"),
    "empresas": Screen("CRM → Empresas", "companies"),
    "productos": Screen("CRM → Productos", "products"),
    "instagram": Screen("Instagram", "instagram"),
    "whatsapp": Screen("WhatsApp", "whatsapp"),
    "help_center": Screen("Help Center", "help-center"),
    "campanas": Screen("Campañas", "campaigns"),
    "reportes": Screen("Reportes", "reports"),
    "notificaciones": Screen("Notificaciones", "notifications"),
    "ajustes_agentes": Screen("Ajustes → Agentes", "settings/agents", admin=True),
    "ajustes_perfil": Screen("Ajustes → Mi perfil", "settings/profile"),
    "ajustes_seguridad": Screen("Ajustes → Seguridad", "settings/security"),
    "ajustes_notificaciones": Screen("Ajustes → Notificaciones", "settings/notifications"),
    "ajustes_etiquetas": Screen("Ajustes → Etiquetas", "settings/labels", admin=True),
    "ajustes_equipos": Screen("Ajustes → Equipos", "settings/teams", admin=True),
    "ajustes_bandejas": Screen("Ajustes → Bandejas de entrada", "settings/inboxes", admin=True),
    "ajustes_asignacion": Screen(
        "Ajustes → Políticas de asignación", "settings/assignment_policies", admin=True
    ),
    "ajustes_respuestas": Screen("Ajustes → Respuestas predefinidas", "settings/canned_responses"),
    "ajustes_macros": Screen("Ajustes → Macros", "settings/macros"),
    "ajustes_horarios": Screen(
        "Ajustes → Horarios laborales", "settings/working_hours", admin=True
    ),
    "ajustes_atributos": Screen(
        "Ajustes → Atributos personalizados", "settings/custom_attributes", admin=True
    ),
    "ajustes_automatizacion": Screen("Ajustes → Automatización", "settings/automation", admin=True),
    "ajustes_clasificacion": Screen("Ajustes → Clasificación", "settings/decisions", admin=True),
    "ajustes_notas_cierre": Screen(
        "Ajustes → Notas de cierre", "settings/closing_notes", admin=True
    ),
    "ajustes_conversions": Screen("Ajustes → Conversions API", "settings/conversions", admin=True),
    "ajustes_etapas": Screen("Ajustes → Etapas del contacto", "settings/lifecycle", admin=True),
    "ajustes_bots": Screen("Ajustes → Bots", "settings/agent_bots", admin=True),
    "ajustes_integraciones": Screen("Ajustes → Integraciones", "settings/integrations", admin=True),
    "ajustes_csat": Screen("Ajustes → CSAT", "settings/csat", admin=True),
    "ajustes_instalacion": Screen("Ajustes → Instalación", "settings/installation", admin=True),
}

__all__ = ["SCREENS", "Screen"]
