# Fases futuras de AloStudio

Plan acordado con el dueño el 2026-11-09. Junta lo que estaba como Fase 8 y
Fase 9 en `AGENTS.md` del fork de Postiz (ya apagado) y lo nuevo de esa fecha.
Todavía sin código. Cada fase, al arrancar, se baja a su propio
`PLAN.<tema>.md` con pasos y criterios de terminado, como los demás planes.
Las fases de pantallas (interfaz de plantillas, CRM, idiomas) se le pueden
delegar a Argon con ese plan; las de infraestructura, datos y licencias las
revisa el dueño antes.

**Experimentales:** F9 (embeddings) y F10 (decisiones) se prueban en ramas
aparte (`exp/*`). Pasan a `develop` solo si convencen al dueño con números.

**Estado de F1 (2026-11-09): hecho en CTC.** Scripts en `ops/respaldo/`, procedimiento en `docs/operacion/respaldos.md`. Copias cifradas con restic en el bucket `alostudio-respaldos` de Cloudflare R2, cron diario 03:30 y prueba de restauración el día 1, avisos en Healthchecks.io. Primera copia y prueba de restauración verificadas. Develop sigue sin respaldo de AloStudio (el dueño solo quiso avisos para CTC).

**Orden propuesto:** F1 → F2 → F3 → F4, y después según prioridad. F1 va
primero porque hoy un disco roto o un servidor perdido se lleva los datos de
CTC. F3 conviene arrancarla temprano porque las revisiones de cada red
tardan semanas.

---

## F1. Política de respaldos

Estado medido el 2026-11-09 en CTC: `~/backup.sh` corre a las 03:30, hace
`pg_dump` de la base y guarda 14 días en `~/backups/` **del mismo servidor**.
No respalda los archivos de MinIO (adjuntos, medios), ni los `.env`, ni copia
nada afuera. Nunca se probó restaurar.

- **Qué se respalda:** base Postgres; buckets de MinIO; `~/AloStudio/.env` y
  `~/infra/.env` cifrados (tienen secretos, nunca en texto plano fuera del
  servidor).
- **Dónde:** fuera del servidor, en otro proveedor o región (almacenamiento
  S3 compatible). Cifrado antes de salir (por ejemplo `restic` o `age`).
- **Retención:** 7 diarios, 4 semanales, 12 mensuales. Ajustar a lo que pida
  cada cliente por contrato.
- **Objetivos:** perder como máximo 24 h de datos (RPO) y volver a estar
  arriba en menos de 4 h (RTO). Si un cliente pide menos, archivado continuo
  de WAL (`pgBackRest` o `wal-g`).
- **Prueba de restauración:** una vez por mes, automática, en una base
  aparte, con conteo de filas contra producción. Un respaldo que no se
  restauró no cuenta.
- **Aviso:** si el respaldo falla o no llega afuera, alerta (correo o
  Telegram). Hoy un fallo no lo ve nadie.
- **Documento:** procedimiento de restauración paso a paso, en el repo.
- Aplica igual a develop y a cada servidor dedicado (ver F2).

## F2. Comercialización: multitenant con plan Enterprise dedicado

Decidido con el dueño el 2026-11-09: una sola instalación multitenant con
suscripción para la mayoría de los clientes, y servidor dedicado como plan
Enterprise para quien lo pida (por contrato, datos o volumen). Una sola app
de Meta como tech provider sirve a todos.

- **Aislamiento:** AloStudio ya separa por `account_id`. Auditar que toda
  consulta, tarea del worker, webhook, búsqueda, vector y herramienta MCP
  filtre por cuenta. Tests que intenten leer datos de otra cuenta.
- **Alta de clientes:** registro, creación de cuenta y conexión de canales
  con Embedded Signup de WhatsApp y los OAuth de Meta, sin intervención
  nuestra.
- **Facturación:** planes, límites por plan (agentes, canales, mensajes,
  almacenamiento, uso de IA), cobro recurrente con un proveedor de pagos y
  suspensión por falta de pago sin borrar datos. El código del webhook de
  pagos no puede tirar excepciones.
