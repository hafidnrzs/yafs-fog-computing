import networkx as nx
import random
import matplotlib.pyplot as plt

# --- Konfigurasi Dasar ---
NUM_COMMUNITIES = 10

# --- Parameter Fitness Function ---
omega_1 = 0.4  # Resource usage
omega_2 = 0.25  # Node distribution between communities
omega_3 = 0.35  # Whole node usage

lambda_1 = 0.35  # Resource usage in community
lambda_2 = 0.15  # Resource usage variance
lambda_3 = 0.15  # Node usage in community

# --- Weight of Resources ---
w_RAM = 0.20  # Weight of RAM
w_TB = 0.20  # Weight of Storage
w_IPT = 0.25  # Weight of CPU

# --- Other Parameters ---
PF = 0.0001  # Penalty factor

# --- 1. Algoritma Genetika ---
def genetic_algorithm(graph, num_communities, population_size=50, generations=100, mutation_rate=0.1):
    """
    Algoritma genetika untuk menentukan komunitas node dalam graf.
    :param graph: Graf NetworkX.
    :param num_communities: Jumlah komunitas yang diinginkan.
    :param population_size: Ukuran populasi.
    :param generations: Jumlah generasi.
    :param mutation_rate: Probabilitas mutasi.
    :return: Kromosom terbaik (list komunitas untuk setiap node).
    """
    def initialize_population():
        population = []
        for _ in range(population_size):
            chromosome = [random.randint(1, num_communities) for _ in range(len(graph.nodes))]
            population.append(chromosome)
        return population

    def fitness_function(chromosome):
        community_counts = {i: 0 for i in range(1, num_communities + 1)}
        for community_id in chromosome:
            community_counts[community_id] += 1
        variance = sum((count - (len(chromosome) / num_communities))**2 for count in community_counts.values())

        resource_usage = sum(
            graph.nodes[node].get('RAM', 0) * w_RAM +
            graph.nodes[node].get('STO', 0) * w_TB +
            graph.nodes[node].get('IPT', 0) * w_IPT
            for node in graph.nodes
        )

        fitness = (
            omega_1 * resource_usage +
            omega_2 * variance +
            omega_3 * len(set(chromosome))  # Jumlah komunitas unik
        )
        return -fitness  # Minimalkan fitness

    def selection(population, fitness_values):
        total_fitness = sum(fitness_values)
        probabilities = [f / total_fitness for f in fitness_values]
        selected = random.choices(population, weights=probabilities, k=2)
        return selected

    def crossover(parent1, parent2):
        point = random.randint(1, len(parent1) - 1)
        child1 = parent1[:point] + parent2[point:]
        child2 = parent2[:point] + parent1[point:]
        return child1, child2

    def mutate(chromosome):
        for i in range(len(chromosome)):
            if random.random() < mutation_rate:
                chromosome[i] = random.randint(1, num_communities)

    population = initialize_population()
    best_chromosome = None
    best_fitness = float('-inf')

    for generation in range(generations):
        fitness_values = [fitness_function(chromosome) for chromosome in population]
        if max(fitness_values) > best_fitness:
            best_fitness = max(fitness_values)
            best_chromosome = population[fitness_values.index(best_fitness)]

        #print(f"Generation {generation}: Best Fitness = {best_fitness}")

        new_population = []
        for _ in range(population_size // 2):
            parent1, parent2 = selection(population, fitness_values)
            child1, child2 = crossover(parent1, parent2)
            mutate(child1)
            mutate(child2)
            new_population.extend([child1, child2])
        population = new_population

    return best_chromosome
# --- 2. Fungsi untuk Menghitung Fitness ---
def calculate_fitness(graph, communities):
    """
    Menghitung fitness dari komunitas yang diberikan.
    :param graph: Graf NetworkX.
    :param communities: List komunitas untuk setiap node.
    :return: Nilai fitness.
    """
    resource_usage = 0
    node_distribution = {i: 0 for i in range(1, NUM_COMMUNITIES + 1)}
    node_usage = {i: 0 for i in range(1, NUM_COMMUNITIES + 1)}

    for node, community_id in enumerate(communities):
        node_data = graph.nodes[node]
        resource_usage += (
            node_data.get('RAM', 0) * w_RAM +
            node_data.get('STO', 0) * w_TB +
            node_data.get('IPT', 0) * w_IPT
        )
        node_distribution[community_id] += 1
        node_usage[community_id] += (
            node_data.get('RAM', 0) * w_RAM +
            node_data.get('STO', 0) * w_TB +
            node_data.get('IPT', 0) * w_IPT
        )

    # Hitung fitness berdasarkan rumus yang diberikan
    fitness = (
        omega_1 * resource_usage +
        omega_2 * sum((count - (len(communities) / NUM_COMMUNITIES))**2 for count in node_distribution.values()) +
        omega_3 * sum(node_usage.values())
    )
    return -fitness  # Minimalkan fitness
