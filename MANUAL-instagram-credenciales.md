# Manual — Credenciales permanentes de Instagram (Graph API)

Cómo obtener un **Page Access Token de larga duración (que no expira)** y
el **ID de la cuenta de Instagram Business** para publicar/borrar/moderar
desde AloStudio, sin tener que regenerar el token a mano cada hora.

> Estado de la validación: el camino de **publicación** (crear contenedor →
> poll → publicar → permalink + cuota) está probado contra Meta real y
> funciona. Ver "Verificación" más abajo.

---

## 0. Conceptos (qué token usa qué)

| Credencial | Para qué | ¿Dónde vive? |
|---|---|---|
| **App ID / App Secret** | Solo para el flujo OAuth (intercambio de tokens) y la firma HMAC de webhooks. **No** se usa para publicar. | `.env.local` (`META_APP_ID`, `META_APP_SECRET`) |
| **Page Access Token** | Publicar, borrar, comentar. Es **la** credencial que usa el publisher. | fila del canal (`channel_instagram.access_token`) — o `.env.local` para pruebas |
| **IG Business Account ID** | Identifica a qué cuenta de IG se publica (es un número, no el @usuario). | `channel_instagram.instagram_id` — o `.env.local` para pruebas |

La clave de la "permanencia": **un Page Token derivado de un User Token
de larga duración no expira** (mientras no cambies la contraseña de
Facebook ni revoques permisos).

---

## 1. Requisitos previos (una sola vez)

1. Una **Página de Facebook**.
2. Una cuenta de **Instagram Business o Creator** **vinculada** a esa
   Página. (Desde la app de Instagram: *Configuración → Cuenta y
   herramientas profesionales → Compartir en otras apps → Facebook*; o
   desde la Página de FB → *Configuración → Cuentas vinculadas*.)
3. Una **App de Meta** (en tu caso ya existe: "Test Post") con el producto
   *Instagram* agregado.
4. Tu usuario tiene que ser **admin** de la app y de la Página.

### Permisos (scopes) a otorgar al token

| Scope | Para qué |
|---|---|
| `instagram_basic` | leer perfil + media |
| `instagram_content_publish` | **publicar** (`/media` + `/media_publish`) |
| `instagram_manage_comments` | listar/responder/ocultar/borrar comentarios |
| `instagram_manage_insights` | métricas de stories |
| `pages_show_list` | descubrir las Páginas del usuario |
| `pages_read_engagement` | leer metadatos de la Página |
| `business_management` | contexto de Business Manager |

> **Borrar media:** ver la nota al final — requiere un permiso/aprobación
> extra que el token de prueba no tiene (por eso el smoke test dio `#10`).

---

## 2. Paso 1 — User Token corto (Graph API Explorer)

1. https://developers.facebook.com → **Herramientas → Explorador de la API
   Graph**.
2. En *App de Meta* elegí tu app (p. ej. "Test Post").
3. En *Permisos* agregá los scopes de la tabla de arriba.
4. Click en **Generate Access Token** y aceptá el diálogo de permisos.

Ese token dura **~1–2 horas**. Sirve solo como punto de partida.

---

## 3. Paso 2 — Convertir a User Token largo (~60 días)

Necesitás `META_APP_ID` y `META_APP_SECRET` (de *Configuración → Básica*
de tu app). Pegá esta URL en el navegador (o en el Explorer):

```
GET https://graph.facebook.com/v23.0/oauth/access_token
    ?grant_type=fb_exchange_token
    &client_id=TU_APP_ID
    &client_secret=TU_APP_SECRET
    &fb_exchange_token=USER_TOKEN_CORTO
```

Respuesta:

```json
{ "access_token": "USER_TOKEN_LARGO", "token_type": "bearer", "expires_in": 5183944 }
```

`expires_in` ≈ 60 días. Guardá ese **USER_TOKEN_LARGO** para el paso
siguiente (no es el que termina en `.env.local`).

---

## 4. Paso 3 — Page Token que NO expira

Con el user token largo:

```
GET https://graph.facebook.com/v23.0/me/accounts?access_token=USER_TOKEN_LARGO
```

Respuesta (recortada):

```json
{ "data": [ { "name": "Test Pagina", "id": "472137605992335",
             "access_token": "PAGE_TOKEN_PERMANENTE", "tasks": ["CREATE_CONTENT", ...] } ] }
```

El `access_token` de tu Página ahora es de **larga duración / no expira**.
Ese es tu **PAGE_TOKEN** definitivo.

**Verificá la duración** en el debugger:
https://developers.facebook.com/tools/debug/accesstoken/ → pegá el page
token → en *Expires* debería decir **"Never"**.

---

## 5. Paso 4 — IG Business Account ID

Con el page token:

```
GET https://graph.facebook.com/v23.0/472137605992335?fields=instagram_business_account&access_token=PAGE_TOKEN_PERMANENTE
```

Respuesta:

```json
{ "instagram_business_account": { "id": "17841451736515320" }, "id": "472137605992335" }
```

Ese `instagram_business_account.id` es tu **INSTAGRAM_BUSINESS_ACCOUNT_ID**.

> Si el campo viene vacío, la Página **no tiene una cuenta de IG
> Business/Creator vinculada** — volvé al Requisito #2.

