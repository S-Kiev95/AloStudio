# Pendientes por fase

Lista viva: qué falta de cada fase de `PLAN.fases-futuras.md`. Se actualiza
al cerrar cada trabajo. El detalle de cada fase está en ese plan; acá solo
el estado y lo que queda.

Última actualización: 2026-11-10.

| Fase | Estado |
|---|---|
| F1 Respaldos | Hecha en CTC |
| F2 Multitenant | Pasos 1 y 2 hechos en `feat/multitenant`; resto para más adelante |
| F3 Redes que faltan | Sin empezar |
| F4 Herramientas MCP | Sin empezar |
| F5 Plantillas de WhatsApp | Sin empezar |
| F6 Gastos por uso | Sin empezar |
| F7 Llamadas y voz | Sin empezar |
| F8 Búsqueda en conversaciones viejas | Sin empezar |
| F9 EmbeddingGemma | En develop, comparando en sombra con OpenAI |
| F10 Jev y Laya | Sin empezar |
| F11 CRM (Krayin) | Sin empezar |
| F12 Grafos | Sin empezar |
| F13 Multi-idioma | Sin empezar |
| F14 Foto del contacto | Sin empezar |
| F15 Canal de aviso por agente | Idea; esperando la opinión de los agentes de CTC |

---

## F1. Respaldos

- Confirmar en Healthchecks.io que el respaldo diario de las 03:30 llega
  en verde, y el 1 de diciembre la primera prueba de restauración
  automática.
- Develop no tiene respaldo de AloStudio (decisión del dueño: solo CTC).

## F2. Multitenant (rama `feat/multitenant`, nunca a `develop` ni `main`)

`main` es la instalación propia de CTC. Detalle en `PLAN.multitenant.md`
dentro de la rama.

- **Del lado de Meta (el dueño):** configuración de WhatsApp Embedded
  Signup (su ID va a `WHATSAPP_EMBEDDED_SIGNUP_CONFIG_ID`), webhook de la
  app en `/webhooks/whatsapp` con su token, y acceso como Tech Provider
  (verificación del negocio y acceso avanzado a los permisos de WhatsApp).
- **Servidor** para la instalación multitenant, con `MULTITENANT=true` y un
  superadministrador creado antes de abrir el registro.
- Al borrar una bandeja conectada por Embedded Signup, desuscribir la app
  de esa cuenta de WhatsApp Business.
- Captcha en el registro, si el límite por IP no alcanza.
- **Paso 3, facturación:** elegir proveedor de cobro, moneda, planes y sus
  límites (decisiones del dueño). El webhook de pagos no puede tirar
  excepciones.
- **Paso 4:** límites de uso por cuenta en el worker y la API.
- **Paso 5:** panel interno de cuentas, métricas por cliente, borrado y
  exportación de los datos de una cuenta.
- **Paso 6:** script para desplegar una instalación dedicada (Enterprise),
  como la de CTC.
- **Paso 7:** términos de servicio, política de privacidad y acuerdo de
  tratamiento de datos.
- **Para el lanzamiento:** elegir y pagar un plan al registrarse; entrar
  con Facebook, X y otros (Google ya existe: revisar que en multitenant
  cree la cuenta con el mismo flujo del registro).

## F3. Redes que faltan

- Iniciar los trámites de las apps de desarrollador (tardan semanas):
  YouTube, LinkedIn página de empresa y TikTok Business primero.
- Después: X (cobra por uso, entra con F6), Google Business Profile, Slack
  y Twitch.

## F4. Herramientas que le faltan al MCP

- Prioridad alta: `list_inboxes`, `list_agents`, `list_teams`,
  `create_contact`, `update_contact`, `create_conversation`, adjuntos y
  plantillas en `send_message`, `list_canned_responses`, `upload_media`,
  publicaciones (`show`, `update`, `retry`), `create_label`.
- Después las de prioridad media y baja del plan.

## F5. Plantillas de WhatsApp

- Pantalla para listar, crear, editar y borrar plantillas, con vista previa
  y aviso de cambios de estado; mandar plantillas desde la Bandeja pasadas
  las 24 h.

## F6. Gastos por uso

- Guardar el `pricing` de los estados de WhatsApp, tabla de precios por
  categoría y país, uso de IA por cuenta; mostrarlo en Estadísticas.

## F7. Llamadas y voz

- Revisar requisitos y costo de las llamadas de WhatsApp; investigar lives;
  agentes de voz después.

## F8. Búsqueda en conversaciones viejas

- Búsqueda por mensaje con salto al mensaje (texto completo de Postgres en
  español + `pg_trgm`); semántica después, con F9; herramienta MCP
  `search_messages`.

## F9. EmbeddingGemma 2

- Corre en sombra en develop desde el 2026-11-09. Después de 1 o 2 semanas:
  contar en cuántos casos coinciden los dos modelos
  (`same_decision` / `same_top1` en el log del backend, ver
  `docs/operacion/embeddings.md`).
- Revisar con el dueño la regla de autorespuesta de Instagram con umbral
  0,55 antes de pasar esa cuenta a Gemma.
- Pasar cuenta por cuenta; en CTC hoy no está configurado (sigue OpenAI).

## F10 a F13

Sin cambios respecto del plan: Jev y Laya, CRM con base Krayin, grafos y
multi-idioma.

## F14. Foto del contacto

- Foto de Instagram y Messenger guardada en MinIO y renovada; WhatsApp sigue
  con iniciales.
- Arreglo chico que se puede hacer antes: que las iniciales ignoren lo que
  no es letra ("Lucía Pereira (demo)" muestra "L(").

## F15. Canal de aviso por agente

- Esperar lo que prefieren los agentes de CTC (Sofía lo consulta el
  2026-11-11). Telegram con un bot propio sería la opción gratis.

---

## Pendientes sueltos (no son de una fase)

- **Sofía, en cada dispositivo:** activar el push en Ajustes →
  Notificaciones → Este dispositivo y probar el sonido. Si quiere, el aviso
  por WhatsApp con su número.
- **Agentes en las bandejas de CTC:** ninguna bandeja tiene agentes
  cargados. Sumar a quienes atienden (Ajustes → Bandejas → Agentes) para que
  funcionen la asignación automática y los avisos de conversación nueva.
- **Revisiones de Meta de CTC y de Skiev:** los borradores están listos; los
  envía el dueño. Después, borrar el contenido de prueba en Meta.
- **Bot de CTC:** las frases que nunca debe decir (`never_say_phrases`)
  siguen sin cargar hasta que el dueño lo confirme con el director.
- **Capacitación del 11/11:** abrir el PPTX en PowerPoint antes, nunca se
  probó ahí.
- **Tests de webhooks** (`test_webhooks_router.py`): dos fallan cuando hay
  Redis al alcance, porque la entrega se encola en el worker. Hacer que el
  test fuerce la entrega inmediata.
- **Colores con transparencia** (`bg-x/NN` sobre colores del tema) no generan
  CSS: falta el arreglo central en la configuración de Tailwind.
