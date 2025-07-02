import sys
import numpy
import json
import random
from solutionGA import SolutionGA

# =======================
# GA Population Management
# =======================
class GAPopulation:
    def __init__(self, pop_size, rng, ec, cnf):
        print(f"[GA] Inisialisasi populasi awal ({pop_size} individu)...")
        self.population = []
        self.rng = rng
        self.ec = ec
        self.cnf = cnf
        for i in range(pop_size):
            sol = SolutionGA(rng, ec, cnf)
            sol.calculateFitness()
            self.population.append(sol)
            if (i+1) % 10 == 0 or (i+1) == pop_size:
                print(f"[GA] Populasi: {i+1}/{pop_size} individu selesai.")

    def getFitnessList(self):
        return [
            {"chromosome": sol.getChromosome(), "fitness": sol.getFitness()}
            for sol in self.population
        ]

    def tournament_selection(self):
        a, b = self.rng.choice(len(self.population), 2, replace=False)
        return self.population[a] if self.population[a].getFitness() < self.population[b].getFitness() else self.population[b]

    def evolve(self):
        print("[GA] Evolusi generasi baru...")
        new_population = []
        best_fitness = self.getBest().getFitness()
        for _ in range(len(self.population)):
            parent1 = self.tournament_selection()
            parent2 = self.tournament_selection()
            children = parent1.crossover(parent2.getChromosome())
            for child in children:
                if self.rng.random() < self.cnf.mutationProbability:
                    child.mutate()
                child.calculateFitness()
                new_population.append(child)
                # Print jika ada solusi lebih baik
                if child.getFitness() < best_fitness:
                    print(f"[GA] Solusi terbaik baru ditemukan: {child.getFitness()}")
                if len(new_population) >= len(self.population):
                    break
        self.population = new_population
        print("[GA] Evolusi generasi selesai.")

    def getBest(self):
        return min(self.population, key=lambda s: s.getFitness())

def save_allocation_to_json(best_solution, app_json_path, net_json_path, output_path):
    # Load app definition
    with open(app_json_path, "r") as f:
        app_json = json.load(f)
    # Load network definition
    with open(net_json_path, "r") as f:
        net_json = json.load(f)
    # Ambil id node dari entity (harus ada field "id" di setiap entity)
    node_id_list = [entity["id"] for entity in net_json["entity"]]

    allocation = []
    chromosome = best_solution.getChromosome()
    service_idx = 0
    for app in app_json:
        app_id = str(app["id"])
        for module in app["module"]:
            module_name = module["name"]
            # Cek node mana saja yang dapat module ini
            for node_idx, deployed in enumerate(chromosome[service_idx]):
                if deployed:
                    allocation.append({
                        "module_name": module_name,
                        "app": app_id,
                        "id_resource": node_id_list[node_idx]
                    })
            service_idx += 1

    with open(output_path, "w") as f:
        json.dump({"initialAllocation": allocation}, f, indent=4)
      # PATCH: Pastikan module tujuan user dialokasikan di node yang sama dengan user source
    try:
        with open("data/usersDefinition.json", "r") as f:
            users_json = json.load(f)
        for user in users_json.get("sources", []):
            user_app = str(user["app"])
            user_node = user["id_resource"]
            user_msg = user["message"]
            # Cari module tujuan dari message user
            app_obj = next((a for a in app_json if str(a["id"]) == user_app), None)
            if app_obj:
                msg_obj = next((m for m in app_obj["message"] if m["name"] == user_msg), None)
                if msg_obj:
                    module_dst = msg_obj["d"]
                    # Cek apakah sudah ada alokasi module_dst di user_node
                    found = any(
                        alloc["module_name"] == module_dst and
                        alloc["app"] == user_app and
                        alloc["id_resource"] == user_node
                        for alloc in allocation
                    )
                    if not found:
                        allocation.append({
                            "module_name": module_dst,
                            "app": user_app,
                            "id_resource": user_node
                        })
        # Tulis ulang hasil patch
        with open(output_path, "w") as f:
            json.dump({"initialAllocation": allocation}, f, indent=4)
    except Exception as e:
        print("WARNING: Patch allocDefinitionGA gagal:", e)

def run_GA(ec, cnf_):
    pop_size = cnf_.numberOfSolutionsInWorkers
    generations = cnf_.numberOfGenerations
    randomseed = cnf_.randomSeed4Optimization[0] if hasattr(cnf_, "randomSeed4Optimization") else 42
    
    rng = numpy.random.RandomState(randomseed)
    ga_pop = GAPopulation(pop_size, rng, ec, cnf_)

    print(f"[GA] Mulai evolusi selama {generations} generasi...")
    for gen in range(generations):
        print(f"[GA] Generasi {gen+1} dimulai...")
        ga_pop.evolve()
        best = ga_pop.getBest()
        print(f"[GA] Generasi {gen+1} selesai. Fitness terbaik: {best.getFitness()}")

    print("[GA] Evolusi selesai.")
    print("[GA] Solusi terbaik akhir:")
    print(ga_pop.getBest().getChromosome())
    print("Fitness:", ga_pop.getBest().getFitness())

    # Simpan alokasi ke file JSON sesuai format
    save_allocation_to_json(
        ga_pop.getBest(),
        "data/appDefinition.json",
        "data/networkDefinition.json",
        "data/allocDefinitionGA.json"
    )
    return ga_pop.getBest()