- **Límites de uso:** cuotas por cuenta en el worker y en la API, para que
  un cliente no frene a los demás.
- **Operación:** panel interno de cuentas, métricas por cliente, borrado y
  exportación de datos de una cuenta a pedido (privacidad).
- **Enterprise:** la misma imagen desplegada por script en el servidor del
  cliente, con F1 incluida y actualizaciones desde `main`.
- **Legal:** términos de servicio, política de privacidad y acuerdo de
  tratamiento de datos para clientes.

## F3. Redes que faltan

Pendientes desde la Fase 7 de Postiz: **YouTube, LinkedIn (perfil y página
de empresa), TikTok y TikTok Business**, más X, Google Business Profile,
Slack y Twitch. Detalle de cada app en `HANDOFF-apps-redes-sociales.md`
(en el repo de Postiz).

- Primero YouTube, LinkedIn página y TikTok Business, que pidió el dueño.
- Cada una necesita su app de desarrollador y su revisión: iniciar los
  trámites antes de programar, porque tardan.
- Son redes de solo publicación: se suman como adaptadores al módulo de
  publicaciones (`app/domains/publishing/adapters/`), igual que Instagram,
  Facebook y Threads, con métricas en Estadísticas.
- X cobra por uso: entra en F6.

## F4. Herramientas que le faltan al MCP

Hoy `/mcp` tiene 43 herramientas (`app/mcp/tools/`): conversaciones,
mensajes, contactos, etiquetas, citas, productos (solo lectura),
publicaciones e Instagram. Comparado contra los dominios del backend el
2026-11-04 y revisado el 2026-11-09, siguen faltando:

- **Prioridad alta, sin esto un agente se traba:**
  - `list_inboxes`, `list_agents`, `list_teams`: hoy se puede asignar
    (`assign_agent`, `assign_team`), pero no consultar los ids.
  - `create_contact`, `update_contact`.
  - `create_conversation`: hoy solo se responde una conversación existente.
  - `send_message` con adjuntos, y envío de plantillas de WhatsApp.
  - `list_canned_responses`.
  - `upload_media`: hoy solo está `list_media`.
  - `show_publication`, `update_publication`, `retry_publication`.
  - `create_label`.
- **Prioridad media:**
  - Productos: crear y editar. Citas: editar y reprogramar (hoy solo cambia
    el estado).
  - `list_macros` y `execute_macro`.
  - Reportes de conversaciones y agentes, resultados de CSAT.
  - Campañas: listar, crear, consultar resultado.
  - `refresh_publication_metrics`, `list_publishing_networks`.
  - Firmas y sets de publicaciones.
- **Prioridad baja, tocan configuración, con scope `admin`:**
  automatizaciones, autopost RSS, plugs, webhooks, horarios de atención,
  artículos del centro de ayuda, fusionar y bloquear contactos.
- Conectar canales queda fuera: requiere que la persona autorice en el
  navegador.
- Cada función nueva de este plan suma su herramienta (`search_media`,
  `search_messages`, plantillas, etc.).
- WebMCP no se hace por ahora: borrador W3C, solo Chrome con flag. Revisar
  cuando esté estable.

## F5. Plantillas de WhatsApp

Hoy las plantillas se sincronizan desde Meta y se usan en campañas, pero no
hay pantalla para crearlas ni editarlas.

- Pantalla para listar con su estado de aprobación (aprobada, pendiente,
  rechazada con el motivo), crear, editar y borrar.
- Editor con categoría (marketing, utilidad, autenticación), idioma,
  encabezado (texto, imagen, video, documento), cuerpo con variables y
  ejemplos, pie y botones (respuesta rápida, URL, teléfono).
- Vista previa como burbuja de WhatsApp.
- Aviso cuando Meta cambia el estado o la categoría (webhook
  `message_template_status_update`).
- Mandar una plantilla desde la Bandeja cuando pasaron las 24 h.

## F6. Seguimiento de gastos por uso

