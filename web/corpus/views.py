from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from .helpers import score_query
from .models import Expert, Run


def _run(request):
    name = request.GET.get("run")
    if name:
        return Run.objects.filter(name=name).first()
    return Run.objects.first()


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
