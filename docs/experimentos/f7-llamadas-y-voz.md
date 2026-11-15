# F7. Llamadas y voz: lo que hay (2026-11-14)

Investigación antes de empezar. Fuentes: documentación de Meta (Calling API,
precios, Live Video API, webhooks de Instagram) y la consulta al número de
CTC con su propio token (solo lectura).

## 1. Llamadas de WhatsApp (Business Calling API)

### Requisitos y estado de CTC

| Requisito | CTC (Instituto CTC Salto) |
|---|---|
| Número en Cloud API, no en la app de WhatsApp Business | Sí (`CLOUD_API`) |
| Límite diario de 2.000 destinatarios o más | Sí (`TIER_2K`), justo en el mínimo |
| Calidad del número | Verde |
| Permiso `whatsapp_business_messaging` | Sí |
| Llamadas activadas en el número | **No** (`status: NOT_SET`) |
| Webhook `calls` suscripto en la app | **No** (hay que agregarlo) |

- **Recibir llamadas** (el cliente llama): disponible en todos los países de
  Cloud API. **Gratis.**
- **Hacer llamadas** (el negocio llama): disponible salvo si el número del
  negocio es de EE. UU., Canadá, Egipto, Vietnam o Nigeria. Uruguay puede.
  El cliente tiene que dar permiso antes: se le manda un pedido de permiso
  (se cobra como mensaje), como máximo 1 por día y 2 por semana por
  cliente. Si no atiende 4 llamadas seguidas, el permiso se pierde solo.
  Meta también restringe a los negocios con poca tasa de atención o con
  quejas.

### Costo

- Llamadas que hace el cliente: gratis. Que llame también abre o renueva la
  ventana de 24 horas, se atienda o no.
- Llamadas que hace el negocio: por minuto, cobradas en tramos de 6
  segundos, según el país del número llamado y con descuento por volumen
  mensual. La tarifa de Uruguay está en la tabla en USD de Meta (cambia el
  1 de enero, abril, julio y octubre); revisarla antes de usarlas. Como
  referencia, los revendedores hablan de centavos de dólar por minuto
  (hasta unos 5 centavos).
- Grabación y transcripción de Meta: gratis por ahora.
- Entra en F6 (gastos por uso) como "llamadas, por minuto".

### Cómo funciona por dentro

- Meta avisa por el webhook `calls` (`connect`, con la oferta SDP del
  cliente) y AloStudio tiene entre 30 y 60 segundos para atender
  (`pre_accept` y `accept` con la respuesta SDP) o rechazar. Al terminar
  llega `terminate` con estado y duración.
- **El audio no pasa por Meta como un archivo: es WebRTC.** Quien atiende
  tiene que tener una conexión WebRTC propia. Para un agente humano eso es
  el navegador: el backend le pasa la oferta al navegador del agente por
  el canal en tiempo real que ya existe, el navegador arma la respuesta y
  el backend la manda a Meta. No hace falta un servidor de audio propio;
  quizá un servidor TURN si algún agente está detrás de una red muy
  cerrada.
- También se puede por SIP, pidiéndoselo a Meta, para conectar una central
  telefónica o un proveedor de voz.

### Propuesta en pasos

1. **Recibir llamadas en la Bandeja (gratis).** Activar las llamadas en el
   número y su horario desde Ajustes de la bandeja; cuando un cliente
   llama, suena en el panel de los agentes de esa bandeja, el primero que
   atiende habla desde el navegador (micrófono y auriculares), y la
   llamada queda en la conversación (quién atendió, duración, perdida).
   Fuera de horario, Meta le ofrece al cliente pedir que lo llamen.
2. **Llamar desde la conversación.** Botón de llamar; si el cliente todavía
   no dio permiso, se le manda el pedido. Tiene costo por minuto: mostrar
   el gasto en F6.
3. **Agente de voz** (ver punto 3).

Toca archivos del agente A: el webhook de WhatsApp
(`app/domains/whatsapp/incoming_cloud.py`) y `components/whatsapp/`.
Coordinar antes de empezar el paso 1.

## 2. Lives

- **Facebook:** la Live Video API permite transmitir en vivo en la Página
  desde un programa (RTMPS), leer y responder comentarios y hacer
  encuestas. Pide `pages_manage_posts` y `pages_read_engagement` con
  revisión de la app, y la Página tiene que tener al menos 100 seguidores
  y la cuenta 60 días.
- **Instagram:** no se puede transmitir desde otra app. Sí se pueden leer
  los comentarios mientras el vivo está en el aire (webhook
  `live_comments`, con acceso avanzado y la cuenta pública) y responder
  una vez por privado a quien comentó, dentro de los 7 días.
- Lo útil para CTC sería lo de Instagram: que los comentarios de un vivo
  caigan en la Bandeja y se puedan contestar por privado. Es un pedido más
  al permiso de comentarios que ya está en revisión.

## 3. Agentes de voz (después)

- Camino más corto: el conector de WhatsApp de LiveKit (en beta). AloStudio
  recibe la llamada, le pasa la oferta a LiveKit y LiveKit atiende con un
  agente que escucha, piensa con las herramientas del MCP y habla. Si hace
  falta una persona, pasa la llamada a la Bandeja.
- Voz a texto y texto a voz con español rioplatense (voseo, "sh"): no hay
  comparaciones publicadas confiables. Hay que probar a ciegas con gente de
  acá: ElevenLabs (voces argentinas), Deepgram Nova-3 para escuchar, y los
  modelos de voz en tiempo real de OpenAI.
- Costo: el proveedor de voz cobra por minuto, aparte de Meta. Entra en F6.
