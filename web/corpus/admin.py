from django.contrib import admin

from .models import Edge, Expert, Passage, Run


@admin.register(Run)
class RunAdmin(admin.ModelAdmin):
    list_display = ("name", "n_experts", "coverage_bpb", "run_dir")


@admin.register(Expert)
class ExpertAdmin(admin.ModelAdmin):
    list_display = ("expert_id", "run", "label", "n_owned", "marginal", "orders")
    list_filter = ("run", "label")
    search_fields = ("terms", "sample", "label")


@admin.register(Passage)
class PassageAdmin(admin.ModelAdmin):
    list_display = ("expert",)


@admin.register(Edge)
class EdgeAdmin(admin.ModelAdmin):
    list_display = ("run", "src", "dst", "weight")
