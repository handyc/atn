from django.urls import path

from . import views

urlpatterns = [
    path("", views.atlas, name="atlas"),
    path("query/", views.query, name="query"),
    path("graph/", views.graph_view, name="graph"),
    path("api/graph.json", views.graph_json, name="graph_json"),
    path("expert/<int:pk>/", views.territory, name="territory"),
]