Decidida el 2026-11-02. Hoy AloStudio solo muestra el gasto en anuncios de
Meta; no registra lo que cuesta cada mensaje ni el uso de IA.

- **WhatsApp:** Meta cobra por plantilla entregada según categoría y país;
  responder dentro de las 24 h es gratis. El webhook de estados trae el
  objeto `pricing` y `app/domains/whatsapp/incoming_cloud.py` hoy lo ignora:
  guardarlo y valorarlo con una tabla de precios por categoría y país.
- **IA (OpenAI hoy; Jev si entra F10):** tokens consumidos por cuenta.
- **X** (si se integra en F3): pago por post y por lectura.
- **SMS** (si se suma el canal): por mensaje y país.
- **Llamadas** (F7): por minuto.
- Mostrarlo en Estadísticas por mes, canal y campaña. En F2 alimenta los
  límites y la facturación. Confirmar los precios vigentes en las páginas
  oficiales antes de cargar la tabla.

## F7. Llamadas y voz

Juntas por decisión del dueño (puntos 6 y 7).

1. **Llamadas de WhatsApp** (WhatsApp Business Calling API): recibir y hacer
   llamadas de voz desde AloStudio, con el registro en la conversación.
   Revisar requisitos, países habilitados y costo antes de empezar.
2. **Lives:** investigar qué dan las APIs de Facebook (videos en vivo de
   Páginas) e Instagram (lectura de lives y sus comentarios). Instagram no
   permite transmitir desde terceros por API; confirmar en la documentación
   vigente.
3. **Agentes de voz, después:** atender la llamada con un agente que usa las
   herramientas del MCP y pasa a una persona cuando hace falta. Elegir
   proveedor de voz a texto y texto a voz con buen español rioplatense.

## F8. Búsqueda en conversaciones viejas

El caso: encontrar algo que se habló con alguien hace meses, dentro de una
conversación enorme. Hoy `GET /conversations/search` busca con `ILIKE` y
devuelve **conversaciones**, no lleva al mensaje.

1. **Sin IA, primero:** buscar dentro de una conversación y en todas, con
   resultados por mensaje (fragmento resaltado, fecha, contacto) y salto al
   mensaje con su contexto, cargando la conversación alrededor de él.
   Índice de texto completo de Postgres con configuración `spanish` y
   `pg_trgm` para errores de tipeo. Gratis y rápido.
2. **Semántica, después (con F9):** "lo que hablamos del pago en cuotas"
   aunque no se haya escrito esa palabra. Vectores por mensaje o por bloques
   de mensajes, combinados con el texto completo.
3. Herramienta MCP `search_messages`.
4. Siempre filtrado por cuenta y por lo que el agente puede ver.

## F9. Embeddings gratis y búsqueda multimedia (experimental)

**Aprobado por el dueño el 2026-11-09:** EmbeddingGemma 2 reemplaza a OpenAI
si la medición lo confirma. La medición de recursos y umbrales corre en la
rama `exp/embeddinggemma`; informe en `docs/experimentos/embeddinggemma.md`.

