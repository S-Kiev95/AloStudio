# Agente de IA: equipo, clientes por chat y llamadas

Rama `feat/agente-ia` (agente A). Pedido del dueño el 2026-11-17, a partir
de la comparación con respond.io (F17, fila 12) y del paso 3 de F7.

## Qué es

Un solo "cerebro" con tres caras:

1. **Asistente del equipo** (ya existe en el menú "Agente", hoy solo
   publicaciones): ayuda a cada usuario con lo que su rol le permite en la
   cuenta. Un administrador puede todo lo de la cuenta; un agente solo lo
   de sus bandejas, como en el resto del panel.
2. **Agente que atiende clientes por chat** (WhatsApp, Instagram,
   Messenger, chat web...): responde con el conocimiento de la cuenta,
   recomienda productos, agenda en la Agenda, carga datos en el CRM,
   califica y pasa la conversación a una persona cuando hace falta.
3. **Agente de voz** para las llamadas de WhatsApp: lo mismo que el 2,
   hablando, en tiempo real.

Las tres usan las mismas instrucciones de la cuenta, el mismo conocimiento
y las mismas herramientas (las del MCP), cada una con su lista de qué puede
usar.

## Decisiones del dueño (2026-11-17)

- **Texto:** arranca con OpenAI (ya configurado) detrás de un adaptador;
  se suma Claude (Anthropic) y se comparan a ciegas con conversaciones
  reales antes de elegir.
- **Voz:** prueba a ciegas de tres opciones (OpenAI en tiempo real, Gemini
  Live y una voz argentina) con gente de acá; se elige por acento,
  naturalidad y costo.
- **Reparto:** el agente A hace las tres caras, incluido el paso 3 de F7
  (que era del agente B). Del código de llamadas de B se toca solo un
  enganche chico, anotado en `PENDIENTES-POR-FASE.md`.
- **Orden:** base y permisos primero; después el asistente del equipo; el
  agente de clientes en modo sombra y luego en vivo; la voz al final.

## Cómo se arma (y por qué)

### Texto: sin framework externo

AloStudio ya tiene su propio "harness" en `app/domains/agent/service.py`:
el bucle que llama al modelo, corre las herramientas del MCP dentro del
backend como el usuario, pide confirmación antes de escribir y registra el
costo (F6 / créditos de F2). Se amplía eso en vez de sumar un framework:

- Los permisos, el aislamiento entre cuentas y el cobro en créditos son lo
  delicado, y quedan en nuestro código, probados, en un solo lugar.
- Las herramientas ya existen (unas 95 en el MCP) y el bucle ya las usa.
- Cambiar de proveedor es un adaptador chico (OpenAI hoy, Anthropic
  después), no reescribir el agente.

Descartados: Claude Agent SDK (pensado para agentes de código con archivos
y terminal, corre un proceso aparte por agente: no sirve para miles de
conversaciones en un backend con varias cuentas); frameworks genéricos
(LangGraph y similares): suman capas sin resolver lo nuestro.

### Voz: Pipecat

