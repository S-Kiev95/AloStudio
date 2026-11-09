# F9 · EmbeddingGemma 2 en lugar de OpenAI: medición

Rama experimental `exp/embeddinggemma` (cortada de `develop` el 2026-11-09).
No toca `develop`, `main` ni CTC. Mediciones en el VPS de develop
(`vmi3426238`).

## Resumen y recomendación

**Recomiendo reemplazar, con dimensión 768**, en dos pasos y con las dos
columnas conviviendo (plan al final). Conviene empezar por el centro de ayuda,
donde la ganancia es clara, y después pasar las respuestas automáticas, que
quedan al mismo nivel que con OpenAI.

| | OpenAI hoy | EmbeddingGemma 2 (propuesto) |
|---|---|---|
| Centro de ayuda, acierto en el 1.º resultado | 62,7 % (términos de gpt-4o) | **76,5 %** (artículo entero) |
| Centro de ayuda, acierto en los 5 resultados | 92,2 % | **94,1 %** |
| Autorespuesta, umbral | 0,55 | **0,15** (prefijo `Classification`) |
| Autorespuesta, precisión con ese umbral | 86,0 % (8 respuestas equivocadas) | **97,1 %** (1 equivocada) |
| Autorespuesta, cobertura con ese umbral | 68,1 % | 45,8 % |
| Autorespuesta sin ningún error | cobertura 33,3 % (umbral 0,37) | cobertura **41,7 %** (umbral 0,13) |
| RAM | 0 (servicio externo) | 1,8 GB, con un pico de 2,0 GB (solo texto, float32) |
| Tiempo por texto | red | ~0,27–0,29 s en CPU |
| Costo | por uso, más gpt-4o por artículo | 0 |

Con el umbral de 0,55, OpenAI responde más comentarios, pero en este conjunto
contesta mal 8 de 57, y 3 de esos 8 no tenían que recibir respuesta. Si se
comparan los dos modelos con la misma exigencia, quedan parejos:

- sin errores, Gemma cubre más (41,7 % contra 33,3 %);
- con un error, OpenAI cubre algo más (54,2 % en 0,46, contra 51,4 % de Gemma en 0,16).

Con 72 comentarios positivos, una diferencia de 1 o 2 comentarios es ruido.

**Dimensión:** 768. La de 256 da números casi iguales, pero con cientos o
miles de filas el espacio no pesa. Además, 768 es la dimensión nativa y la
misma que usaría el índice multimedia de F9, así que no hace falta recortar y
renormalizar en el código. La de 128 pierde calidad y no conviene.

**Precisión numérica:** `float32`. Este CPU no tiene instrucciones bf16
nativas (no tiene AVX512-BF16 ni AMX). Con `bfloat16` la RAM baja a la mitad,
pero cada texto tarda entre 1,3 y 4 veces más. `float16` no se probó porque
la ficha del modelo lo prohíbe.

**El ahorro de plata es chico y no es el motivo principal.**
`text-embedding-3-small` cuesta centavos por millón de tokens. Lo que sí
cuesta es la llamada a gpt-4o que genera los términos de cada artículo del
centro de ayuda, y la propuesta la elimina, porque el artículo entero
vectorizado con Gemma busca mejor. Las otras ventajas son tres:

- funciona sin clave de OpenAI;
- los textos de los clientes no salen del servidor;
- deja preparado el terreno para la búsqueda multimedia de F9.

## 1. Recursos en el VPS de develop

**Entorno:** 6 vCPU con AVX2, sin GPU y con 11,7 GB de RAM (8,5 GB
disponibles al medir), compartidos con las otras apps del servidor. Las
librerías fueron torch 2.15.0+cpu, transformers 5.22.2 y
sentence-transformers 6.2.0, en un entorno aparte
(`~/pruebas/embeddinggemma`, no en el de la app). Los procesos corrieron con
`systemd-run --user --scope -p MemoryMax=…` y `nice -n 10`.

**Datos medidos:**

