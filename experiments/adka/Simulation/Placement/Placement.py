import random
import numpy as np

def ga_service_placement(graph, services, population_size=30, generations=50, mutation_rate=0.1):
    """
    Placement service ke node menggunakan Genetic Algorithm.
    :param graph: NetworkX graph (topology)
    :param services: List of dict, tiap dict berisi info service (name, RAM, IPT, dll)
    :return: Dict mapping service_name -> node_name (placement terbaik)
    """
    all_nodes = list(graph.nodes())
    num_services = len(services)

    # --- Helper: Evaluasi fitness kromosom ---
    def fitness(chromosome):
        # chromosome: list of node index, length = num_services
        node_resources = {n: {'RAM': graph.nodes[n].get('RAM', 0), 'IPT': graph.nodes[n].get('IPT', 0)} for n in all_nodes}
        penalty = 0
        for idx, node_idx in enumerate(chromosome):
            node = all_nodes[node_idx]
            svc = services[idx]
            # Penalti jika resource tidak cukup
            if node_resources[node]['RAM'] < svc.get('RAM', 0) or node_resources[node]['IPT'] < svc.get('IPT', 0):
                penalty += 1000
            else:
                node_resources[node]['RAM'] -= svc.get('RAM', 0)
                node_resources[node]['IPT'] -= svc.get('IPT', 0)
        # Contoh: fitness = -penalty (semakin kecil penalty, semakin baik)
        return -penalty

    # --- Inisialisasi populasi ---
    population = [np.random.randint(0, len(all_nodes), size=num_services).tolist() for _ in range(population_size)]

    for gen in range(generations):
        # Evaluasi fitness
        fitness_scores = [fitness(chrom) for chrom in population]
        # Seleksi (roulette wheel)
        fitness_arr = np.array(fitness_scores)
        probs = (fitness_arr - fitness_arr.min() + 1e-6)  # biar positif
        probs = probs / probs.sum()
        selected_idx = np.random.choice(len(population), size=population_size, p=probs)
        selected = [population[i] for i in selected_idx]

        # Crossover
        next_gen = []
        for i in range(0, population_size, 2):
            parent1 = selected[i]
            parent2 = selected[(i+1) % population_size]
            cut = random.randint(1, num_services-1)
            child1 = parent1[:cut] + parent2[cut:]
            child2 = parent2[:cut] + parent1[cut:]
            next_gen.extend([child1, child2])

        # Mutasi
        for chrom in next_gen:
            if random.random() < mutation_rate:
                idx = random.randint(0, num_services-1)
                chrom[idx] = random.randint(0, len(all_nodes)-1)

        # Elitism: keep best
        best_idx = int(np.argmax(fitness_scores))
        next_gen[0] = population[best_idx][:]

        population = next_gen[:population_size]

    # Ambil solusi terbaik
    best_chrom = population[np.argmax([fitness(chrom) for chrom in population])]
    placement = {services[i]['name']: all_nodes[best_chrom[i]] for i in range(num_services)}
    return placement

def apply_placement_to_graph(graph, placement):
    """
    Menandai node pada graph dengan service yang ditempatkan.
    :param graph: Graf NetworkX.
    :param placement: Dict mapping service_name -> node_name.
    """
    for service, node in placement.items():
        if node is not None:
            if 'services' not in graph.nodes[node]:
                graph.nodes[node]['services'] = []
            graph.nodes[node]['services'].append(service)