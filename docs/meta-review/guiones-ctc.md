# Videos para la revisión de Meta: app AloStudio CTC (1801154141139581)

CTC es una sola organización que conecta sus propias cuentas. Por eso estos guiones piden menos que los de Skiev Dev (`guiones.md`) y usan **Facebook Login**, así que los permisos de Instagram son los `instagram_*`, no los `instagram_business_*`.

## Qué se pide

| Video | Función | Permisos principales | Permisos que los acompañan |
|---|---|---|---|
| 1 | Mensajes de Instagram | `instagram_manage_messages` | `instagram_basic`, `pages_show_list`, `pages_read_engagement`, `pages_manage_metadata`, `business_management` |
| 2 | Comentarios de Instagram | `instagram_manage_comments` | Los mismos del video 1 |
| 3 | Mensajes de Facebook | `pages_messaging` | `pages_show_list`, `pages_manage_metadata`, `business_management` |

Sumar en el mismo envío, con los videos 1 y 3 como demostración, la función **Business Asset User Profile Access**: sin ella, la bandeja muestra `facebook-123456` en vez del nombre de quien escribe.

No se piden por ahora los permisos de publicar (`instagram_content_publish`, `pages_manage_posts`) ni los de estadísticas: hoy se usan sobre cuentas propias. Si el formulario los exige o la prueba de publicación falla, se suma un video con el guion 2 o 4 de `guiones.md`.

Antes de enviar, confirmar en el formulario qué permisos marca Meta como dependencias. Esa lista puede cambiar la tabla de arriba.

## Antes de grabar

- **Probar todo primero.** Grabar solo cuando la prueba de mensajes y la de publicación hayan funcionado.
- **Sin datos de alumnos.** La bandeja de CTC tiene conversaciones reales, con nombres y mensajes. Usar el difuminado en vivo de abajo y además filtrar la bandeja por el canal del video. No abrir ninguna conversación real ni la campana de notificaciones. Si un dato real se ve nítido aunque sea un instante, volver a grabar.
- **Sin secretos.** Nada de tokens ni de la pantalla Ajustes → Instalación.
- **Ventana limpia.** Grabar solo la ventana del navegador (`Win + G` u OBS), sin otras pestañas, marcadores ni notificaciones.
- **Inglés.** Interfaz de Facebook e Instagram en inglés si se puede. AloStudio está en español, así que los subtítulos en inglés son obligatorios.
- **De punta a punta y sin cortes** en el momento en que se usa el permiso: ingreso, pantalla de permisos de Meta, función en AloStudio y resultado en la red.
- **Segunda cuenta para el "cliente".** Hasta la aprobación, Meta solo entrega mensajes de personas con rol en la app. Hay que dar rol de evaluador en la app a una cuenta de Facebook, con su Instagram vinculado, que no sea la que administra.
- **Autorización visible.** Al tocar Facebook Login, si Facebook no muestra los permisos porque ya están aceptados, entrar por "editar acceso" o quitar antes la app desde la configuración de Facebook de esa cuenta. **Hacer esto solo sabiendo que las bandejas actuales pueden dejar de recibir hasta volver a autorizar**, y hacerlo en un horario tranquilo.

## Difuminado en vivo de la bandeja

Difumina todas las filas de la lista de conversaciones, salvo las del contacto de prueba. Las filas nuevas nacen difuminadas, así que un chat que entra durante la grabación no se ve. Se hace en el navegador y no cambia nada en AloStudio.

1. En Chrome, crear un marcador nuevo llamado "Difuminar" y pegar esto como URL:

```text
javascript:(()=>{const id='rec-blur';const old=document.getElementById(id);if(old){old.remove();clearInterval(window.__recBlur);document.querySelectorAll('[data-rec-ok]').forEach(e=>e.removeAttribute('data-rec-ok'));return}const n=(prompt('Nombre del contacto de prueba')||'').trim().toLowerCase();const s=document.createElement('style');s.id=id;s.textContent='li:has(a[href*="/conversations/"]):not([data-rec-ok]){filter:blur(9px);pointer-events:none}';document.head.appendChild(s);const f=()=>document.querySelectorAll('li:has(a[href*="/conversations/"])').forEach(l=>{const ok=n&&l.textContent.toLowerCase().includes(n);if(ok)l.setAttribute('data-rec-ok','');else l.removeAttribute('data-rec-ok')});f();window.__recBlur=setInterval(f,200)})();
```

2. **Antes de empezar a grabar**, abrir la Bandeja, tocar el marcador y escribir el nombre de la cuenta de prueba, tal como aparece en la lista.
3. Revisar que el resto de las filas se vea borroso. Tocar el marcador de nuevo lo apaga.

**Se apaga al recargar la página**, y volver de la autorización de Facebook la recarga. Después de autorizar, pausar la grabación, volver a activarlo y recién entonces abrir la Bandeja. Nunca abrir la Bandeja grabando sin haberlo activado. También se puede grabar la autorización en un video y la bandeja en otro tramo, si Meta acepta el corte, pero el momento de usar el permiso tiene que quedar sin cortes.