---

## 6. Paso 5 — Dónde poner las credenciales

### Para pruebas locales (`.env.local`, gitignored)

```
PAGE_TOKEN=PAGE_TOKEN_PERMANENTE
INSTAGRAM_BUSINESS_ACCOUNT_ID=17841451736515320
```

### En producción

Van en la fila del canal cuando se crea el inbox de Instagram:
`channel_instagram.access_token` = page token,
`channel_instagram.instagram_id` = IG business account id.
(El flujo OAuth del hito I.10 automatiza este paso cuando se implemente.)

> Nunca commitees el token. `.env.local` está en `.gitignore`. Si un token
> aparece alguna vez en un chat, captura o log, **regeneralo**.

---

## 7. Verificación

Con `PAGE_TOKEN` + `INSTAGRAM_BUSINESS_ACCOUNT_ID` en `.env.local`:

```
.venv/Scripts/python.exe scripts/ig_publish_smoke.py
```

Debe terminar con `SMOKE TEST PASSED` e imprimir el permalink del post.
Opciones útiles (variables de entorno):

| Variable | Efecto |
|---|---|
| `IG_SMOKE_IMAGE_URL` | usar tu propia imagen pública (https, JPEG) |
| `IG_SMOKE_CAPTION` | texto del caption |
| `IG_SMOKE_CLEANUP=1` | borra el post de prueba al terminar (requiere permiso de borrado) |
| `IG_SMOKE_DELETE_MEDIA_ID=<id>` | modo solo-borrar (limpia un post anterior) |

El script lee `.env.local` por sí mismo y **enmascara el token** en su
salida — no hace falta pasárselo a nadie.

---

## 8. Notas y limitaciones

- **Renovación:** un page token derivado de un user largo "no expira",
  pero se invalida si cambiás la contraseña de Facebook, revocás permisos,
  o el user token largo subyacente caduca sin uso (~60 días sin
  renovarlo). Recomendado: re-generar cada ~60 días, o implementar el
  flujo OAuth (hito I.10) que automatiza el refresco.
- **Borrar media (`#10 Insufficient permissions`):** el token de prueba no
  tiene permiso para `DELETE /{ig-media-id}`. El **código de borrado
  funciona** (el smoke test reportó el error de Meta correctamente); es
  cuestión de agregar el scope adecuado y/o pasar el App Review de Meta.
- **`appsecret_proof`:** si en la app activás *"Require app secret proof
  for server API calls"*, hay que mandar `appsecret_proof` (HMAC del token
  con el app secret) en cada llamada. Hoy el cliente no lo manda — avisá y
  se agrega en un commit.
- **Modo desarrollo vs. producción:** en modo desarrollo la app funciona
  para cuentas que tengan un rol en la app. Para publicar en cuentas de
  terceros hace falta el **App Review** de Meta para
  `instagram_content_publish`, `instagram_manage_comments`, etc.
- **Requisitos de la imagen:** Meta exige JPEG público, ancho mínimo
  ~320px y relación de aspecto entre 4:5 y 1.91:1 para el feed.

---

## 9. Cómo conectan los clientes (arquitectura)

La cuenta de IG **siempre** tiene que ser **Profesional (Business o
Creator)** — es gratis e instantáneo desde la app de Instagram
(*Configuración → Tipo de cuenta y herramientas → Cambiar a profesional*).
Eso es requisito de la API de publicación en cualquier flujo.

A partir de ahí hay 3 formas de conectar (planificadas en el hito I.10):

| Flujo | ¿Página de FB? | Publicar | Comentarios | **Borrar media** |
|---|---|---|---|---|
| **Facebook Login** | **requerida** | ✅ | ✅ | ✅ |
| **Instagram Login** | **no** | ✅ | ✅ | ❌ (manual desde la app) |
| **Manual / avanzado** (pegar token) | n/a | ✅ | ✅ | según el token |

> **Verificado (mayo 2026, docs de Meta):** `DELETE /{ig-media-id}` *"solo
> admite la API de Instagram con inicio de sesión con Facebook"*. Con
> Instagram Login se puede publicar y moderar comentarios, pero **no
> borrar** media por API.

### Vincular IG a una Página de Facebook (solo para Facebook Login)
1. Tener una **Página de Facebook** (creala gratis si no tenés).
2. App de Instagram → *Configuración → Cuenta → Compartir en otras apps →
   Facebook* → vincular la Página. (O desde la Página en FB →
   *Configuración → Cuentas vinculadas → Instagram*.)
3. Ser **admin** de esa Página.

### Para TUS cuentas: System User token (permanente)
Si la cuenta es tuya (o un cliente te da acceso de socio), lo más estable
es un **token de Usuario del Sistema** del Business Manager con
*Caducidad: Nunca* (ver pregunta frecuente). No depende de la sesión de
una persona. Se carga por el **modo avanzado** (pegar token).

### Para clientes (auto-servicio): OAuth (Facebook o Instagram Login)
El cliente toca "Conectar Instagram", se loguea **una vez**, autoriza, y
nuestro backend guarda un token de larga duración. No re-autoriza cada 60
días salvo que revoque permisos o cambie la contraseña. **Una sola app de
Meta** (en Live + App Review) sirve a todos los clientes — no crean su
propia app.