**Estado (2026-11-09):** medición hecha y migración aprobada ("la medición
salió superior a OpenAI"). Implementada la parte de texto:

- servicio local;
- columnas `embedding_gemma` junto a las de OpenAI, con escritura doble;
- backfill;
- modo sombra;
- modelo elegido por cuenta;
- umbral de Gemma en una columna aparte, sin convertir los de OpenAI.

Operación en `docs/operacion/embeddings.md`. Falta:

- el período de sombra en develop y el cambio de cada cuenta;
- revisar con el dueño las reglas con umbral propio;
- la búsqueda multimedia, que va aparte.

Hoy los embeddings son de OpenAI (`text-embedding-3-small`, `vector(1536)`,
pagos) y se usan en dos lugares: el centro de ayuda
(`app/domains/portals/embeddings.py`) y las respuestas automáticas de
comentarios de Instagram (`app/domains/instagram/autoreply*`), cuyos
umbrales se midieron con ese modelo.

**Modelo:** [EmbeddingGemma 2](https://huggingface.co/google/embeddinggemma-2),
gratis y local. No hace falta ChromaDB: su modelo gratuito por defecto
(`all-MiniLM-L6-v2`) está entrenado sobre todo en inglés, y lo que importa es
el modelo, no la base. Ya tenemos pgvector (0.8.4) en Postgres. Si
EmbeddingGemma 2 no entra en el servidor, probar modelos de texto
multilingües más chicos (`multilingual-e5-small`, `bge-m3`) para la parte de
texto.

- **Ficha:** Apache 2.0; texto, imagen, video y audio en un mismo espacio de
  768 dimensiones (truncable a 512 o 256, renormalizando); 740M de
  parámetros; ventana de 8192 tokens; usar `bfloat16` o `float32`, nunca
  `float16`; los textos llevan prefijos de tarea.
- **Medir antes de programar,** en el VPS: memoria, tiempo por texto,
  imagen, video, audio y consulta. 6 vCPU sin GPU, unos 8,6 GB libres
  compartidos. Si no entra en un servidor de CTC, descartar o achicar.
- **Evaluar con datos reales en español:** búsqueda por texto, por imagen y
  por audio; confirmar si analiza el audio de un video (si no, transcribir).
- **Diseño:** proceso aparte con límite de memoria y prioridad baja; el
  worker genera vectores por lotes al subir un archivo, más un backfill;
  tabla de vectores con índice HNSW y columna de modelo, porque cambiar de
  modelo obliga a recalcular. Siempre filtrado por cuenta.
- **Usos:**
  - Medios: búsqueda por texto, imagen o audio; publicaciones que usan cada
    recurso; parecidos y duplicados; agrupación automática; MCP
    `search_media`.
  - Manual de uso y centro de ayuda vectorizados, para que el agente
    responda cómo se usa AloStudio.
  - Reemplazar OpenAI en el centro de ayuda y en las respuestas automáticas
    de Instagram: recalcular vectores, cambiar la columna a 768 y **volver a
    medir los umbrales** con comentarios reales antes de cambiar. Migración
    con las dos columnas conviviendo hasta terminar, sin cortar a los
    clientes.
  - Búsqueda semántica de F8.

## F10. Decisiones y clasificación: Jev ahora, Laya después (experimental)

Idea del dueño: usar [Jev](https://knolli.ai/post/jev-vs-laya) (modelo de
decisiones por API de TypeSafe AI, pago, con mejores tasas de acierto
publicadas) un tiempo, guardar sus resultados mientras se entrena
[Laya](https://huggingface.co/convaiinnovations/laya) (Apache 2.0, local), y
dejar de pagar Jev cuando Laya llegue a los niveles acordados. Laya expone un
endpoint compatible con el de Jev, así que el cambio de proveedor es una
configuración, no otro código.

1. **Qué decide:** etiqueta, intención, sentimiento, urgencia y a qué
   equipo va, con pocas opciones por pregunta (hasta unas 6).
2. **Antes de mandar mensajes a Jev:** revisar sus términos (que permitan
   usar sus respuestas para entrenar otro modelo) y su tratamiento de datos;
   avisar a cada cliente y anonimizar (nombres, teléfonos, documentos).
3. **Set de evaluación etiquetado a mano**, apartado y nunca usado para
   entrenar. Las respuestas de Jev tienen sus propios errores: sirven para
   entrenar, no para medir.
4. **Modo sombra con Jev:** decide en paralelo sin tocar nada; se guarda
   cada decisión con su confianza y, cuando una persona corrige, la
   corrección. Medir el costo real (entra en F6).
5. **Entrenar Laya** con las decisiones de Jev más las correcciones humanas
   (la ficha trae un cuaderno para Kaggle con GPU) y recalibrar la
   confianza, que sale inflada. La ficha no publica resultados en español y
   advierte sobre mensajes cortos: medir la línea base sin entrenar primero.
6. **Comparar** Laya, Jev, reglas simples y un LLM sobre el set de
   evaluación, más RAM y latencia de Laya en el VPS.
7. **Umbrales acordados antes de entrenar.** Si Laya los alcanza, pasa a
   producción y se apaga Jev; si no, se sigue juntando datos o se descarta.
8. Ya en producción: etiquetas y prioridad vía condiciones nuevas en
   automatizaciones; después flujos conversacionales (botones y palabras
   clave primero, Laya para texto libre, a una persona si duda).

No bloquear contactos automáticamente por enojo: marcar urgente y pasar a
una persona; bloquear solo por abuso claro y con confirmación humana.

## F11. CRM más completo y minería de datos

AloStudio ya tiene contactos, productos y citas (de Chatwoot y del CRM del
fork). Para completarlo se porta un CRM open source con licencia permisiva,
como se hizo con Chatwoot.

- **Elegido (2026-11-09): [Krayin](https://github.com/krayin/laravel-crm),
  MIT.** Muy activo (24 mil estrellas, cambios diarios), CRM completo:
  leads con embudo por etapas, personas y organizaciones, productos,
  presupuestos, actividades, correo y formularios web. Está en Laravel y
  Vue: se porta reescribiendo a FastAPI y al frontend propio, igual que
  Chatwoot. La MIT permite cerrar el código; pide conservar su aviso de
  copyright en los archivos portados (y en un `NOTICE`). Antes de portar,
  revisar la licencia de cada paquete del repo, no solo la raíz.
- **Referencia secundaria:** [Atomic CRM](https://github.com/marmelab/atomic-crm),
  MIT, en React. Más chico (contactos, empresas, oportunidades en tablero
  Kanban, notas, tareas); sirve para ideas de interfaz.
- **Descartados por licencia** (verificado el 2026-11-09): Odoo Community
  (LGPL-3: lo portado queda LGPL y el plan Enterprise, que instala en el
  servidor del cliente, obliga a entregar ese código), Twenty, EspoCRM,
  SuiteCRM y Frappe CRM (AGPL). Corteza es Apache 2.0 pero es una
  plataforma low-code para armar un CRM, no un CRM hecho.
- **Qué sumar desde Krayin, a decidir con el dueño:** empresas además de personas;
  oportunidades con etapas (embudo de ventas), valor y probabilidad;
  actividades y tareas con vencimiento; presupuestos con productos; origen
  del contacto (qué canal, campaña o publicación lo trajo); historial
  unificado del contacto en todos los canales.
- **Minería de datos** (acordada): segmentos automáticos (clientes que
  preguntan y no compran, inactivos, frecuentes); productos más consultados;
  horarios y canales con más demanda; tiempo de respuesta contra
  conversión. Primero con consultas y reportes; con F9 y F10, temas
  frecuentes e intenciones.
- Herramientas MCP para todo lo nuevo (F4).

## F12. Grafos

Dos grafos, confirmados por el dueño el 2026-11-09, porque responden
preguntas distintas:

1. **Grafo de los datos de la app:** contactos, conversaciones, productos,
   campañas, publicaciones y agentes como nodos y relaciones ("qué contactos
   preguntaron por este curso y vinieron de esta campaña").
2. **Grafo de conocimiento:** conceptos del negocio y del manual (cursos,
   requisitos, precios, preguntas frecuentes) y cómo se relacionan, para que
   el agente responda con más precisión que solo con vectores (combinado
   con F9).

**Cómo, sin esperar a Postgres 19.** Hoy usamos Postgres 16
(`pgvector/pgvector:pg16`). PostgreSQL 19 suma SQL/PGQ (`CREATE PROPERTY
GRAPH` y `GRAPH_TABLE`), pero es nuevo, su primera versión no trae caminos de
largo variable ni camino más corto, y hace falta una imagen con pgvector.
Lo más conveniente, sin infraestructura nueva:

- **Grafo de datos:** las relaciones ya existen como claves foráneas. Se
  consulta con SQL normal y CTE recursivas (`WITH RECURSIVE`) en funciones
  del backend, más vistas para las relaciones que se usan seguido. Nada que
  instalar ni migrar.
- **Grafo de conocimiento:** dos tablas propias en Postgres, nodos (con su
  vector de F9) y aristas (origen, destino, tipo, peso), siempre con
  `account_id`. Búsqueda: vectores para encontrar los nodos de entrada y CTE
  recursiva para recorrer sus vecinos (el patrón de GraphRAG).
- **Descartado por ahora:** Apache AGE (Cypher dentro de Postgres) obliga a
  armar una imagen propia con AGE y pgvector y a seguir sus versiones;
  Neo4j suma otra base que operar y respaldar en cada servidor.
- **Cuando se actualice a Postgres 19** (y tenga camino más corto), definir
  los grafos con `CREATE PROPERTY GRAPH` sobre las mismas tablas, sin mover
  datos; las consultas viejas siguen funcionando.

Empezar por el primero, que no necesita IA; el segundo después de F9.

## F13. Multi-idioma

Hoy la interfaz está solo en español, con los textos escritos en los
componentes.

- Sacar los textos a archivos de traducción (sin librerías externas pesadas
  si alcanza con algo propio), con español como base e inglés y portugués
  primero.
- Idioma por usuario, con el del navegador por defecto; fechas, números y
  monedas con `Intl`.
- Correos, avisos y textos del backend también traducidos.
- Las respuestas del bot y del agente en el idioma del cliente.
- Buen trabajo para Argon una vez definida la estructura.

## F14. Foto del contacto en la bandeja

Pedido del dueño el 2026-11-10. Hoy los contactos se ven con un círculo de
color y sus iniciales (`frontend/components/ui/avatar.tsx`); el backend
devuelve `avatar_url` vacío (`app/domains/contacts/presenters.py`).

Qué se puede por canal:

- **WhatsApp:** no. La Cloud API de Meta no entrega la foto de perfil de
  quien escribe. Quedan las iniciales.
- **Instagram y Messenger:** sí. Se pide `profile_pic` junto con el nombre
  en la consulta de perfil que ya se hace (`fetch_contact_name` en
  `app/domains/instagram/graph.py`). El link de Meta vence a los pocos días:
  bajar la imagen, guardarla en MinIO y renovarla de vez en cuando con un
  trabajo de ARQ.
- **Email:** Gravatar, opcional y apagado por defecto (manda a un tercero un
  hash del correo).
- **Chat del sitio:** no hay foto.

Trabajo:

- Columna de avatar en el contacto, guardada al recibir el primer mensaje
  y renovada por el trabajo periódico.
- `Avatar` acepta una imagen y cae a las iniciales si no hay foto o si no
  carga. Se muestra en la lista, el encabezado de la conversación y el panel
  del contacto.
- Arreglo chico que se puede hacer antes: las iniciales ignoran lo que no es
  letra ni número. Hoy "Lucía Pereira (demo)" muestra "L(" en vez de "LP".
- En CTC el canal principal es WhatsApp, así que ahí casi todo sigue con
  iniciales; la mejora se nota en Instagram y Messenger.

## F15. Canal de aviso que elige cada agente

Idea del dueño del 2026-11-10. Hoy un aviso (derivación del bot,
asignación, mensaje nuevo) llega por la campana con sonido, el push del
navegador, el email y, solo para derivaciones, WhatsApp con plantilla de
Meta (se cobra cada envío).

- Que cada agente elija en Ajustes → Notificaciones por dónde prefiere
  enterarse: push, email, WhatsApp o Telegram, y para qué avisos.
- Telegram sería gratis: un bot de AloStudio al que cada agente le escribe
  una vez para vincularse (con un código de un solo uso), y por ahí le
  llegan los avisos.
- WhatsApp sigue con su costo por envío; mostrarlo al elegirlo.
- Antes de hacerlo, preguntar a los agentes de CTC qué usarían de verdad
  (Sofía lo consulta el 2026-11-11).

## Descartado

- **Consultas de Telegram respondidas por el bot de Meta** (2026-11-09): se
  descarta, y con eso la parte de agentes propios para otros canales queda
  afuera por ahora. Los agentes de voz siguen en F7.
- **Videos con IA** (HeyGen, Reel.Farm): descartado el 2026-11-01.