## Video 1: mensajes de Instagram

Cuenta: `ctcsalto`. Permisos: `instagram_manage_messages`, `instagram_basic`, `pages_show_list`, `pages_read_engagement`, `pages_manage_metadata`, `business_management`.

1. Entrar a AloStudio y abrir **Instagram** en el menú.
2. En **Conectar una cuenta**, tocar **Facebook Login**.
3. Mostrar completa la pantalla de permisos de Meta, elegir la página del instituto y aceptar.
4. Volver a AloStudio y mostrar la cuenta conectada, con su nombre de usuario.
5. Con la segunda cuenta, mandar un mensaje directo a `ctcsalto`.
6. Abrir **Bandeja**, filtrar por Instagram, mostrar que el mensaje llegó y responderlo.
7. Mostrar en Instagram, en la segunda cuenta, que llegó la respuesta.

Subtítulos:

- "Instituto CTC Salto connects its own Instagram professional account to AloStudio through Facebook Login."
- "AloStudio shows the account's username so the staff knows which account is connected."
- "A student sends a direct message. It appears in the institute's shared inbox."
- "A staff member replies from AloStudio, and the student receives the reply on Instagram."

## Video 2: comentarios de Instagram

Cuenta: `ctcsalto`. Permisos: `instagram_manage_comments`, `instagram_basic`, `pages_show_list`, `pages_read_engagement`, `business_management`.

Usar una publicación de prueba de `ctcsalto`, publicada antes de grabar, y borrarla después.

1. Con la segunda cuenta, comentar la publicación en Instagram.
2. En AloStudio, abrir **Instagram → Publicaciones** y entrar a esa publicación.
3. Mostrar el comentario y tocar **Responder**.
4. Mostrar en Instagram que apareció la respuesta.

Subtítulos:

- "Comments on the institute's own posts appear in AloStudio."
- "A staff member replies to the comment from AloStudio."
- "The reply is published on Instagram, under the comment."

## Video 3: mensajes de Facebook

Página: Instituto CTC Salto. Permisos: `pages_messaging`, `pages_show_list`, `pages_manage_metadata`, `business_management`.

1. Abrir **Ajustes → Bandejas de entrada**, crear una nueva y elegir **Facebook**.
2. Tocar **Conectar con Facebook**, mostrar la pantalla de permisos, elegir la página y aceptar.
3. De vuelta en AloStudio, en "¿Qué Página querés conectar?", elegir la página y mostrar la bandeja. Si la bandeja ya existe, AloStudio la actualiza: mostrarla igual.
4. Con la segunda cuenta, mandar un mensaje a la página por Messenger.
5. Abrir **Bandeja**, filtrar por Facebook, mostrar el mensaje y responderlo.
6. Mostrar en Messenger que llegó la respuesta.

Subtítulos:

- "Instituto CTC Salto connects its own Facebook Page to AloStudio and chooses which Page to use."
- "A student sends a message to the Page. It appears in the institute's shared inbox."
- "A staff member replies from AloStudio, and the student receives it on Messenger."

## Textos para el formulario

Descripción general:

> AloStudio is the customer communication tool used by Instituto CTC Salto (CTC Salto SRL), an educational institute in Salto, Uruguay. The institute connects only its own Facebook Page and Instagram accounts, so its staff can answer students and prospective students from one shared inbox. Only people invited by the institute can use it. Data is used only to provide these functions to the institute; it is not sold or used for advertising.

`instagram_manage_messages`:

> Used to receive direct messages sent to the institute's Instagram accounts and let its staff reply from AloStudio's shared inbox.

`instagram_manage_comments`:

> Used to show comments on the institute's own Instagram posts and let its staff reply to them from AloStudio.

`instagram_basic`:

> Used to identify the connected Instagram professional account and show its username and picture, so the staff knows which account it is working with.

Business Asset User Profile Access:

> Used to show the name of the person who writes to the institute, so the staff knows who it is talking to in the shared inbox.

`pages_messaging`:

> Used to receive messages sent to the institute's Facebook Page and let its staff reply from AloStudio's shared inbox.

`pages_show_list`:

> Used to list the Pages the administrator manages so they can choose which one to connect.

`pages_manage_metadata`:

> Used to subscribe the connected Page to webhooks, so its new messages reach AloStudio.

`pages_read_engagement`:

> Used to read the connected Page's basic information and its linked Instagram account when the institute connects them.

`business_management`:

> Used to reach the Pages and Instagram accounts that belong to the institute's business portfolio when it connects them.

## Instrucciones para los revisores

Pendiente de resolver antes de enviar: **no dar acceso a la cuenta "CTC Salto"**, porque tiene conversaciones reales de alumnos. Hace falta una cuenta aparte de demostración en la instalación, con un usuario creado para esto y sin datos reales. Si Meta pide probar la función en vivo y no le alcanza con los videos, ver cómo darle ese acceso sin exponer datos.
