# Pembentukan komunitas dengan Genetic Algorithm (GA)
# - selection
# - crossover (Algoritma 1 - two point crossover)
# - mutation
# - fitness function

import networkx as nx
import random

class GACommunity:
    def __init__(self, graph, num_communities, population_size=50, generations=100, mutation_rate=0.1,
                 omega_1=1.0, omega_2=1.0, omega_3=1.0, w_RAM=1.0, w_TB=1.0, w_IPT=1.0):
        self.graph = graph
        self.num_communities = num_communities
        self.population_size = population_size
        self.generations = generations
        self.mutation_rate = mutation_rate
        self.omega_1 = omega_1
        self.omega_2 = omega_2
        self.omega_3 = omega_3
        self.w_RAM = w_RAM
        self.w_TB = w_TB
        self.w_IPT = w_IPT

    def initialize_population(self):
        population = []
        for _ in range(self.population_size):
            chromosome = [random.randint(1, self.num_communities) for _ in range(len(self.graph.nodes))]
            population.append(chromosome)
        return population

    def fitness_function(self, chromosome):
        community_counts = {i: 0 for i in range(1, self.num_communities + 1)}
        for community_id in chromosome:
            community_counts[community_id] += 1
        variance = sum((count - (len(chromosome) / self.num_communities))**2 for count in community_counts.values())

        resource_usage = sum(
            self.graph.nodes[node].get('RAM', 0) * self.w_RAM +
            self.graph.nodes[node].get('STO', 0) * self.w_TB +
            self.graph.nodes[node].get('IPT', 0) * self.w_IPT
            for node in self.graph.nodes
        )

        fitness = (
            self.omega_1 * resource_usage +
            self.omega_2 * variance +
            self.omega_3 * len(set(chromosome))  # Jumlah komunitas unik
        )
        return -fitness  # Minimalkan fitness

    def selection(self, population, fitness_values):
        # Roulette wheel selection
        min_fitness = min(fitness_values)
        shifted_fitness = [f - min_fitness + 1e-6 for f in fitness_values]  # avoid negative
        total_fitness = sum(shifted_fitness)
        probabilities = [f / total_fitness for f in shifted_fitness]
        selected = random.choices(population, weights=probabilities, k=2)
        return selected

    def crossover(self, parent1, parent2):
        # Two-point crossover
        if len(parent1) < 2:
            return parent1[:], parent2[:]
        point1 = random.randint(0, len(parent1) - 2)
        point2 = random.randint(point1 + 1, len(parent1) - 1)
        child1 = parent1[:point1] + parent2[point1:point2] + parent1[point2:]
        child2 = parent2[:point1] + parent1[point1:point2] + parent2[point2:]
        return child1, child2

    def mutate(self, chromosome):
        for i in range(len(chromosome)):
            if random.random() < self.mutation_rate:
                chromosome[i] = random.randint(1, self.num_communities)

    def run(self):
        population = self.initialize_population()
        best_chromosome = None
        best_fitness = float('-inf')

        for generation in range(self.generations):
            fitness_values = [self.fitness_function(chromosome) for chromosome in population]
            max_fitness = max(fitness_values)
            if max_fitness > best_fitness:
                best_fitness = max_fitness
                best_chromosome = population[fitness_values.index(max_fitness)]

            new_population = []
            for _ in range(self.population_size // 2):
                parent1, parent2 = self.selection(population, fitness_values)
                child1, child2 = self.crossover(parent1, parent2)
                self.mutate(child1)
                self.mutate(child2)
                new_population.extend([child1, child2])
            population = new_population

            # Optional: print progress
            # print(f"Generation {generation+1}: Best Fitness = {best_fitness}")

        return best_chromosome, -best_fitness  # Return best chromosome and its (minimized) fitness

# Contoh penggunaan:
if __name__ == "__main__":
    # Buat graph contoh
    G = nx.erdos_renyi_graph(10, 0.3)
    # Tambahkan atribut node (RAM, STO, IPT)
    for n in G.nodes:
        G.nodes[n]['RAM'] = random.randint(1, 8)
        G.nodes[n]['STO'] = random.randint(10, 100)
        G.nodes[n]['IPT'] = random.randint(100, 1000)

    ga = GACommunity(G, num_communities=3, generations=50)
    best_community, best_fitness = ga.run()
    print("Best community assignment:", best_community)
    print("Best fitness:", best_fitness)