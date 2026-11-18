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

**Decisiones del dueño (2026-11-17)** sobre quién atiende cada
conversación, ahora que hay tres: el agente de Meta (Business Agent, en
los números que lo tienen, como CTC), la IA de AloStudio y las personas:

- **Responsable de derivación** (cuando el agente de Meta o la IA de
  AloStudio pasan una conversación): lo eligen los administradores de la
  cuenta (el dueño del tenant) o el superadmin, por chat, por etiqueta o
  para toda la cuenta. Hoy CTC deriva todo a Sofía; con una etiqueta
  "Admin" asignada a Yamila, esas derivaciones irían a Yamila. La IA de
  AloStudio es una opción más si el plan la incluye.
- Cuando la IA de AloStudio termina o no puede seguir, pasa a **una
  persona** (el responsable que toque, sin contar la IA), con una nota que
  resume lo hablado. Al resolver, vuelve al agente de Meta, como hoy.
- En bandejas sin agente de Meta, **cada bandeja elige** cuándo atiende la
  IA: siempre primero, solo fuera de horario o solo cuando nadie del
  equipo está libre. Si una persona contesta, la IA se corre.
- **Modo sombra:** la respuesta propuesta aparece arriba de la caja de
  texto con "Usar" (la pone en la caja para editarla y mandarla) y
  "Descartar"; se mide cuántas se usan tal cual.

**2a. Responsable de derivación** (sirve también sin la IA):

- Niveles, gana el más específico: **chat** (el cliente: vale para sus
  próximas derivaciones) → **etiqueta** (reglas en orden; gana la primera
  etiqueta de la conversación que tenga regla) → **bandeja** (el
  "Responsable por defecto" que ya existe) → **cuenta** → nadie (le llega
  el aviso a todo el equipo de la bandeja).
- Destino: una persona de la cuenta, o la IA de AloStudio (solo si hay un
  agente de IA configurado y, en multitenant, si el plan lo incluye).
- Se aplica en `bot_handoff`, el único punto por el que pasan las
  derivaciones (del agente de Meta y de la IA). Junto a la línea de
  asignación de siempre ("Asignada a Yamila") deja el motivo: "Derivada por
  la etiqueta Admin", "al responsable de este chat" o "al responsable
  general". El nivel bandeja no agrega nota (se comporta como antes).
- Ajustes → Derivación (cuenta y etiquetas), el panel de la bandeja (ya
  existe) y el panel de la conversación (por chat). Solo administradores.

Hecho (2026-11-18):
- Tabla `handoff_rules` (alcance `account` / `label` / `contact`, una
  persona o `to_ai`, `position` para el orden de las etiquetas; índices
  únicos parciales), dominio `app/domains/handoff` y API
  `/api/v1/accounts/{id}/handoff` (GET, PUT `/account`, PUT `/labels`,
  GET/PUT `/contacts/{contact_id}`), solo administradores; errores con
  código `handoff.<motivo>`.
- Una regla que no sirve (la persona dejó la cuenta, la IA no está o es la
  IA la que deriva) pasa al nivel siguiente. Las etiquetas se comparan por
  nombre, sin distinguir mayúsculas.
- La IA todavía no se puede elegir: aparece cuando exista un bot de tipo 1
  (2b).
- Frontend: Ajustes → Derivación (reglas por etiqueta en orden, con subir y
  bajar, y el responsable general) y "Derivación de este chat" en el panel
  del contacto, solo para administradores. Textos en los 7 idiomas.
- Tests: `tests/integration/test_handoff_rules.py`,
  `frontend/components/handoff/handoff-settings-view.test.tsx`.

**2b. La IA de AloStudio atiende:**

- Nuevo tipo de bot "IA de AloStudio" (`agent_bots.bot_type = 1`) que se
  conecta a bandejas desde Ajustes → Bots, como los bots por webhook de
  Chatwoot. Configuración: nombre, instrucciones y tono, cuándo responde
  (siempre, fuera de horario, cuando nadie atiende), qué puede hacer y
  cuándo pasa a una persona.
