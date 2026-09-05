# Pendientes de AloStudio

Lista viva de mejoras, ordenada por lo que cuesta no hacerlas. Cada punto
lleva la evidencia con la que se levantó — si no hay medición, lo dice.

Medido el 2026-09-04 contra staging (`vmi3426238`), cuenta 1, con datos
reales: 257 conversaciones, 1.157 mensajes, 295 contactos.

---

## 1. Carga anticipada indiscriminada — MEDIDO, es lo más caro

Las 33 relaciones del backend están declaradas `lazy="selectin"`. Cargar
cualquier objeto arrastra un pedazo grande del esquema, sin importar qué
se vaya a mostrar.

| Camino (25 filas) | Consultas | Tiempo |
|---|---|---|
| Lista de conversaciones | **79** | 256–396 ms |
| Mensajes de una conversación (17 filas) | **98** | 595 ms |
| Lista de contactos | 17 | 142 ms |
| Conversaciones, cargando **sólo lo que el presentador lee** | **8** | 54–74 ms |

Diez veces menos consultas y cuatro veces menos tiempo, medido tres veces.

**Por qué se dispara.** Para listar conversaciones consulta `users` 30
veces, `accounts` 15 y `account_users` 15 — nada de eso está en la
respuesta. Dos formas lo empeoran:

- **Ciclos:** `Message.conversation` es `selectin` con
  `back_populates="messages"`. Conversación → mensajes → conversación.
- **Relaciones hacia arriba:** `Message.account` y `Message.inbox`
  recargan, por cada mensaje, la misma cuenta y bandeja ya cargadas.

**No es una relación suelta.** Se probó cortar `Account.account_users`:
ahorra 3 de 79. Es la política, no un caso.

**Hecho (2026-09-04, `3f53fdb` + siguiente).** Carga explícita en los dos
caminos, con tope fijado por test:

| | antes | después |
|---|---|---|
| Lista de conversaciones (staging, 25 filas) | 79 | **13** |
| Endpoint de mensajes (20 filas, por HTTP) | 109 | **15** |

Los modelos no se tocaron: el `lazyload("*")` vale sólo para esas dos
consultas, así que todo lo demás se comporta igual que antes.

Dos cosas que aparecieron al hacerlo, y que valen para lo que falta:

- El costo del endpoint de mensajes **no estaba en los mensajes** sino en
  cargar la conversación antes. Medir la consulta suelta daba 98; medir
  el endpoint daba 109 y el arreglo de los mensajes solos apenas movía la
  aguja. Hay que medir por HTTP.
- El primer test de mensajes reconstruía la consulta con las mismas
  opciones: habría pasado con el `.options(...)` del router borrado.
  Los tests de conteo tienen que pegarle al endpoint.

**Falta**

- Aplicar lo mismo a los demás caminos: contactos (17 consultas para 25
  filas), informes, búsqueda.
- *De fondo:* invertir el default a `lazy="raise"` y declarar la carga en
  cada consulta. Correcto a largo plazo, toca muchos sitios; con `raise`
  un olvido falla en los tests y no en producción.

---

## 2. N+1 real en CSAT — HECHO (`ebe1e9e`)

Era peor de lo que decía esta nota. No eran dos consultas por fila sino
seis (contacto, conversación, y un usuario más un `account_user` por
cada uno de los dos agentes), y encima cada `session.get(Conversation)`
detonaba la cascada `selectin` detrás.

| Página de 12 respuestas | consultas |
|---|---|
| Antes | **804** |
| Después | **16** |

Y plano: 2 respuestas cuestan lo mismo que 12. Todo se trae por id, un
viaje por tabla, con `lazyload("*")` en cada lote — el presentador lee
cinco columnas planas y ninguna relación.

El test afirma la **planitud**, no un techo: una consulta por fila es la
falla, y un conteo que crece con la página es lo que la prueba, sin
depender de cuánto cueste el resto del endpoint.

---

## 3. 30 claves foráneas sin índice — HECHO (migración `b5c6d7e8f9a0`)

Postgres indexa la clave primaria y las restricciones únicas solo; las
foráneas **no**. Sin índice se degradan dos cosas a medida que las
tablas crecen: cualquier join por esa clave, y —menos evidente— cada
borrado en la fila **padre**, porque hay que escanear la tabla hija
entera para hacer cumplir la restricción.

La lista salió de consultar `pg_constraint` contra la base corriendo, no
de leer los modelos. Después de aplicarla quedan **0** foráneas sin
índice.

Se hizo ahora justamente porque todavía no duele: un `CREATE INDEX`
sobre una tabla casi vacía es gratis, y sobre un millón de filas es una
ventana de mantenimiento.

---

## 4. Cosas que se revisaron y **no** son problema

Anotadas para que nadie las vuelva a investigar:

- **`users` y `access_tokens` con decenas de miles de escaneos
  secuenciales.** Parece grave y no lo es: ambos tienen índice utilizable
  (`(uid, provider)` y `token`), y Postgres elige escaneo completo porque
  tienen 7 y 2 filas. A ese tamaño es la decisión correcta del
  planificador. Volver a mirarlo cuando las tablas crezcan.
- **Los presentadores no consultan la base.** Reciben objetos ya
  cargados; el problema está en cómo se cargan, no en cómo se presentan.
- **El worker.** Los cron están bien espaciados y con offsets pensados
  (IMAP cada 2 min desfasado del tick de 5, insights al minuto 17).
- **IO bloqueante en caminos async.** No hay.
- **3 índices sin uso** (`reporting_events`, `messages`, `contacts`):
  216 kB en total. Irrelevante; no vale una migración.

---

## 5. Producto y operación

**Urgente**

- **Contraseña de `demo@example.com`.** Sigue siendo la del seed
  (`scripts/seed_demo_account.py:26`), en una URL pública por Funnel, y
  ese usuario es hoy el operador de la instalación: puede sobrescribir
  las credenciales de Meta desde Ajustes → Instalación.
  `PYTHONPATH=. .venv/bin/python scripts/set_user_password.py demo@example.com`

**Legal / trámite**

- **Política de privacidad:** faltan la razón social real y un correo de
  contacto que exista (`frontend/lib/legal/privacy.ts`, marcados `TODO`).
  Hoy apunta a `privacidad@alostudio.app`, un dominio que no controlamos.
- **URL de eliminación de datos** de la app de Meta: quedó apuntando a
  `facebook.com` para poder publicar. App Review la mira.
- **Correo de contacto de la app sin verificar** (`contact_email_verified:
  false`).
- **Acceso Avanzado a `instagram_manage_messages`** + Verificación de
  Negocio: sin eso no se le puede escribir a alguien sin rol en la app.

**Deuda chica**

- `"You are not authorized to do this action"` sale en inglés en la
  interfaz. Es cadena de compatibilidad con Chatwoot y el backend debe
  seguir devolviéndola, pero la UI puede traducirla — ya existe
  `code: "not_authorized"` para distinguirla sin depender del texto.
- `fetch_all_email_inboxes_once` en `imap_fetch.py` duplica la tarea del
  worker y no lo usa nadie. Código muerto.
- El constructor de correo por bloques no tiene **columnas** (filas de
  dos columnas). Es lo siguiente si alguien lo pide.
- El patrón "no ofrezcas un botón que no puede funcionar" se aplicó a
  Instagram. Vale revisar los otros canales — **no verificado**.