- latencia: 60 comentarios y 40 consultas de a uno, más los 23 artículos, después de una llamada de calentamiento;
- lote: 100 comentarios.

Script: `scripts/experimentos/embeddinggemma_recursos.py`. Datos crudos:
`scripts/experimentos/resultados/embeddinggemma_recursos.jsonl`.

| Configuración | Parámetros | Carga | RAM tras cargar | RAM pico | Comentario p50 / p95 | Consulta p50 / p95 | Artículo p50 | Lote |
|---|---|---|---|---|---|---|---|---|
| float32, solo texto, 6 hilos | 271 M | 14,2 s | 1 782 MB | 1 992 MB | 267 / 1 069 ms | 229 / 794 ms | 492 ms | 14,3 textos/s |
| float32, solo texto, 2 hilos | 271 M | 13,7 s | 1 782 MB | 1 991 MB | 290 / 730 ms | 286 / 732 ms | 519 ms | 12,6 textos/s |
| float32, solo texto, 1 hilo | 271 M | 14,8 s | 1 782 MB | 1 991 MB | 278 / 379 ms | 276 / 359 ms | 610 ms | 7,4 textos/s |
| bfloat16, solo texto, 6 hilos | 271 M | 13,9 s | 761 MB | 1 150 MB | 362 / 731 ms | 377 / 1 036 ms | 1 473 ms | 3,3 textos/s |
| float32, completo (texto, imagen y audio), límite de 3 GB | 744 M | — | — | — | se cortó por memoria (OOM) | | | |
| float32, completo, límite de 5 GB | 744 M | 31,9 s | 3 512 MB | 4 411 MB | 302 / 850 ms | 354 / 755 ms | 864 ms | 8,2 textos/s |

**Lecturas:**

- **Solo texto entra holgado:** unos 2 GB con un límite de 2,5 GB. El modelo
  completo, en cambio, pide unos 4,5 GB. Con eso entra en develop, pero es
  justo para un servidor compartido. Para la parte multimedia de F9 hay que
  medir aparte cada servidor de cliente.
- **Con 2 hilos ya alcanza.** Un comentario o una consulta tardan unos 0,3 s
  y casi no mejoran con más hilos. Los p95 altos con 6 hilos se deben a que
  el VPS es compartido.
- **Cargar el modelo tarda unos 14 s.** Por eso no se puede cargar en cada
  pedido: tiene que vivir en un proceso que quede levantado.
- No hizo falta medir `multilingual-e5-small` ni `bge-m3`, porque EmbeddingGemma
  2 entra en memoria.

## 2. Umbrales

### Método

**Datos de develop (cuenta de pruebas):**

- los 2 disparadores de autorespuesta reales: "Hacen envios al interior" y
  "Tienen becas?";
- los 12 comentarios reales de primer nivel: 8 con respuesta esperada y 4 de
  prueba sin respuesta.

Develop **no tiene artículos** en el centro de ayuda (0 filas en `articles`).
Como esos datos no alcanzan para fijar un umbral, armé un conjunto ampliado,
etiquetado a mano, en `scripts/experimentos/embeddinggemma_datos.json`. Cada
fila dice si su origen es `real` o `sintetico`.

- **Respuestas automáticas:**
  - 12 disparadores: los 2 reales y 10 preguntas típicas de un instituto,
    como costo, cuotas, inscripción, horarios o requisitos. A propósito hay
    pares parecidos, como costo y cuotas o inscripción y requisitos.
  - 100 comentarios: 72 deberían recibir respuesta (8 reales) y 28 no
    (4 reales). Están escritos como en Instagram: sin tildes, con faltas,
    emojis, menciones, elogios y preguntas fuera del catálogo.
- **Centro de ayuda:**
  - 23 artículos tomados de las secciones del Manual de AloStudio de CTC
    (capacitación del 11/11);
  - 66 consultas: 51 tienen un artículo correcto y 15 están fuera de tema,
    como "cómo conecto TikTok" o "receta de torta".

