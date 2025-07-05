import random
import numpy as np
import networkx as nx
from collections import defaultdict
from config import config


class GeneticAlgorithm:
    """
    Mengimplementasikan Algoritma Genetika untuk membuat komunitas fog node
    berdasarkan paper FSPCN.
    """

    def __init__(
        self, network_graph, population_size=50, generations=100, mutation_rate=0.1
    ):
        self.network = network_graph
        self.fog_nodes = [
            n for n, d in network_graph.nodes(data=True) if d.get("type") != "CLOUD"
        ]
        self.num_nodes = len(self.fog_nodes)

        self.population_size = population_size
        self.generations = generations
        self.mutation_rate = mutation_rate

        self.population = self._initialize_population()
        self._calculate_total_resources()

    def _initialize_population(self):
        population = []
        for _ in range(self.population_size):
            chromosome = [
                random.randint(0, config.NOMINAL_COMMUNITIES - 1)
                for _ in range(self.num_nodes)
            ]
            population.append(chromosome)
        return population

    def _calculate_total_resources(self):
        self.total_ram = sum(
            d.get("RAM", 0)
            for _, d in self.network.nodes(data=True)
            if d.get("type") != "CLOUD"
        )
        self.total_ipt = sum(
            d.get("IPT", 0)
            for _, d in self.network.nodes(data=True)
            if d.get("type") != "CLOUD"
        )
        self.total_tb = sum(
            d.get("TB", 0)
            for _, d in self.network.nodes(data=True)
            if d.get("type") != "CLOUD"
        )
        self.total_bw = sum(d.get("BW", 0) for _, _, d in self.network.edges(data=True))
        self.total_pd = sum(d.get("PR", 0) for _, _, d in self.network.edges(data=True))

    def _get_communities_from_chromosome(self, chromosome):
        communities = defaultdict(list)
        for node_idx, community_id in enumerate(chromosome):
            node_id = self.fog_nodes[node_idx]
            communities[community_id].append(node_id)
        return dict(communities)

    def _calculate_fitness(self, chromosome):
        communities_map = self._get_communities_from_chromosome(chromosome)
        valid_communities = {
            cid: nodes for cid, nodes in communities_map.items() if nodes
        }
        if not valid_communities:
            return 0

        penalty_factor = 1.0
        final_communities = {}
        for cid, nodes in valid_communities.items():
            subgraph = self.network.subgraph(nodes)
            if not nx.is_connected(subgraph):
                penalty_factor = config.PENALTY_FACTOR
                if not subgraph.nodes():
                    continue
                largest_cc = max(nx.connected_components(subgraph), key=len)
                final_communities[cid] = list(largest_cc)
            else:
                final_communities[cid] = nodes

        num_communities = len(final_communities)
        if num_communities == 0:
            return 0

        resource_ratios = []
        for cid, nodes in final_communities.items():
            comm_ram = sum(self.network.nodes[n].get("RAM", 0) for n in nodes)
            comm_ipt = sum(self.network.nodes[n].get("IPT", 0) for n in nodes)
            comm_tb = sum(self.network.nodes[n].get("TB", 0) for n in nodes)
            subgraph_links = self.network.subgraph(nodes).edges(data=True)
            comm_bw = sum(d.get("BW", 0) for _, _, d in subgraph_links)
            comm_pd = sum(d.get("PR", 0) for _, _, d in subgraph_links)
            ratios = {
                "RAM": comm_ram / self.total_ram if self.total_ram > 0 else 0,
                "IPT": comm_ipt / self.total_ipt if self.total_ipt > 0 else 0,
                "TB": comm_tb / self.total_tb if self.total_tb > 0 else 0,
                "BW": comm_bw / self.total_bw if self.total_bw > 0 else 0,
                "PD": comm_pd / self.total_pd if self.total_pd > 0 else 0,
            }
            resource_ratios.append(ratios)

        alpha_sum = sum(
            config.WEIGHTS_RESOURCES["RAM"] * r["RAM"]
            + config.WEIGHTS_RESOURCES["TB"] * r["TB"]
            + config.WEIGHTS_RESOURCES["IPT"] * r["IPT"]
            + config.WEIGHTS_RESOURCES["BW"] * r["BW"]
            + config.WEIGHTS_RESOURCES["PD"] * (1 - r["PD"])
            for r in resource_ratios
        )
        alpha = (
            alpha_sum / (num_communities * penalty_factor) if num_communities > 0 else 0
        )

        variances = {
            key: np.std([r[key] for r in resource_ratios]) if resource_ratios else 0
            for key in config.WEIGHTS_VARIANCES
        }
        beta = sum(
            config.WEIGHTS_VARIANCES[key] * (1 - variances[key])
            for key in config.WEIGHTS_VARIANCES
        )

        gamma_sum = sum(
            len(nodes) / len(valid_communities.get(cid, []))
            if valid_communities.get(cid)
            else 0
            for cid, nodes in final_communities.items()
        )
        gamma = (
            gamma_sum / (num_communities * penalty_factor) if num_communities > 0 else 0
        )

        ideal_bc_size = self.num_nodes / num_communities if num_communities > 0 else 1
        phi_sum = sum(
            (len(nodes) / ideal_bc_size) for nodes in final_communities.values()
        )
        phi = phi_sum / (num_communities * penalty_factor) if num_communities > 0 else 0

        total_used_nodes = sum(len(nodes) for nodes in final_communities.values())
        theta = total_used_nodes / self.num_nodes if self.num_nodes > 0 else 0

        term1 = config.LAMBDA1 * alpha + config.LAMBDA2 * beta + config.LAMBDA3 * gamma
        fitness = config.W1 * term1 + config.W2 * phi + config.W3 * theta
        return fitness

    def _selection(self, fitness_scores):
        sorted_population = [
            x
            for _, x in sorted(
                zip(fitness_scores, self.population),
                key=lambda pair: pair[0],
                reverse=True,
            )
        ]
        num_parents = int(self.population_size * 0.5)
        return sorted_population[:num_parents]

    def _crossover(self, parent1, parent2):
        size = len(parent1)
        div = config.CROSSOVER_DIV_PARAMETER
        range1_start, range1_end = size // div, (size * 2) // div
        range2_start, range2_end = (size * (div - 2)) // div, (size * (div - 1)) // div
        p1 = random.randint(range1_start, range1_end)
        p2 = random.randint(range2_start, range2_end)
        if p1 > p2:
            p1, p2 = p2, p1
        child1 = parent1[:p1] + parent2[p1:p2] + parent1[p2:]
        child2 = parent2[:p1] + parent1[p1:p2] + parent2[p2:]
        return child1, child2

    def _mutation(self, chromosome):
        if random.random() < self.mutation_rate:
            point = random.randint(0, len(chromosome) - 1)
            new_value = random.randint(0, config.NOMINAL_COMMUNITIES - 1)
            chromosome[point] = new_value
        return chromosome

    def run(self):
        print("Memulai Algoritma Genetika untuk pembuatan komunitas...")
        best_fitness_overall = -1
        best_chromosome_overall = None
        for gen in range(self.generations):
            fitness_scores = [
                self._calculate_fitness(chromo) for chromo in self.population
            ]
            best_fitness_current_gen = max(fitness_scores)
            avg_fitness_current_gen = np.mean(fitness_scores)
            if best_fitness_current_gen > best_fitness_overall:
                best_fitness_overall = best_fitness_current_gen
                best_chromosome_overall = self.population[np.argmax(fitness_scores)]
            if (gen + 1) % 10 == 0 or gen == 0:
                print(
                    f"Generasi {gen + 1: >4}/{self.generations} -> Fitness Terbaik: {best_fitness_current_gen:.4f} | Rata-rata Fitness: {avg_fitness_current_gen:.4f}"
                )
            parents = self._selection(fitness_scores)
            offspring = []
            while len(offspring) < self.population_size - len(parents):
                p1, p2 = random.sample(parents, 2)
                c1, c2 = self._crossover(p1, p2)
                offspring.append(self._mutation(c1))
                if len(offspring) < self.population_size - len(parents):
                    offspring.append(self._mutation(c2))
            self.population = parents + offspring
        print(
            f"\nAlgoritma Genetika selesai. Fitness terbaik: {best_fitness_overall:.4f}"
        )
        return self._get_communities_from_chromosome(best_chromosome_overall)
