"""F9 · Vectores de EmbeddingGemma 2 para el experimento.

Corre en un entorno aparte (no en el de la app): torch CPU +
sentence-transformers >= 6.1. Carga solo la parte de texto del modelo.

    python embeddinggemma_vectores.py datos.json gemma.json [float32|bfloat16]

Guarda los vectores completos de 768 dimensiones; el recorte a 512/256/128
(con renormalización) lo hace ``embeddinggemma_evaluar.py``.

Variantes de prefijo (ficha del modelo, sección "Task Instruction Prefixes"):

* comentarios y disparadores (simétrico): ``SentenceSimilarity``,
  ``Classification`` y sin prefijo, para ver cuánto pesa;
* centro de ayuda (asimétrico): consulta con ``SearchQuery`` o
  ``QuestionAnswering``; artículo como ``title: {t} | text: {c}`` y
  términos generados como ``title: none | text: {term}``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import torch
from sentence_transformers import SentenceTransformer

MODEL = "google/embeddinggemma-2"


def main(datos_path: str, out_path: str, dtype_name: str = "float32") -> None:
    datos = json.loads(Path(datos_path).read_text(encoding="utf-8"))
    openai = json.loads(
        (Path(out_path).parent / "openai.json").read_text(encoding="utf-8")
    )
    dtype = {"float32": torch.float32, "bfloat16": torch.bfloat16}[dtype_name]
    model = SentenceTransformer(
        MODEL,
        device="cpu",
        model_kwargs={"torch_dtype": dtype},
        config_kwargs={"vision_config": None, "audio_config": None},
    )
    prompts = model.prompts

    def enc(texts: list[str], prompt: str) -> dict[str, list[float]]:
        vecs = model.encode(
            [prompt + t for t in texts],
            batch_size=16,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return {t: v.astype("float32").tolist() for t, v in zip(texts, vecs)}

    short = [t["text"] for t in datos["triggers"]] + [
        c["text"] for c in datos["comments"]
    ]
    queries = [q["text"] for q in datos["queries"]]
    terms = sorted({t for ts in openai["terms"].values() for t in ts})

    out: dict[str, dict[str, list[float]]] = {
        "sts": enc(short, prompts["SentenceSimilarity"]),
        "clf": enc(short, prompts["Classification"]),
        "raw": enc(short, ""),
        "q_search": enc(queries, prompts["SearchQuery"]),
        "q_qa": enc(queries, prompts["QuestionAnswering"]),
        "doc_terms": enc(terms, prompts["Document"]),
    }
    arts = model.encode(
        [f"title: {a['title']} | text: {a['content']}" for a in datos["articles"]],
        batch_size=8,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    out["doc_articles"] = {
        a["id"]: v.astype("float32").tolist()
        for a, v in zip(datos["articles"], arts)
    }
    Path(out_path).write_text(json.dumps(out), encoding="utf-8")
    print("listo", {k: len(v) for k, v in out.items()})


if __name__ == "__main__":
    main(*sys.argv[1:])