Los vectores de OpenAI se calcularon en el servidor con el mismo código de
producción (`app.core.llm.embed_text` y `generate_search_terms`). La clave
salió del `.env` y no se escribió en la base. Los de Gemma se calcularon con
la parte de texto del modelo, en `float32`, con los prefijos de la ficha:

- **Comentarios y disparadores (simétrico):**
  - `task: sentence similarity | query: …` (`SentenceSimilarity`, el que
    recomienda la ficha para similitud);
  - `task: classification | query: …` (`Classification`);
  - sin prefijo.
- **Centro de ayuda (asimétrico):**
  - consultas con `task: search result | query: …` o
    `task: question answering | query: …`;
  - artículos como `title: {título} | text: {contenido}`;
  - términos generados como `title: none | text: {término}`.

La distancia es `1 − coseno`, igual que `cosine_distance` de pgvector. Así
los umbrales quedan en la misma escala que `DEFAULT_MATCH_MAX_DISTANCE`. La
evaluación imita `_semantic_match`: busca el disparador más cercano y
responde si la distancia es menor o igual al umbral.

- **Precisión:** respuestas correctas sobre respuestas dadas.
- **Cobertura:** respuestas correctas sobre comentarios que tenían respuesta.
- **Respuesta equivocada:** una respuesta con el disparador incorrecto, o una
  respuesta a un comentario que no la necesitaba.

Script: `scripts/experimentos/embeddinggemma_evaluar.py`. Detalle por
comentario y curvas completas en
`scripts/experimentos/resultados/embeddinggemma_resultados.json`.

### 2a. Respuestas automáticas a comentarios

**Distancias de cada modelo:** las de Gemma salen mucho más comprimidas que
las de OpenAI. Por eso el 0,55 actual, aplicado a Gemma, respondería todo
(47 errores), y **el umbral tiene que depender del modelo**.

| Modelo | Distancia al disparador correcto (p5 / p50 / p95) | Distancia al más cercano en comentarios sin respuesta (mín / p50) | El más cercano es el correcto |
|---|---|---|---|
| OpenAI 1536 | 0,212 / 0,430 / 0,670 | 0,502 / 0,677 | 81,9 % |
| Gemma `Classification` 768 | 0,056 / 0,158 / 0,266 | 0,166 / 0,243 | 80,6 % |
| Gemma `SentenceSimilarity` 768 | 0,038 / 0,106 / 0,168 | 0,115 / 0,178 | 73,6 % |
| Gemma sin prefijo 768 | 0,070 / 0,166 / 0,261 | 0,155 / 0,233 | 72,2 % |

**Prefijo:** el de `Classification` separa mejor que `SentenceSimilarity`,
aunque la ficha sugiere este último para similitud. Sin prefijo da el peor
resultado.

**Cobertura según cuántos errores se toleran (los 100 comentarios):**

| Modelo | 0 errores | 1 error | 2 errores | 3 errores |
|---|---|---|---|---|
| OpenAI 1536 | 33,3 % (umbral 0,365–0,37) | 54,2 % (0,45–0,46) | 62,5 % (0,50) | 65,3 % (0,505) |
| Gemma `Classification` 768 | **41,7 %** (0,13–0,135) | 51,4 % (0,16) | 51,4 % | 56,9 % (0,175) |
| Gemma `Classification` 512 | 41,7 % (0,13–0,135) | 50,0 % (0,155) | 51,4 % (0,16) | 56,9 % (0,17–0,175) |
| Gemma `Classification` 256 | 40,3 % (0,12–0,125) | 51,4 % (0,15) | 54,2 % (0,16) | 56,9 % (0,165) |
| Gemma `SentenceSimilarity` 768 | 12,5 % | 29,2 % | 41,7 % | 45,8 % |

**Umbrales posibles:**

