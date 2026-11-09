"""F9 · Comparación OpenAI vs EmbeddingGemma 2 sobre los mismos pares.

    python embeddinggemma_evaluar.py datos.json openai.json gemma.json resultados.json

Solo usa numpy. Distancia = 1 - coseno, igual que ``cosine_distance`` de
pgvector, para que los umbrales salgan en la misma escala que
``DEFAULT_MATCH_MAX_DISTANCE``.

Respuestas automáticas: cada comentario se compara contra todos los
disparadores y se toma el más cercano (como ``_semantic_match``). Con un
umbral ``t`` se responde si la distancia es <= t.

* precisión = respuestas correctas / respuestas dadas
* cobertura = respuestas correctas / comentarios que tenían respuesta
* equivocadas = respuestas dadas que no correspondían (incluye contestarle
  a un comentario que no tenía respuesta)

Centro de ayuda: se ordenan los artículos por la mejor similitud entre la
consulta y sus vectores (términos generados, como ``vector_search``, o el
artículo entero) y se mide acierto@1, @3, @5 y MRR. Las consultas sin
artículo sirven para medir un corte mínimo de similitud, que hoy no existe.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

DIMS = (768, 512, 256, 128)
OPENAI_ACTUAL = 0.55
MIN_PRECISION = 0.97


def norm(m: np.ndarray, dim: int | None = None) -> np.ndarray:
    if dim is not None:
        m = m[:, :dim]
    return m / np.linalg.norm(m, axis=1, keepdims=True)


def mat(store: dict[str, list[float]], keys: list[str], dim: int | None) -> np.ndarray:
    return norm(np.array([store[k] for k in keys], dtype=np.float64), dim)


# --- respuestas automáticas -------------------------------------------------


def autoreply(datos: dict, store: dict, dim: int | None) -> dict:
    trig_ids = [t["id"] for t in datos["triggers"]]
    T = mat(store, [t["text"] for t in datos["triggers"]], dim)
    C = mat(store, [c["text"] for c in datos["comments"]], dim)
    dist = 1 - C @ T.T
    nearest = dist.argmin(axis=1)
    nd = dist[np.arange(len(C)), nearest]
    labels = [c["trigger"] for c in datos["comments"]]
    pos = np.array([lab is not None for lab in labels])
    right = np.array(
        [lab is not None and trig_ids[n] == lab for lab, n in zip(labels, nearest)]
    )
    correct_d = np.array(
        [dist[i, trig_ids.index(lab)] for i, lab in enumerate(labels) if lab]
    )

    def at(t: float) -> dict:
        answered = nd <= t
        ok = int((answered & right).sum())
        n = int(answered.sum())
        return {
            "umbral": round(float(t), 3),
            "respondidos": n,
            "correctos": ok,
            "equivocados": n - ok,
            "equivocados_a_comentarios_sin_respuesta": int((answered & ~pos).sum()),
            "precision": round(ok / n, 3) if n else 1.0,
            "cobertura": round(ok / int(pos.sum()), 3),
        }

    grid = np.round(np.arange(0.0, 1.2, 0.005), 3)
    curve = [at(t) for t in grid]
    ok_curve = [c for c in curve if c["precision"] >= MIN_PRECISION]
    best = max(ok_curve, key=lambda c: (c["cobertura"], -c["umbral"]))
    # El umbral recomendado queda en el medio del tramo con la mejor
    # cobertura, no pegado al borde donde empieza a equivocarse.
    tramo = [
        c["umbral"]
        for c in ok_curve
        if c["cobertura"] == best["cobertura"] and c["equivocados"] == best["equivocados"]
    ]
    rec = round((min(tramo) + max(tramo)) / 2, 2)
    return {
        "techo_cobertura": round(float(right[pos].mean()), 3),
        "dist_correcta": pct(correct_d),
        "dist_mas_cercana_sin_respuesta": pct(nd[~pos]),
        "tramo_mejor": [min(tramo), max(tramo)],
        "umbral_recomendado": at(rec),
        "en_055": at(OPENAI_ACTUAL),
        "curva": curve,
        "detalle": [
            {
                "comentario": c["text"],
                "esperado": c["trigger"],
                "mas_cercano": trig_ids[n],
                "distancia": round(float(d), 3),
                "origen": c["origen"],
            }
            for c, n, d in zip(datos["comments"], nearest, nd)
        ],
    }


def pct(x: np.ndarray) -> dict:
    q = np.percentile(x, [0, 5, 50, 95, 100])
    return dict(zip(("min", "p5", "p50", "p95", "max"), (round(float(v), 3) for v in q)))


# --- centro de ayuda --------------------------------------------------------


def helpcenter(
    datos: dict,
    qstore: dict,
    docs: list[tuple[str, list[float]]],
    dim: int | None,
) -> dict:
    art_ids = [a["id"] for a in datos["articles"]]
    owners = [d[0] for d in docs]
    D = norm(np.array([d[1] for d in docs], dtype=np.float64), dim)
    Q = mat(qstore, [q["text"] for q in datos["queries"]], dim)
    sim = Q @ D.T
    # Mejor similitud por artículo (varios términos por artículo).
    per_art = np.full((len(Q), len(art_ids)), -1.0)
    for j, owner in enumerate(owners):
        k = art_ids.index(owner)
        per_art[:, k] = np.maximum(per_art[:, k], sim[:, j])
    order = np.argsort(-per_art, axis=1)
    top1 = per_art.max(axis=1)
    hits = {1: [], 3: [], 5: []}
    rr = []
    inscope = []
    for i, q in enumerate(datos["queries"]):
        if q["article"] is None:
            inscope.append(False)
            continue
        inscope.append(True)
        rank = list(order[i]).index(art_ids.index(q["article"])) + 1
        for k in hits:
            hits[k].append(rank <= k)
        rr.append(1 / rank)
    inscope = np.array(inscope)
    right1 = np.array(
        [
            q["article"] is not None and art_ids[order[i][0]] == q["article"]
            for i, q in enumerate(datos["queries"])
        ]
    )

    # Corte mínimo de similitud: mostrar resultados solo si el mejor supera s.
    def at(s: float) -> dict:
        shown = top1 >= s
        return {
            "corte": round(float(s), 3),
            "acierto1_con_corte": round(float((shown & right1)[inscope].mean()), 3),
            "consultas_con_articulo_sin_resultados": int((~shown & inscope).sum()),
            "consultas_fuera_de_tema_con_resultados": int((shown & ~inscope).sum()),
        }

    cuts = [at(s) for s in np.round(np.arange(0.1, 0.9, 0.01), 2)]
    n_out = int((~inscope).sum())
    # Corte que deja afuera al menos la mitad de lo fuera de tema perdiendo
    # lo menos posible de lo que sí tiene artículo.
    cand = [c for c in cuts if c["consultas_fuera_de_tema_con_resultados"] <= n_out // 2]
    best_cut = max(cand, key=lambda c: (c["acierto1_con_corte"], -c["corte"])) if cand else None
    return {
        "acierto@1": round(float(np.mean(hits[1])), 3),
        "acierto@3": round(float(np.mean(hits[3])), 3),
        "acierto@5": round(float(np.mean(hits[5])), 3),
        "mrr": round(float(np.mean(rr)), 3),
        "sim_top1_con_articulo": pct(top1[inscope]),
        "sim_top1_fuera_de_tema": pct(top1[~inscope]),
        "corte_sugerido": best_cut,
        "fallos@1": [
            {
                "consulta": q["text"],
                "esperado": q["article"],
                "devolvio": art_ids[order[i][0]],
                "sim": round(float(top1[i]), 3),
            }
            for i, q in enumerate(datos["queries"])
            if q["article"] is not None and not right1[i]
        ],
    }


def main(datos_p: str, openai_p: str, gemma_p: str, out_p: str) -> None:
    datos = json.loads(Path(datos_p).read_text(encoding="utf-8"))
    oa = json.loads(Path(openai_p).read_text(encoding="utf-8"))
    gm = json.loads(Path(gemma_p).read_text(encoding="utf-8"))
    ov = oa["vectors"]
    terms = oa["terms"]

    res: dict = {"autorespuesta": {}, "centro_de_ayuda": {}}
    res["autorespuesta"]["openai_1536"] = autoreply(datos, ov, None)
    for variant in ("sts", "clf", "raw"):
        for dim in DIMS:
            res["autorespuesta"][f"gemma_{variant}_{dim}"] = autoreply(
                datos, gm[variant], dim
            )

    oa_terms = [(a, ov[t]) for a, ts in terms.items() for t in ts]
    oa_arts = [
        (a["id"], ov[f"{a['title']}\n{a['content']}"]) for a in datos["articles"]
    ]
    gm_terms = [(a, gm["doc_terms"][t]) for a, ts in terms.items() for t in ts]
    gm_arts = list(gm["doc_articles"].items())
    hc = res["centro_de_ayuda"]
    hc["openai_1536_terminos"] = helpcenter(datos, ov, oa_terms, None)
    hc["openai_1536_articulo"] = helpcenter(datos, ov, oa_arts, None)
    for qv in ("q_search", "q_qa"):
        for dim in DIMS:
            hc[f"gemma_{qv}_terminos_{dim}"] = helpcenter(datos, gm[qv], gm_terms, dim)
            hc[f"gemma_{qv}_articulo_{dim}"] = helpcenter(datos, gm[qv], gm_arts, dim)
            hc[f"gemma_{qv}_ambos_{dim}"] = helpcenter(
                datos, gm[qv], gm_terms + gm_arts, dim
            )

    Path(out_p).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")

    print("== Respuestas automáticas (umbral recomendado, precisión >= %.2f)" % MIN_PRECISION)
    print("modelo | techo | tramo | umbral | prec | cob | equiv | en 0.55 prec/cob/equiv")
    for k, v in res["autorespuesta"].items():
        r, a = v["umbral_recomendado"], v["en_055"]
        print(
            f"{k} | {v['techo_cobertura']} | {v['tramo_mejor']} | {r['umbral']} | "
            f"{r['precision']} | {r['cobertura']} | {r['equivocados']} | "
            f"{a['precision']}/{a['cobertura']}/{a['equivocados']}"
        )
    print("\n== Centro de ayuda")
    print("modelo | @1 | @3 | @5 | MRR | top1 con art p5/p50 | fuera de tema p50/max | corte")
    for k, v in hc.items():
        c = v["corte_sugerido"]
        print(
            f"{k} | {v['acierto@1']} | {v['acierto@3']} | {v['acierto@5']} | {v['mrr']} | "
            f"{v['sim_top1_con_articulo']['p5']}/{v['sim_top1_con_articulo']['p50']} | "
            f"{v['sim_top1_fuera_de_tema']['p50']}/{v['sim_top1_fuera_de_tema']['max']} | "
            f"{c}"
        )


if __name__ == "__main__":
    main(*sys.argv[1:])