La voz sí usa un framework: [Pipecat](https://docs.pipecat.ai/pipecat/features/whatsapp)
(Python como el backend, código abierto, corre en nuestro servidor). Se
ocupa de lo difícil del audio: la conexión WebRTC con WhatsApp, detectar
cuándo el cliente terminó de hablar, cortar al agente si lo interrumpen, y
conectar cualquier modelo de voz (OpenAI, Gemini, o escuchar → pensar →
hablar con proveedores separados).

- El backend ya recibe la llamada (`connect` con la oferta WebRTC de Meta,
  F7). Si la atiende la IA, le pasa la oferta al proceso de voz, que arma
  la respuesta, y el backend la manda a Meta con el mismo `pre_accept` /
  `accept` que usa el navegador de un agente.
- Las herramientas que pide el modelo de voz las corre el backend, igual
  que en el chat.

Descartados:

- **LiveKit:** su conector de WhatsApp funciona solo en LiveKit Cloud (no
  se puede autohospedar) y está en beta con acceso pedido.
- **SIP directo a OpenAI:** Meta deja usar SIP o la API de llamadas por
  número, no las dos. Pasar un número a SIP rompe lo que hizo B (atender
  desde el navegador, grabar, llamar desde la conversación).

Costo de audio de referencia (por millón de tokens, entrada / salida):
`gpt-realtime-2.1` US$ 32 / 64, `gpt-realtime-2.1-mini` US$ 10 / 20
([precios de OpenAI](https://developers.openai.com/api/docs/pricing));
`gemini-3.8-live` US$ 3 / 12 ([Gemini](https://aistudio.google.com/docs/pricing)).
Llamar a un cliente lo cobra Meta aparte; atender es gratis.

## Seguridad

- **Cada cara tiene su lista de herramientas.** El asistente del equipo usa
  las del MCP según el rol. El agente de clientes **no** usa las del MCP
  directamente: usa herramientas propias atadas a la conversación en curso
  (no reciben ids de contactos ni de conversaciones; los pone el sistema),
  así un cliente que escribe "mostrame los datos de otro cliente" no tiene
  con qué hacerlo.
- **Permisos en el código, no en las instrucciones.** Lo que un rol no
  puede hacer no se le ofrece al modelo y, si igual lo pide, la herramienta
  lo rechaza.
- **Límites:** pasos por respuesta, respuestas por conversación por hora,
  tope de gasto del plan y créditos; sin créditos el agente pasa la
  conversación a una persona.
- **Registro:** cada acción del agente queda como nota en la conversación
  ("IA: agendó una cita para el martes 10:00") y cada corrida con sus
  herramientas, tokens y costo.
- **Modo sombra antes de soltarlo:** el agente propone la respuesta y una
  persona la manda; se mide cuántas manda sin cambios.

## Pasos

### Paso 1. Base y permisos — asistente del equipo según el rol

- Las herramientas del MCP respetan al usuario cuando el agente actúa en su
  nombre: un agente (rol no administrador) solo ve y toca conversaciones y
  mensajes de las bandejas de las que es miembro (o de sus equipos), como
  `conversations/permission.py`. Las herramientas que la API reserva a
  administradores no se le ofrecen.
- El asistente del equipo pasa de publicaciones a todas las herramientas
  que el rol permite; toda escritura se confirma en la tarjeta del chat.
- **Terminado cuando:** tests de que un agente no lista, no lee ni escribe
  en conversaciones de bandejas ajenas; un administrador sí; las
  herramientas solo de administradores no aparecen para un agente; los
  tokens del MCP (sin usuario) siguen igual.

**Hecho (2026-11-17):**

- `MCPContext.user_scoped`: el asistente y las apps OAuth actúan como la
  persona y ven lo que su rol ve en el panel. Las herramientas lo aplican
  con `app/mcp/permissions.py` (`ensure_conversation_visible`,
  `visible_conversations`, `ensure_inbox_visible`, `visible_inboxes`), que
  reusan `conversations/permission.py` (se sumó `can_view_inbox`). Los
  tokens "API y MCP" no cambian.
- Cada herramienta declara en `@requires(...)` si el panel la reserva a
  administradores (`panel_admin=True`, como su ruta REST con
  `require_admin`) y si una herramienta `admin` solo lee (`reads=True`).
  Una herramienta sin `@requires` cuenta como escritura de administradores.
  Con `user_scoped`, la herramienta misma rechaza a un agente (también si
  la llama una app OAuth).
- El asistente ofrece todas las herramientas que el rol permite (unas 100
  para un administrador, ~48.000 caracteres de definiciones por llamada:
  medir el costo; si pesa, elegir grupos de herramientas por pedido). Toda
  escritura espera la confirmación; solo las de publicaciones se ensayan
  antes (lo demás manda mensajes, llama a Meta o avisa al panel).
- Tarjeta de confirmación genérica: los datos de la acción con sus nombres
  y los ids como nombres (solo de lo que el usuario puede ver), en los 7
  idiomas; los estados del chat también pasaron a los 7 idiomas.
- Arreglos que salieron de la revisión: macros sobre conversaciones de
  bandejas ajenas; `list_inboxes` y las plantillas de WhatsApp respetan las
  bandejas; `set_ai_mode` (apaga las automatizaciones) queda para
  administradores; asignar a una persona o equipo que no existe da error
  (el servicio lo ignoraba o borraba el equipo); `search_messages`
  devuelve el id interno de la conversación (y el número en
  `conversation_display_id`); confirmar ya no da error 500 cuando el
  servicio confirma la base por su cuenta (adjuntos de Instagram, reintento
  de publicaciones).
- Igual que la API REST, sin cambios: los reportes y la CSAT no se filtran
  por bandeja para los agentes (decisión de producto, a revisar).
- Tests: `tests/integration/test_agent_roles.py`, `test_agent_chat.py`,
  `test_oauth_apps.py` y los del MCP; frontend `components/agent`.

### Paso 2. Agente de clientes por chat

- Nuevo tipo de bot "IA de AloStudio" (`agent_bots.bot_type = 1`) que se
  conecta a bandejas desde Ajustes → Bots, como los bots por webhook de
  Chatwoot. Configuración: nombre, instrucciones y tono, cuándo responde
  (siempre, fuera de horario, cuando nadie atiende), qué puede hacer y
  cuándo pasa a una persona.
- Conocimiento: Centro de ayuda (búsqueda por significado), productos y
  catálogo, horarios y Agenda.
- Herramientas de cliente: buscar en el conocimiento, ver productos,
  ver horarios libres y agendar, guardar datos del contacto, poner etapa o
  etiqueta, crear oportunidad, pasar a una persona (`bot_handoff` + nota
  con resumen).
- Corre en el worker (no frena el webhook). Convive con el Business Agent
  de Meta: si Meta tiene el control de la conversación, no responde.
- Modo sombra primero, después en vivo. Adaptador de Anthropic y
  comparación a ciegas OpenAI / Claude.

### Paso 3. Agente de voz

- Proceso de voz con Pipecat; cada bandeja elige cuándo atiende la IA
  (siempre, cuando nadie está libre, fuera de horario).
- Mismo cerebro y herramientas; la transcripción queda en la conversación.
- Pasar a una persona, primera versión: "te llamamos en unos minutos",
  conversación asignada con el resumen, y la persona devuelve la llamada
  (permiso de Meta de 7 días al que llamó).
- Prueba a ciegas de las tres voces. Costo por minuto a créditos.
- Servidor: puertos UDP abiertos para el audio y, si hace falta, TURN.

### Paso 4. Traspaso en vivo y extras

- Pasar la llamada en curso a una persona sin cortar (puente de audio).
- Sugerencias y resúmenes en la Bandeja (F17, fila 1), con el mismo núcleo.

## Planes y créditos (multitenant, F2)

Todo consume créditos de IA. Propuesta a cerrar con el dueño al terminar
el paso 2: agente de clientes por chat en Pro y Max, voz en Max.