| Umbral | Respondidos | Correctos | Equivocados (a comentarios sin respuesta) | Precisión | Cobertura |
|---|---|---|---|---|---|
| OpenAI 0,55 (actual) | 57 | 49 | 8 (3) | 86,0 % | 68,1 % |
| OpenAI 0,46 | 40 | 39 | 1 (0) | 97,5 % | 54,2 % |
| OpenAI 0,37 | 24 | 24 | 0 | 100 % | 33,3 % |
| **Gemma `Classification` 768 · 0,15 (propuesto)** | 34 | 33 | 1 (0) | **97,1 %** | 45,8 % |
| Gemma `Classification` 768 · 0,13 (conservador) | 30 | 30 | 0 | 100 % | 41,7 % |
| Gemma `Classification` 768 · 0,16 | 38 | 37 | 1 (0) | 97,4 % | 51,4 % |
| Gemma `Classification` 768 · 0,18 | 45 | 41 | 4 (1) | 91,1 % | 56,9 % |

**Comentarios reales solos (8 con respuesta y 4 sin):**

| Modelo y umbral | Cobertura | Errores |
|---|---|---|
| OpenAI 0,55 | 87,5 % | 0 |
| Gemma 0,15 | 87,5 % | 0 |
| Gemma `SentenceSimilarity` 0,12 | 100 % | 0 |

Con los dos modelos se escapa la misma palabra suelta, "Beca": con OpenAI
queda en 0,586 y con Gemma en 0,157. Con Gemma, todos los comentarios reales
con respuesta quedan en 0,157 o menos, y los de prueba en 0,204 o más.

**Propuesta:** 0,15 para Gemma con el prefijo `Classification`. Queda dentro
del tramo seguro: hasta 0,16 el único error es "hay examen de ingreso?", que
el modelo asocia a becas, y desde 0,165 empiezan a sumarse errores
(4 en 0,18).

**Hallazgo aparte:** con este conjunto, el 0,55 actual de OpenAI ya es
demasiado flojo. Contesta "tienen estacionamiento?" y "estan contratando
docentes?" con la respuesta de becas, y "se suspenden las clases por la
lluvia?" con la de horarios. Si OpenAI se queda un tiempo más, conviene bajar
su umbral a 0,46.

**Qué falla en los dos modelos:**

- El disparador corto "Tienen becas?" atrae preguntas vagas como "oferta
  educativa 2027?", "necesito tener el liceo terminado?" o "esta habilitado
  por el MEC?".
- También se confunden pares cercanos, como costo y cuotas, o inscripción y
  requisitos.

Los dos problemas se arreglan cargando varias frases de ejemplo por
respuesta, algo que el diseño ya permite. No se arreglan con el umbral.

### 2b. Centro de ayuda

**Cómo funciona hoy:** gpt-4o genera términos de búsqueda para cada
artículo, se vectoriza cada término y la consulta se compara contra esos
términos. Hoy no hay umbral: siempre se muestran los 5 más cercanos.

**Qué se midió:** acierto en el primer resultado (@1), en los tres primeros
(@3) y en los cinco que se muestran (@5), sobre las 51 consultas que tienen
artículo.

| Modelo y qué se vectoriza | @1 | @3 | @5 | MRR |
|---|---|---|---|---|
| OpenAI 1536, términos de gpt-4o (**producción**) | 62,7 % | 86,3 % | 92,2 % | 0,765 |
| OpenAI 1536, artículo entero | 82,4 % | 94,1 % | 94,1 % | 0,885 |
| Gemma 768, `SearchQuery` contra términos | 66,7 % | 88,2 % | 94,1 % | 0,775 |
| **Gemma 768, `SearchQuery` contra artículo entero** | **76,5 %** | **90,2 %** | **94,1 %** | **0,843** |
| Gemma 512, `SearchQuery` contra artículo | 74,5 % | 90,2 % | 94,1 % | 0,830 |
| Gemma 256, `SearchQuery` contra artículo | 76,5 % | 90,2 % | 96,1 % | 0,844 |
| Gemma 128, `SearchQuery` contra artículo | 68,6 % | 84,3 % | 94,1 % | 0,788 |
| Gemma 768, `QuestionAnswering` contra artículo | 72,5 % | 90,2 % | 96,1 % | 0,822 |

