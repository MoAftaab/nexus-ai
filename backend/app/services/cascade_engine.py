"""NetworkX dependency graph and Monte-Carlo cascade propagation."""
from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Any

import networkx as nx


@dataclass
class CascadeSimulation:
    trials: int
    propagation_probability: float
    expected_impact: int
    p90_impact: int
    reached_outcomes: list[str]


class CascadeEngine:
    def __init__(self, seed: int):
        self.seed = seed

    def build(self, anomaly) -> nx.DiGraph:
        graph = nx.DiGraph(anomaly_id=anomaly.id)
        for node in anomaly.cascade_nodes:
            graph.add_node(node.id, **node.model_dump())
        for edge in anomaly.cascade_edges:
            graph.add_edge(edge.source, edge.target, probability=edge.probability / 100, label=edge.label)
        return graph

    def simulate(self, anomaly, trials: int = 1_000) -> CascadeSimulation:
        graph = self.build(anomaly)
        if not graph.nodes:
            return CascadeSimulation(trials=trials, propagation_probability=0, expected_impact=0, p90_impact=0, reached_outcomes=[])
        rng = random.Random(f"{self.seed}:{anomaly.id}:{trials}")
        roots = [node for node in graph.nodes if graph.in_degree(node) == 0]
        impacts: list[int] = []
        reached_outcomes: set[str] = set()
        propagated = 0
        for _ in range(trials):
            reached = set(roots)
            queue = list(roots)
            while queue:
                source = queue.pop(0)
                for _, target, payload in graph.out_edges(source, data=True):
                    if target not in reached and rng.random() <= payload["probability"]:
                        reached.add(target); queue.append(target)
            outcome_nodes = [node for node in reached if graph.nodes[node].get("kind") == "outcome"]
            trial_impact = sum(int(graph.nodes[node].get("impact", 0)) for node in outcome_nodes)
            impacts.append(trial_impact)
            if trial_impact:
                propagated += 1; reached_outcomes.update(outcome_nodes)
        impacts.sort()
        return CascadeSimulation(trials=trials, propagation_probability=round(propagated / trials, 4), expected_impact=round(sum(impacts) / trials), p90_impact=impacts[min(len(impacts) - 1, int(trials * .9))], reached_outcomes=sorted(reached_outcomes))

    def payload(self, anomaly) -> dict[str, Any]:
        graph = self.build(anomaly)
        simulation = self.simulate(anomaly)
        nodes = [{**payload, "id": node_id, "anomaly_id": anomaly.id} for node_id, payload in graph.nodes(data=True)]
        edges = [{"source": source, "target": target, "label": payload["label"], "probability": round(payload["probability"] * 100)} for source, target, payload in graph.edges(data=True)]
        return {"nodes": nodes, "edges": edges, "anomaly_id": anomaly.id, "simulation": {"trials": simulation.trials, "propagation_probability": simulation.propagation_probability, "expected_impact": simulation.expected_impact, "p90_impact": simulation.p90_impact, "reached_outcomes": simulation.reached_outcomes}}

    def simulate_whatif(self, anomaly, action) -> dict[str, Any]:
        """Compare the cascade with and without a control applied virtually.

        Applying a control cuts each edge's propagation probability by the
        control's stated confidence (a 98%-confidence source correction leaves
        2% residual risk on every hop), so the counterfactual stays tied to the
        same Monte-Carlo machinery as the headline simulation.
        """
        baseline = self.simulate(anomaly)
        residual = 1 - (action.confidence / 100)
        damped = anomaly.model_copy(deep=True)
        for edge in damped.cascade_edges:
            edge.probability = max(1, round(edge.probability * residual))
        mitigated = self.simulate(damped)
        return {
            "anomaly_id": anomaly.id,
            "action": {"id": action.id, "title": action.title, "owner": action.owner, "eta": action.eta, "confidence": action.confidence},
            "baseline": {"propagation_probability": baseline.propagation_probability, "expected_impact": baseline.expected_impact, "p90_impact": baseline.p90_impact},
            "mitigated": {"propagation_probability": mitigated.propagation_probability, "expected_impact": mitigated.expected_impact, "p90_impact": mitigated.p90_impact},
            "expected_impact_avoided": baseline.expected_impact - mitigated.expected_impact,
            "edges": [{"source": edge.source, "target": edge.target, "probability": edge.probability} for edge in damped.cascade_edges],
        }