- Quién tiene la conversación, en un solo lugar: el agente de Meta
  (`thread_control.owner = ai_agent`, AloStudio solo lee), la IA de
  AloStudio (conversación `pending` con el bot asignado) o una persona
  (`open`). Las puertas de Meta que ya existen (deriva, una persona toma o
  contesta, resolver la devuelve) no cambian.
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

Por partes:

- **2b.1** El bot de IA (Ajustes → Bots: instrucciones, modo sombra o en
  vivo, cuándo responde) y su motor en el worker. En vivo, una conversación
  que la IA toma queda `pending` con el bot asignado (la asignación
  automática no la toca) y se abre cuando la IA deriva o contesta una
  persona. En sombra no toma nada: deja la respuesta propuesta arriba de la
  caja de texto (Usar / Descartar) y se mide cuántas salen sin cambios.
  Herramientas: Centro de ayuda, productos, pasar a una persona con resumen.
  La IA como destino de las derivaciones de Meta.
- **2b.2** Agenda (horarios libres y agendar) y CRM (datos del contacto,
  etapa, etiqueta, oportunidad).
- **2b.3** Adaptador de Anthropic y comparación a ciegas.

Hecho 2b.1 (2026-11-18):
- Bot de tipo IA (`bot_type = 1`, en la API `"ai"`) con `bot_config`:
  `instructions`, `mode` (`shadow` / `live`) y `respond_when` (`always`,
  `out_of_hours` con el horario de la bandeja, `nobody_available`: nadie
  de la bandeja "En línea"; la disponibilidad la marca cada persona, no
  hay presencia automática). Ajustes → Bots lo crea; cada bandeja elige
  su bot en Ajustes → Bandejas → Bot (`GET /inboxes/{id}/agent_bot`, que
  faltaba).
- En vivo, una conversación nueva (o una resuelta que vuelve a escribir y
  no tiene persona asignada) queda `pending` con el bot como
  `assignee_agent_bot_id`; la asignación automática salta las `pending`.
  En bandejas con el agente de Meta la IA no toma nada sola: solo lo que
  una regla de derivación le da cuando Meta deriva (`bot_handoff` con
  `allow_ai`).
- Cada mensaje del cliente encola una corrida en el worker
  (`ai_reply_task`, 4 s después: una ráfaga recibe una respuesta). La
  corrida usa herramientas propias atadas a la conversación (Centro de
  ayuda, productos, pasar a una persona), responde como el bot o deriva
  con un resumen en nota privada. Si el modelo falla, se pasa al equipo.
  Tope de 20 corridas por conversación por hora. Una persona que
  responde la saca a la IA (queda `open`). Respeta `ai_mode` (una IA
  externa por MCP).
- Modo sombra: la respuesta queda en `ai_replies` como sugerencia arriba
  de la caja de texto (Usar / Descartar); al mandarla viaja
  `content_attributes.ai_reply_id` y queda `sent` (tal cual) o `edited`;
  si el equipo manda otra cosa, `superseded`.
- Nadie queda esperando a la IA: suelta la conversación (queda `open`)
  si Meta retoma el hilo, si se asigna a una persona, si el bot sale de
  la bandeja, se borra o pasa a sombra; si la corrida no se puede encolar
  o falla, se deriva al equipo. Quien responde se queda con la
  conversación (la asignación automática no se la da a otro). La corrida
  se encola después del commit y, al volver del modelo, se descarta si
  mientras tanto el cliente escribió o una persona respondió. Sin la
  clave de OpenAI no toma nada; tampoco las conversaciones que inicia una
  persona desde el panel.
- Cada corrida queda en `ai_replies` (modo, estado, herramientas usadas);
  el costo va a los créditos con el propósito `ai_agent`.
- Tests: `tests/integration/test_ai_agent.py`;
  `frontend/components/conversations/ai-suggestion.test.tsx`,
  `components/settings/inboxes/inbox-bot-panel.test.tsx`,
  `components/settings/agent-bots/agent-bots-view.test.tsx`.

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
