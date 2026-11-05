# Videos para la revisión de Meta (app AloStudio, 2913274559045232)

Permisos ya aprobados: `whatsapp_business_messaging`, `whatsapp_business_management`.

## Antes de grabar

- Grabá solo la ventana del navegador (OBS o `Win + G`), en una ventana limpia, sin otras pestañas ni datos privados.
- Interfaz de Facebook e Instagram en inglés si se puede; si no, subtítulos en inglés. Meta pide entender cada pantalla.
- Mostrá siempre, de punta a punta: el ingreso, la pantalla de permisos de Meta, la función en AloStudio y el resultado en la red.
- Sin cortes en el momento en que se usa el permiso. Sin mostrar tokens, secretos ni datos de alumnos o clientes reales.
- Hace falta una segunda cuenta para mandar mensajes y comentarios.
- Publicaciones de prueba en cuentas tuyas; se pueden borrar después.

## Video 1: mensajes de Instagram

Permisos: `instagram_business_basic`, `instagram_business_manage_messages`

1. Entrar a AloStudio y abrir Instagram → Conexión.
2. Conectar con Instagram Login y mostrar la pantalla de permisos completa. Aceptar.
3. Volver a AloStudio y mostrar la cuenta conectada (nombre de usuario).
4. Con la segunda cuenta, mandar un mensaje directo a la cuenta conectada.
5. Abrir Bandeja, mostrar que el mensaje llegó y responder.
6. Mostrar en Instagram, en la segunda cuenta, que llegó la respuesta.

Subtítulos:
- "A business connects its own Instagram professional account to AloStudio."
- "AloStudio shows the account's username so the team knows which account is connected."
- "A customer sends a direct message. It appears in the team's shared inbox."
- "An agent replies from AloStudio, and the customer receives the reply on Instagram."

## Video 2: publicar en Instagram

Permisos: `instagram_business_content_publish`, `instagram_business_manage_insights`, `instagram_business_manage_comments`

Si la cuenta ya está conectada, igual mostrá la conexión con la pantalla de permisos.

1. Abrir Publicaciones, crear una publicación con imagen para esa cuenta y publicarla.
2. Abrir la publicación en Instagram para mostrar que salió.
3. Con la segunda cuenta, comentar la publicación.
4. En AloStudio, abrir Instagram → Publicaciones, ver el comentario y responderlo.
5. Mostrar la respuesta en Instagram.
6. Abrir Estadísticas y mostrar los números de la publicación y de la cuenta. Hacelo con un post que ya tenga algunos días, porque los datos pueden tardar.

Subtítulos:
- "The business schedules a post from AloStudio and it is published to its own Instagram account."
- "Comments on the post appear in AloStudio, and the team can reply to them."
- "The business sees the performance of its own posts and account in AloStudio's analytics."

## Video 3: mensajes de Facebook (PENDIENTE: requiere desarrollo)

Permisos: `pages_show_list`, `pages_manage_metadata`, `pages_messaging`, `business_management`

No se puede grabar todavía. AloStudio conecta Messenger con un token manual: falta una conexión de Páginas de Facebook con OAuth que muestre la pantalla de permisos y deje elegir la Página.

## Video 4: publicar en Facebook (PENDIENTE: requiere desarrollo)

Permisos: `pages_manage_posts`, `pages_read_engagement`

Depende de la misma conexión del video 3. Además, las estadísticas de vistas necesitan `read_insights`, que hoy no se pide.

## Video 5: Threads (para el final)

Permisos: `threads_basic`, `threads_content_publish`, `threads_manage_insights`, `threads_manage_replies`

1. Abrir Publicaciones → Agregar canal → Threads. Mostrar la pantalla de permisos y aceptar.
2. Publicar un post en ese canal y mostrarlo en Threads.
3. En Ajustes → Plugs, crear una respuesta automática al llegar a un número de "me gusta".
4. Con la segunda cuenta, darle "me gusta" al post. Esperar a que corra el plug, porque corre después de la sincronización horaria, y mostrar la respuesta en Threads.
5. Abrir Estadísticas y mostrar los números del post.

Subtítulos:
- "The user connects their own Threads profile and publishes from AloStudio."
- "A rule replies to the user's own post when it reaches a number of likes."
- "The user sees the performance of their posts in AloStudio's analytics."

## Textos para el formulario

Descripción general:

> AloStudio is a customer communication and social media management tool. Businesses connect their own accounts to answer customers from a shared inbox, publish and schedule their own content, and measure its performance. Only people invited by the business can use it. Data is used only to provide these functions to that business; it is not sold or used for advertising.

`instagram_business_basic`:

> Used to identify the connected Instagram professional account and show its username and picture, so the team knows which account it is working with.

`instagram_business_manage_messages`:

> Used to receive direct messages sent to the business's Instagram account and let its agents reply from AloStudio's shared inbox.

`instagram_business_content_publish`:

> Used to publish and schedule posts that the business creates in AloStudio on its own Instagram account.

`instagram_business_manage_comments`:

> Used to show comments on the business's own posts and let it reply to them from AloStudio.

`instagram_business_manage_insights`:

> Used to show the business the metrics of its own posts and account in AloStudio's analytics.

`threads_basic`:

> Used to identify the connected Threads profile and show its name and username.

`threads_content_publish`:

> Used to publish and schedule posts that the user creates in AloStudio on their own Threads profile.

`threads_manage_replies`:

> Used to post automatic replies on the user's own posts, according to rules the user creates, such as when a post reaches a number of likes.

`threads_manage_insights`:

> Used to show the user the metrics of their own Threads posts in AloStudio's analytics.

Instrucciones para los revisores: completar con la URL, y con un usuario y una contraseña de prueba creados para esto, sin datos de clientes.
