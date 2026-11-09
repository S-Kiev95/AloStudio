"""F9 · Vectores de OpenAI para el experimento EmbeddingGemma.

Usa el mismo camino que producción (``app.core.llm.embed_text`` y
``generate_search_terms``), así que la clave sale del ``.env`` del servidor y
nunca pasa por la terminal. Solo hace llamadas HTTP: no escribe en la base.

Correr desde la raíz del repo del servidor (para que lea ``.env``):

    cd ~/AloStudio && .venv/bin/python <ruta>/embeddinggemma_openai.py \
        <ruta>/embeddinggemma_datos.json <salida>/openai.json

Salida: ``{"vectors": {texto: [1536 floats]}, "terms": {articulo: [...]}}``.
Si la salida ya existe, reusa lo calculado (no paga dos veces).
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from app.core.llm import embed_text, generate_search_terms


async def main(datos_path: str, out_path: str) -> None:
    datos = json.loads(Path(datos_path).read_text(encoding="utf-8"))
    out = Path(out_path)
    cache = (
        json.loads(out.read_text(encoding="utf-8"))
        if out.exists()
        else {"vectors": {}, "terms": {}}
    )

    # Términos de búsqueda por artículo, como hace reindex_article.
    for art in datos["articles"]:
        if art["id"] not in cache["terms"]:
            cache["terms"][art["id"]] = await generate_search_terms(
                title=art["title"], description=None, content=art["content"]
            )
            print(f"terminos {art['id']}: {len(cache['terms'][art['id']])}")

    texts: list[str] = []
    texts += [t["text"] for t in datos["triggers"]]
    texts += [c["text"] for c in datos["comments"]]
    texts += [q["text"] for q in datos["queries"]]
    texts += [f"{a['title']}\n{a['content']}" for a in datos["articles"]]
    for terms in cache["terms"].values():
        texts += terms

    pending = [t for t in dict.fromkeys(texts) if t not in cache["vectors"]]
    print(f"textos a vectorizar: {len(pending)}")
    for i, text in enumerate(pending, 1):
        cache["vectors"][text] = await embed_text(text)
        if i % 50 == 0:
            out.write_text(json.dumps(cache), encoding="utf-8")
            print(f"  {i}/{len(pending)}")
    out.write_text(json.dumps(cache), encoding="utf-8")
    print("listo")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2]))
