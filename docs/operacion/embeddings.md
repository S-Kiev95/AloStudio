# Embeddings locales (EmbeddingGemma 2)

Migración aprobada por el dueño el 2026-11-09 (F9 de
`PLAN.fases-futuras.md`). La medición y la recomendación están en
`docs/experimentos/embeddinggemma.md`.

## Qué cambia

Los embeddings se usan en dos lugares: las respuestas automáticas a
comentarios de Instagram y la búsqueda del centro de ayuda. Hasta ahora los
calculaba OpenAI (`text-embedding-3-small`). Con esta migración también los
calcula EmbeddingGemma 2, un modelo gratis que corre en el servidor.

- **Dos modelos conviviendo:** mientras estén configurados los dos, cada
  guardado escribe los dos vectores. El de OpenAI va en la columna
  `vector(1536)` de siempre y el local en `embedding_gemma vector(768)`.
- **Cada cuenta lee con un modelo:** se elige con
  `accounts.internal_attributes.embedding_read_model`. Si la cuenta no lo
  tiene, se usa `EMBEDDING_READ_MODEL` del `.env`, que por defecto es
  `openai`.
- **Volver atrás es cambiar la bandera:** la columna de OpenAI sigue al día
  mientras haya escritura doble.
- **Umbrales separados por modelo:** las distancias de los dos modelos no
  son comparables. En las reglas, `max_distance` es de OpenAI y
  `max_distance_gemma` es del modelo local.
  - El modelo local usa 0,15 por defecto. En el formulario, Exigente es
    0,13, Equilibrada 0,15 y Amplia 0,18.
  - **Los valores de OpenAI no se convierten:** las reglas con un umbral
    propio se revisan una por una con el dueño antes de pasar la cuenta.
  - Editar el umbral de un modelo no toca el del otro.
- **Centro de ayuda:** el modelo local indexa el artículo entero (título y
  texto), sin la llamada a gpt-4o que generaba los términos.
- **Modo sombra** (`EMBEDDING_SHADOW=true`): además del modelo que
  responde, corre el otro y registra si habrían coincidido. Nunca cambia lo
  que se publica.

## Componentes

| Pieza | Dónde |
|---|---|
| Servicio con el modelo (127.0.0.1:8100, solo texto, `float32`, 2 hilos, `MemoryMax=2560M`) | `app/embeddings_service/`, unidad `ops/embeddings/alostudio-embeddings.service` |
| Cliente y elección de modelo por cuenta | `app/core/embeddings.py` |
| Migración (columnas nuevas, solo agrega) | `alembic/versions/6a7b8c9d0e1f_embedding_gemma.py` |
| Backfill (tarea ARQ, por lotes de 32, se puede retomar) | `app/workers/embeddings_backfill.py` |
| Operación: estado, backfill, cambio de modelo | `scripts/embeddings_gemma.py` |

El servicio corre en un entorno virtual propio (`.venv-embeddings`): torch
no entra al `.venv` de la app. Escucha solo en localhost y no guarda datos.

## Puesta en marcha en un servidor

1. Correr la migración. Es la misma de siempre y solo agrega columnas:

   ```bash
   cd ~/AloStudio && .venv/bin/alembic upgrade head
   ```

2. Instalar el servicio. Lo hace el script, y la primera vez descarga el
   modelo (unos 1,5 GB):

   ```bash
   bash ops/embeddings/instalar.sh
   ```

3. Agregar al `.env` (no son secretos):

   ```
   EMBEDDINGS_SERVICE_URL=http://127.0.0.1:8100
   EMBEDDING_SHADOW=true
   ```

4. Reiniciar el backend y el worker.

5. Completar los vectores que faltan y revisar el estado:

   ```bash
   PYTHONPATH=. .venv/bin/python scripts/embeddings_gemma.py backfill
   PYTHONPATH=. .venv/bin/python scripts/embeddings_gemma.py estado
   ```

**Memoria:** el servicio usa unos 2 GB. Antes de instalarlo en un servidor
de cliente, confirmar que tiene ese margen libre.

## Período de sombra (1 a 2 semanas)

Con las cuentas todavía en `openai` y `EMBEDDING_SHADOW=true`, cada
comentario que llega a una regla por similitud deja una línea en el log del
backend (la decisión se toma al recibir el webhook):

```
instagram.autoreply.shadow account_id=… comment=… reading=openai openai=(answer=12 semantic_match 0.4123) gemma=(answer=12 semantic_match 0.1102) same_decision=True
```

Lo mismo pasa con las búsquedas del centro de ayuda. Esas líneas solo
llevan ids de artículos, nunca el texto buscado:

```
portals.search.shadow portal_id=… reading=openai openai=[3, 7] gemma=[3, 9] same_top1=True
```

Para contarlas:

```bash
grep -c "autoreply.shadow" ~/logs/backend.log
grep "autoreply.shadow" ~/logs/backend.log | grep -c "same_decision=False"
```

En los casos con `same_decision=False`, mirar el comentario en AloStudio
para ver cuál de los dos modelos acertó. Si el 0,15 tiene que moverse, se
cambia `DEFAULT_MATCH_MAX_DISTANCE_GEMMA` (o el umbral de una regla) antes
de pasar la cuenta.

## Pasar una cuenta al modelo local

1. Revisar `estado`: tiene que mostrar todos los vectores locales
   completos, y conviene revisar con el dueño las reglas marcadas con
   "revisar".
2. Cambiar la cuenta:

   ```bash
   PYTHONPATH=. .venv/bin/python scripts/embeddings_gemma.py modelo <ID> gemma
   ```

   El formulario de reglas pasa a mostrar la escala del modelo local.

3. **Volver atrás:**

   ```bash
   PYTHONPATH=. .venv/bin/python scripts/embeddings_gemma.py modelo <ID> openai
   ```

**Orden:** develop, después la cuenta de pruebas de CTC y por último CTC.
CTC solo cuando lo pida el dueño.

## Cierre (más adelante, aparte)

Con todas las cuentas en Gemma y unas semanas sin volver atrás:

1. dejar de escribir en OpenAI (sacar la clave o dejar de llamar a
   `embed_text` al guardar);
2. en otra migración, borrar las columnas `vector(1536)` y las filas de
   términos de gpt-4o;
3. agregar un índice HNSW sobre `embedding_gemma` si el volumen lo pide.
