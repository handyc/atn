"""Schema for a built atn-ga population (a "run").

These are Django *models* in the database sense — tables describing the
population. The actual n-gram "brains" stay as files on disk under the run
directory; we store metadata about them and shell out to the atn binary for
live scoring (see helpers.score_query).
"""
import os

from django.db import models


class Run(models.Model):
    """One evolved population over one corpus."""
    name = models.CharField(max_length=200, unique=True)
    run_dir = models.CharField(max_length=500, help_text="absolute path to the run output dir")
    atn_path = models.CharField(max_length=500, help_text="absolute path to the atn binary")
    corpus_path = models.CharField(max_length=500, blank=True)
    coverage_bpb = models.FloatField(default=0.0)
    config_json = models.TextField(blank=True)

    def __str__(self):
        return self.name

    @property
    def n_experts(self):
        return self.experts.count()


class Expert(models.Model):
    """A surviving expert: a cheap n-gram brain specialised on one territory."""
    run = models.ForeignKey(Run, related_name="experts", on_delete=models.CASCADE)
    expert_id = models.IntegerField()
    brain_path = models.CharField(max_length=300, help_text="relative to run.run_dir")
    mapbits = models.IntegerField(default=22)
    orders = models.CharField(max_length=40, default="2,4,7")
    marginal = models.FloatField(default=0.0)
    n_owned = models.IntegerField(default=0)
    centroid = models.FloatField(default=0.0)         # fractional position in corpus
    pos_lo = models.FloatField(default=0.0)
    pos_hi = models.FloatField(default=0.0)
    label = models.CharField(max_length=60, blank=True)   # guessed language/topic
    terms = models.TextField(blank=True)              # comma-joined distinctive words
    sample = models.TextField(blank=True)

    class Meta:
        ordering = ["-n_owned", "expert_id"]
        unique_together = [("run", "expert_id")]

    def __str__(self):
        return f"expert {self.expert_id} — {self.label or 'territory'}"

    @property
    def brain_abspath(self):
        return os.path.join(self.run.run_dir, self.brain_path)

    @property
    def term_list(self):
        return [t for t in self.terms.split(",") if t]

    def neighbors(self):
        """Related experts via the routing graph, strongest edge first."""
        return [e.dst for e in self.out_edges.select_related("dst").order_by("-weight")]


class Passage(models.Model):
    """A sample passage drawn from an expert's training territory."""
    expert = models.ForeignKey(Expert, related_name="passages", on_delete=models.CASCADE)
    text = models.TextField()


class Edge(models.Model):
    """A directed routing-graph edge between experts (fallback / co-activation)."""
    run = models.ForeignKey(Run, related_name="edges", on_delete=models.CASCADE)
    src = models.ForeignKey(Expert, related_name="out_edges", on_delete=models.CASCADE)
    dst = models.ForeignKey(Expert, related_name="in_edges", on_delete=models.CASCADE)
    weight = models.IntegerField(default=1)