**Resultados:**

- Gemma sobre el artículo entero le gana a lo que hoy corre en producción
  (+13,8 puntos en @1) y no necesita gpt-4o.
- OpenAI sobre el artículo entero sería todavía mejor en @1, pero sigue
  siendo pago y externo.
- Los términos generados empeoran los dos modelos con estos artículos.
- Mezclar términos y artículo da lo mismo que usar solo términos, porque las
  similitudes de los términos son más altas y tapan a las del artículo.

**Corte mínimo, opcional y nuevo:** hoy la búsqueda siempre devuelve algo.
Con Gemma 768 (`SearchQuery` contra artículo), un corte de similitud de
**0,67** (distancia de 0,33):

- no deja sin resultados a ninguna de las 51 consultas con artículo;
- elimina los resultados de 10 de las 15 consultas fuera de tema.

Es un cambio de comportamiento visible, así que lo dejo como opción y no como
parte del reemplazo.

**Límites de la medición:**

- El conjunto es chico. Los positivos de autorespuesta y todas las consultas
  del centro de ayuda los escribí yo: imitan comentarios reales, pero no lo
  son.
- Los umbrales propuestos son un punto de partida para el período de sombra
  del plan, no un valor definitivo.
- Antes de cambiar en CTC, hay que repetir la medición con los comentarios
  reales que se junten en ese período.

## 3. Plan de migración sin cortar a los clientes

**Principios del plan:**

- Todo cambio de esquema es aditivo.
- El modelo y la escala de distancia se guardan con cada vector.
- La lectura cambia por bandera, cuenta por cuenta.
- Volver atrás es cambiar una bandera.

### 3.1. Servicio de embeddings

Un proceso aparte (`alostudio-embeddings.service`) carga EmbeddingGemma 2
una sola vez, solo la parte de texto y en `float32`. Atiende en `127.0.0.1`
y corre con:

- `MemoryMax=2.5G`;
- `CPUWeight` bajo y `Nice=10`;
- `torch.set_num_threads(2)`.

La API y el worker lo llaman por HTTP. Así ninguno de los dos paga los 2 GB
ni los 14 s de carga. La función `embed_text` de `app/core/llm.py` pasa a
tomar el proveedor de la configuración (`EMBEDDING_PROVIDER=openai|gemma`) y
recibe un tipo de tarea (`clasificacion`, `consulta` o `documento`), para
poner el prefijo correcto. La ruta de OpenAI queda igual.

### 3.2. Columnas nuevas (migración de Alembic, solo agrega)

- **`instagram_comment_replies`:** `embedding_gemma vector(768)`, que puede
  quedar vacía.
- **`article_embeddings`:** `embedding_gemma vector(768)`, que puede quedar
  vacía, y `model`, de texto.
  - Con Gemma se guarda una fila por artículo (o por fragmento, si el
    artículo es largo) con `term` = título.
  - Las filas de términos de gpt-4o se dejan como están hasta el final.
- No se tocan `embedding vector(1536)` ni los datos que ya existen.

### 3.3. Escritura doble

Mientras dura la migración, cada alta o edición de una respuesta preparada,
y cada `reindex_article`, calcula los dos vectores: OpenAI en la columna
vieja y Gemma en la nueva.

- Si falla uno, se registra el error y queda vacía solo esa columna, como hoy.
- Ningún pedido queda bloqueado por el servicio nuevo, porque todo va por la
  cola ARQ, como el reindexado actual.

### 3.4. Backfill

Una tarea ARQ, `backfill_gemma_embeddings`, por cuenta y en lotes de 32:

- toma solo las filas con `embedding_gemma IS NULL` y sigue de a lotes, así
  que se puede cortar y retomar;
- corre con prioridad baja.

Al ritmo medido (unos 12 textos/s con 2 hilos), 10 000 filas tardan unos
15 minutos. Un comando de `scripts/` la encola para una cuenta o para todas,
y muestra cuántas faltan.

