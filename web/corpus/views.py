import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from .helpers import predict_next, score_chars, score_query
from .models import Expert, Run


def _run(request):
    name = request.GET.get("run")
    if name:
        return Run.objects.filter(name=name).first()
    return Run.objects.order_by("-id").first()   # default to the most recently imported


def atlas(request):
    run = _run(request)
    experts = run.experts.all() if run else []
    return render(request, "corpus/atlas.html", {
        "run": run, "experts": experts, "runs": Run.objects.all(),
    })


def territory(request, pk):
    expert = get_object_or_404(Expert, pk=pk)
    return render(request, "corpus/territory.html", {
        "run": expert.run, "e": expert,
        "passages": expert.passages.all(),
        "neighbors": expert.neighbors(),
    })


def query(request):
    run = _run(request)
    q = request.GET.get("q", "").strip()
    ranked = score_query(run, q) if (run and q) else []
    winner = ranked[0][1] if ranked else None
    rows = [{"bpb": b, "e": e} for b, e in ranked[:10]]
    return render(request, "corpus/query.html", {
        "run": run, "q": q, "rows": rows, "winner": winner,
        "winner_bpb": ranked[0][0] if ranked else None,
        "neighbors": winner.neighbors() if winner else [],
    })


def graph_view(request):
    run = _run(request)
    return render(request, "corpus/graph.html", {"run": run})


def graph_json(request):
    run = _run(request)
    if not run:
        return JsonResponse({"nodes": [], "edges": []})
    nodes = [{
        "id": e.expert_id, "pk": e.pk,
        "label": e.label or f"expert {e.expert_id}",
        "group": e.label or "—",
        "value": max(1, e.n_owned),
        "title": ", ".join(e.term_list[:8]),
    } for e in run.experts.all()]
    edges = [{"from": ed.src.expert_id, "to": ed.dst.expert_id, "value": ed.weight}
             for ed in run.edges.select_related("src", "dst").all()]
    return JsonResponse({"nodes": nodes, "edges": edges})


def overview(request):
    """Dashboard: summary + the GA learning curve (Chart.js)."""
    run = _run(request)
    hist = list(run.history.all()) if run else []
    chart = {
        "gen": [h.gen for h in hist],
        "coverage": [round(h.coverage_bpb, 4) for h in hist],
        "owners": [h.n_owners for h in hist],
    }
    return render(request, "corpus/overview.html", {
        "run": run, "runs": Run.objects.all(),
        "chart_json": json.dumps(chart),
        "n_gens": len(hist),
        "top_experts": run.experts.all()[:12] if run else [],
    })


def heatmap(request):
    """Live per-character surprisal: type text, see it coloured by how surprised
    the chosen (or auto-routed) expert is — the model 'reading'."""
    run = _run(request)
    text = request.GET.get("text", "")
    pk = request.GET.get("expert")
    experts = list(run.experts.all()) if run else []
    expert = None
    if run and text.strip():
        if pk:
            expert = get_object_or_404(Expert, pk=pk, run=run)
        else:                                   # auto-route to the best-fit expert
            ranked = score_query(run, text)
            expert = ranked[0][1] if ranked else (experts[0] if experts else None)
    cells = score_chars(run, expert, text) if expert else []
    mean = round(sum(c["bpb"] for c in cells) / len(cells), 2) if cells else None
    return render(request, "corpus/heatmap.html", {
        "run": run, "experts": experts, "text": text, "expert": expert,
        "cells": cells, "mean": mean, "sel_pk": int(pk) if pk else None,
    })


def predict(request):
    """Live next-byte prediction: type a context, see the model's distribution
    over the next character as a bar chart — 'watch the LM predict'."""
    run = _run(request)
    text = request.GET.get("text", "the ")
    pk = request.GET.get("expert")
    experts = list(run.experts.all()) if run else []
    expert = None
    if run and experts:
        if pk:
            expert = get_object_or_404(Expert, pk=pk, run=run)
        elif text.strip():                      # auto-route on the context
            ranked = score_query(run, text)
            expert = ranked[0][1] if ranked else experts[0]
        else:
            expert = experts[0]
    preds = predict_next(run, expert, text) if expert else []
    return render(request, "corpus/predict.html", {
        "run": run, "experts": experts, "text": text, "expert": expert,
        "preds_json": json.dumps(preds), "sel_pk": int(pk) if pk else None,
    })