### 3.5. Umbrales por modelo

`DEFAULT_MATCH_MAX_DISTANCE` pasa a ser un mapa por modelo:
`{"openai": 0.55, "gemma": 0.15}`. Si OpenAI sigue un tiempo, conviene bajar
su valor a 0,46.

> **Atención: dato guardado.** `instagram_post_autoreplies.max_distance`
> guarda umbrales por regla **en la escala de OpenAI**. En develop, la regla
> 3 tiene `0.55`. Ese valor no se puede leer igual con Gemma, porque
> respondería todo. Propuesta, a confirmar con el dueño antes de tocar el
> dato:
>
> - Agregar `max_distance_gemma`, vacía al principio. Si está vacía, se usa
>   el 0,15 general.
> - No convertir los valores viejos automáticamente.
> - Antes del cambio, listar las reglas con un `max_distance` propio para
>   revisarlas una por una.
>
> La validación del formulario (`MIN_MATCH_DISTANCE = 0.05`,
> `MAX_MATCH_DISTANCE = 1.0`) y el texto de ayuda de la interfaz también
> tienen que depender del modelo.

### 3.6. Sombra

Con la bandera de lectura todavía en OpenAI, `_semantic_match` calcula
también la decisión de Gemma y registra las diferencias, sin publicar nada:

```
autoreply.shadow  account_id  openai=(trigger, dist)  gemma=(trigger, dist)  coinciden
```

Lo mismo para el centro de ayuda: se registra el top 5 de cada modelo.

1. Correr 1 o 2 semanas en develop y después en CTC.
2. Con los comentarios reales que se junten, repetir `embeddinggemma_evaluar.py`.
3. Confirmar el 0,15 o corregirlo.

### 3.7. Cambio por cuenta

Una bandera por cuenta, `embedding_read_model`, que puede ser `openai` o
`gemma`:

1. develop;
2. la cuenta de pruebas de CTC;
3. CTC.

Para volver atrás alcanza con poner la bandera en `openai`. La columna vieja
sigue al día mientras dure la escritura doble.

### 3.8. Cierre

Con todas las cuentas en Gemma y unas semanas sin volver atrás:

1. cortar la escritura en OpenAI y la generación de términos con gpt-4o;
2. en una migración aparte, borrar `embedding vector(1536)` y las filas de
   términos;
3. agregar un índice HNSW sobre `embedding_gemma` cuando el volumen lo
   justifique. Hoy hay pocas filas por cuenta y no hace falta.

## Cómo repetir la medición

En el VPS, desde un entorno aparte con
`torch` (CPU), `torchvision`, `pillow`, `sentence-transformers>=6.1`,
`transformers`, `numpy` y `psutil`:

```bash
# 1. OpenAI (código y .env de la app; no escribe en la base)
cd ~/AloStudio && PYTHONPATH=. .venv/bin/python \
  <ruta>/embeddinggemma_openai.py <ruta>/embeddinggemma_datos.json <salida>/openai.json
# 2. Gemma (lee openai.json de la misma carpeta para reusar los términos)
systemd-run --user --scope -p MemoryMax=3G nice -n 10 \
  .venv/bin/python embeddinggemma_vectores.py embeddinggemma_datos.json <salida>/gemma.json float32
# 3. Recursos
systemd-run --user --scope -p MemoryMax=3G nice -n 10 \
  .venv/bin/python embeddinggemma_recursos.py embeddinggemma_datos.json float32 texto 2
# 4. Comparación
.venv/bin/python embeddinggemma_evaluar.py embeddinggemma_datos.json openai.json gemma.json resultados.json
```

**Archivos que no se commitean:** `openai.json` y `gemma.json` (los
vectores) quedaron en `~/pruebas/embeddinggemma/` en el VPS.

**Costo de la corrida en OpenAI:** 408 textos vectorizados y 23 llamadas de
generación de términos, unos centavos de dólar.
