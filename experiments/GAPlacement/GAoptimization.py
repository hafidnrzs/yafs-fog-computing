#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Copyright 2018 Carlos Guerrero, Isaac Lera.
Created on Tue May 22 15:58:58 2018
@authors:
    Carlos Guerrero
    carlos ( dot ) guerrero  uib ( dot ) es
    Isaac Lera
    isaac ( dot ) lera  uib ( dot ) es
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.
You should have received a copy of the GNU General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>.


This program has been implemented for the research presented in the
article "Availability-aware Service Placement Policy in Fog Computing
Based on Graph Partitions" and submitted for evaluation to the "IEEE
IoT Journal".
"""

import numpy
from typing import List, Tuple
import random
import sys
import json
import copy
import time


# =======================
# GA Solution Class
# =======================
class SolutionGA:
    def __init__(self, rng: numpy.random.mtrand.RandomState, ec, cnf, solConf: dict = None, solInfr: dict = None) -> None:
        print("[SolutionGA] Mulai inisialisasi individu baru...")
        self.randomNG = rng
        self.ec = ec
        self.cnf = cnf
        self.numberOfNodes = self.ec.getNumberOfNodes()
        self.numberOfServices = self.ec.getNumberOfServices()
        self.objectivesFunctions = self.ec.getObjectivesFunctions()
        self.nodeResources = self.ec.getNodeResources()
        self.serviceResources = self.ec.getServiceResources()
        self.infrastructure = {
            'Gdistances': self.ec.Gdistances if hasattr(self.ec, 'Gdistances') else {},
            'clientNodes': self.ec.clientNodes if hasattr(self.ec, 'clientNodes') else [],
            'serviceResource': self.serviceResources,
            'nodeResource': self.nodeResources
        }
        self.solutionConfig = {'numberOfNodes': self.numberOfNodes, 'numberOfServices': self.numberOfServices}
        print("[SolutionGA] Memanggil initWorker untuk inisialisasi kromosom...")
        self.initWorker(self.solutionConfig, self.infrastructure)
        if (solConf is None) and (solInfr is None):
            self.initCoordinator()
        elif isinstance(solConf, dict) and isinstance(solInfr, dict):
            self.initWorker(solConf, solInfr)
        else:
            self.initWorker({'numberOfNodes': self.numberOfNodes, 'numberOfServices': self.numberOfServices}, self.infrastructure)

    def initCoordinator(self) -> None:
        self.state = 'active'

    def initWorker(self, solConf: dict, solInfr: dict) -> None:
        self.state = 'active'
        self.solutionConfig = solConf
        self.infrastructure = solInfr
        max_attempts = 1000  # batas percobaan
        attempts = 0
        satisfiedConstraints = False
        print("[SolutionGA] Mencari solusi feasible untuk individu baru...")
        while not satisfiedConstraints and attempts < max_attempts:
            self.generateRandomChromosome(solConf['numberOfNodes'], solConf['numberOfServices'])
            satisfiedConstraints = self.checkConstraints()
            attempts += 1
            if attempts % 100 == 0:
                print(f"[SolutionGA] Percobaan ke-{attempts} mencari solusi feasible...")
        if not satisfiedConstraints:
            print("[SolutionGA] Gagal menemukan solusi feasible setelah 1000 percobaan!")
            raise Exception("Gagal menemukan solusi feasible pada inisialisasi individu GA.")
        print(f"[SolutionGA] Solusi feasible ditemukan setelah {attempts} percobaan.")

    def generateRandomChromosome(self, numberOfNodes: int, numberOfServices: int) -> None:
        self.chromosome = []
        node_capacity = self.nodeResources.copy()
        forced = set()
        # Siapkan baris kosong untuk semua service
        for i in range(numberOfServices):
            self.chromosome.append([0] * numberOfNodes)
        # Step 1: Tempatkan module tujuan user di node user lebih dulu
        if hasattr(self.ec, "user_module_node"):
            for (app, mod_dst, node) in self.ec.user_module_node:
                idx = self.ec.module2idx.get((app, mod_dst), None)
                if idx is not None and node < numberOfNodes:
                    # Cek resource cukup
                    if node_capacity[node] >= self.serviceResources[idx]:
                        self.chromosome[idx][node] = 1
                        node_capacity[node] -= self.serviceResources[idx]
                        forced.add(idx)
                    else:
                        # Tidak cukup resource, biar constraint gagal
                        pass
        # Step 2: Generate untuk service lain secara random
        for iService in range(numberOfServices):
            if iService in forced:
                continue
            n_nodes = self.randomNG.randint(1, 4)
            candidates = [i for i in range(numberOfNodes) if node_capacity[i] >= self.serviceResources[iService]]
            if len(candidates) < n_nodes:
                chosen = self.randomNG.choice(numberOfNodes, n_nodes, replace=False)
            else:
                chosen = self.randomNG.choice(candidates, n_nodes, replace=False)
            for idx in chosen:
                self.chromosome[iService][idx] = 1
                if idx < len(node_capacity):
                    node_capacity[idx] -= self.serviceResources[iService]

    def meanNumberOfInstances(self) -> float:
        numInstances = sum(sum(serviceAllocation) for serviceAllocation in self.chromosome)
        return float(numInstances) / float(len(self.chromosome))

    def meanEdgeDistance(self) -> float:
        finalTotalDistance = 0
        for serviceAllocation in self.chromosome:
            closestInstanceDistance = 0
            numberOfInstances = sum(serviceAllocation)
            if numberOfInstances > 0:
                for edgeNodeId in self.infrastructure['clientNodes']:
                    minDistance = float('inf')
                    for nodeId, value in enumerate(serviceAllocation):
                        if value == 1:
                            distanceBetweenNodes = self.infrastructure['Gdistances'][str(nodeId)][str(edgeNodeId)]
                            if distanceBetweenNodes < minDistance:
                                minDistance = distanceBetweenNodes
                    closestInstanceDistance += minDistance
                closestInstanceDistance /= float(numberOfInstances)
            else:
                closestInstanceDistance = float('inf')
            finalTotalDistance += closestInstanceDistance
        return float(finalTotalDistance) / float(len(self.chromosome))

    def meanResourceUsage(self) -> float:
        nodeResUse = [0.0 for _ in range(self.numberOfNodes)]
        for idServ, serviceAllocation in enumerate(self.chromosome):
            for idNode, deployed in enumerate(serviceAllocation):
                if deployed:
                    nodeResUse[idNode] += self.serviceResources[idServ]
        usage = []
        for idNode in range(self.numberOfNodes):
            cap = self.nodeResources[idNode]
            usage.append(nodeResUse[idNode] / cap if cap > 0 else 0)
        return float(sum(usage)) / len(usage)

    def dominatesTo(self, solB: 'SolutionGA') -> bool:
        atLeastOneBetter = False
        for i in range(len(self.objectivesFunctions)):
            if solB.fitness[i] < self.fitness[i]:
                return False
            elif self.fitness[i] < solB.fitness[i]:
                atLeastOneBetter = True
        return atLeastOneBetter

    def calculateFitness(self) -> None:
        print("[SolutionGA] Menghitung fitness individu...")
        objectives = []
        for obj in self.objectivesFunctions:
            objValue = eval(obj[1], {}, {"self": self})
            objectives.append(objValue)
        self.fitness = objectives
        print(f"[SolutionGA] Fitness individu: {self.fitness}")

    def setFitness(self, fitnessValues: List[float]) -> None:
        self.fitness = fitnessValues

    def getFitness(self) -> List[float]:
        return self.fitness

    def mutationSwapNode(self) -> None:
        print("[SolutionGA] Mutasi: swap node...")
        
        # Buat set untuk melacak node yang terkait user constraint
        user_constraint_nodes = set()
        if hasattr(self.ec, "user_module_node"):
            for (app, mod_dst, node) in self.ec.user_module_node:
                user_constraint_nodes.add(node)
        
        # Pilih node yang tidak melanggar user constraint
        available_nodes = [n for n in range(self.numberOfNodes) if n not in user_constraint_nodes]
        
        if len(available_nodes) >= 2:
            node1, node2 = self.randomNG.choice(available_nodes, 2, replace=False)
            for i in range(self.numberOfServices):
                # Jangan swap jika service i memiliki user constraint
                has_user_constraint = False
                if hasattr(self.ec, "user_module_node"):
                    for (app, mod_dst, node) in self.ec.user_module_node:
                        idx = self.ec.module2idx.get((app, mod_dst), None)
                        if idx == i:
                            has_user_constraint = True
                            break
                
                if not has_user_constraint:
                    self.chromosome[i][node1], self.chromosome[i][node2] = self.chromosome[i][node2], self.chromosome[i][node1]

    def mutationSwapService(self) -> None:
        print("[SolutionGA] Mutasi: swap service...")
        
        # Buat set untuk melacak service yang memiliki user constraint
        user_constraint_services = set()
        if hasattr(self.ec, "user_module_node"):
            for (app, mod_dst, node) in self.ec.user_module_node:
                idx = self.ec.module2idx.get((app, mod_dst), None)
                if idx is not None:
                    user_constraint_services.add(idx)
        
        # Pilih service yang tidak memiliki user constraint
        available_services = [s for s in range(self.numberOfServices) if s not in user_constraint_services]
        
        if len(available_services) >= 2:
            s1, s2 = self.randomNG.choice(available_services, 2, replace=False)
            self.chromosome[s1], self.chromosome[s2] = self.chromosome[s2], self.chromosome[s1]

    def enforceUserConstraints(self):
        """
        Memastikan user constraints selalu terpenuhi pada kromosom.
        Dipanggil setelah crossover atau operasi yang bisa merusak constraint.
        """
        if hasattr(self.ec, "user_module_node"):
            for (app, mod_dst, node) in self.ec.user_module_node:
                idx = self.ec.module2idx.get((app, mod_dst), None)
                if idx is not None and node < self.numberOfNodes:
                    # Pastikan module tujuan user ada di node user
                    self.chromosome[idx][node] = 1

    def repairChromosome(self):
        """
        Memperbaiki kromosom agar:
        1. Tidak ada node overload (resource usage <= kapasitas)
        2. Setiap service minimal di-deploy di 1 node
        3. User constraints tetap terjaga (module tujuan user di node user)
        """
        nodeResUse = [0.0 for _ in range(self.numberOfNodes)]
        
        # Buat set untuk melacak constraint user (service_idx, node) yang wajib
        user_constraints = set()
        if hasattr(self.ec, "user_module_node"):
            for (app, mod_dst, node) in self.ec.user_module_node:
                idx = self.ec.module2idx.get((app, mod_dst), None)
                if idx is not None and node < self.numberOfNodes:
                    user_constraints.add((idx, node))
        
        # Hitung resource awal
        for idServ, serviceAllocation in enumerate(self.chromosome):
            for idNode, deployed in enumerate(serviceAllocation):
                if deployed:
                    nodeResUse[idNode] += self.serviceResources[idServ]
        
        # Repair node overload
        for idNode in range(self.numberOfNodes):
            while nodeResUse[idNode] > self.nodeResources[idNode]:
                # Cari service yang bisa dihapus dari node ini
                found = False
                for idServ, serviceAllocation in enumerate(self.chromosome):
                    if serviceAllocation[idNode]:
                        # JANGAN hapus jika ini adalah constraint user
                        if (idServ, idNode) in user_constraints:
                            continue
                        # Pastikan service ini masih punya instance di node lain
                        if sum(self.chromosome[idServ]) > 1:
                            self.chromosome[idServ][idNode] = 0
                            nodeResUse[idNode] -= self.serviceResources[idServ]
                            found = True
                            break
                if not found:
                    # Tidak bisa repair lagi, break biar constraint gagal
                    break
        
        # Repair service yang tidak dideploy
        for idServ, serviceAllocation in enumerate(self.chromosome):
            if sum(serviceAllocation) == 0:
                # Cari node yang masih cukup resource
                for idNode in range(self.numberOfNodes):
                    if nodeResUse[idNode] + self.serviceResources[idServ] <= self.nodeResources[idNode]:
                        self.chromosome[idServ][idNode] = 1
                        nodeResUse[idNode] += self.serviceResources[idServ]
                        break

    def mutate(self) -> None:
        print("[SolutionGA] Proses mutasi individu...")
        max_attempts = 100  # batas percobaan mutasi
        attempts = 0
        satisfiedConstraints = False
        while not satisfiedConstraints and attempts < max_attempts:
            mutationOperators = [self.mutationSwapNode, self.mutationSwapService]
            mutationOperators[self.randomNG.randint(len(mutationOperators))]()
            
            # Pastikan user constraints selalu terpenuhi setelah mutasi
            self.enforceUserConstraints()
            
            self.repairChromosome()
            satisfiedConstraints = self.checkConstraints()
            attempts += 1
            if attempts % 20 == 0:
                print(f"[SolutionGA] Mutasi percobaan ke-{attempts}...")
        if not satisfiedConstraints:
            print("[SolutionGA] Mutasi gagal menemukan solusi feasible, reset individu!")
            self.initWorker(self.solutionConfig, self.infrastructure)
        else:
            print("[SolutionGA] Mutasi menghasilkan solusi feasible.")

    def crossover(self, chromosome: List[list]) -> List['SolutionGA']:
        print("[SolutionGA] Proses crossover...")
        satisfiedConstraints = False
        while not satisfiedConstraints:
            chr = [0] * 2
            chr[0], chr[1] = self.twoPointServiceCrossover(self.chromosome, chromosome)
            solutions = []
            satisfiedConstraints = True
            for i in range(len(chr)):
                sol = SolutionGA(self.randomNG, self.ec, self.cnf)
                sol.infrastructure = self.infrastructure
                sol.chromosome = chr[i]
                sol.state = 'active'
                sol.numberOfNodes = self.numberOfNodes
                sol.numberOfServices = self.numberOfServices
                sol.objectivesFunctions = self.objectivesFunctions
                sol.nodeResources = self.nodeResources
                sol.serviceResources = self.serviceResources
                
                # Pastikan user constraints terpenuhi di offspring
                sol.enforceUserConstraints()
                
                sol.repairChromosome()
                solutions.append(sol)
                satisfiedConstraints = satisfiedConstraints and sol.checkConstraints()
            if not satisfiedConstraints:
                print("[SolutionGA] Crossover gagal, ulangi proses crossover...")
        print("[SolutionGA] Crossover menghasilkan solusi feasible.")
        return solutions

    def twoPointServiceCrossover(self, chr1: List[list], chr2: List[list]) -> Tuple[List[list], List[list]]:
        newChild1 = []
        newChild2 = []
        for idService in range(len(chr1)):
            serviceFather1 = chr1[idService]
            serviceFather2 = chr2[idService]
            serviceChild1 = []
            serviceChild2 = []
            firstCrossoverPoint = self.randomNG.randint(len(serviceFather1))
            secondCrossoverPoint = self.randomNG.randint(firstCrossoverPoint, len(serviceFather1))
            for idNode in range(firstCrossoverPoint):
                serviceChild1.append(serviceFather1[idNode])
                serviceChild2.append(serviceFather2[idNode])
            for idNode in range(firstCrossoverPoint, secondCrossoverPoint + 1):
                serviceChild2.append(serviceFather1[idNode])
                serviceChild1.append(serviceFather2[idNode])
            for idNode in range(secondCrossoverPoint + 1, len(serviceFather1)):
                serviceChild1.append(serviceFather1[idNode])
                serviceChild2.append(serviceFather2[idNode])
            newChild1.append(serviceChild1)
            newChild2.append(serviceChild2)
        return newChild1, newChild2

    def getChromosome(self) -> List[list]:
        return self.chromosome

    def checkConstraints(self) -> bool:
        # Constraint 1: Setiap service minimal di-deploy di 1 node
        for serviceAllocation in self.chromosome:
            if sum(serviceAllocation) == 0:
                print("[SolutionGA] Constraint gagal: ada service yang tidak dideploy di node manapun.")
                return False
        # Constraint 2: Resource usage tiap node tidak boleh melebihi kapasitas
        nodeResUse = [0.0 for _ in range(self.numberOfNodes)]
        for idServ, serviceAllocation in enumerate(self.chromosome):
            for idNode, deployed in enumerate(serviceAllocation):
                if deployed:
                    nodeResUse[idNode] += self.serviceResources[idServ]
        for idNode in range(self.numberOfNodes):
            if nodeResUse[idNode] > self.nodeResources[idNode]:
                print(f"[SolutionGA] Constraint gagal: node {idNode} overload (pakai {nodeResUse[idNode]}, kapasitas {self.nodeResources[idNode]})")
                return False
        # Constraint 3: Untuk setiap user, module tujuan user harus dialokasikan di node user
        if hasattr(self.ec, 'user_module_node'):
            for (app, mod_dst, node) in self.ec.user_module_node:
                idx = self.ec.module2idx.get((app, mod_dst), None)
                if idx is None:
                    print(f"[SolutionGA] Constraint gagal: mapping (app={app}, module={mod_dst}) tidak ditemukan.")
                    return False
                if node >= self.numberOfNodes:
                    print(f"[SolutionGA] Constraint gagal: node {node} di luar range node.")
                    return False
                if self.chromosome[idx][node] != 1:
                    print(f"[SolutionGA] Constraint gagal: module {mod_dst} (app {app}) tidak dialokasikan di node user {node}.")
                    return False
        return True
    
    def computeNodeResUseGA(self):
        """Hitung resource usage tiap node untuk solusi GA."""
        self.nodeResUseGA = [0 for _ in range(self.numberOfNodes)]
        for s, allocation in enumerate(self.chromosome):
            for n, deployed in enumerate(allocation):
                if deployed:
                    self.nodeResUseGA[n] += self.serviceResources[s]

    def computeStatisticsDistancesRequestGA(self):
        """Hitung statistik distance vs request untuk solusi GA."""
        # Misal: dictionary {distance: jumlah_request}
        self.statisticsDistancesRequestGA = {}
        for serviceAllocation in self.chromosome:
            for edgeNodeId in self.infrastructure['clientNodes']:
                minDistance = float('inf')
                for nodeId, deployed in enumerate(serviceAllocation):
                    if deployed:
                        distance = self.infrastructure['Gdistances'][str(nodeId)][str(edgeNodeId)]
                        if distance < minDistance:
                            minDistance = distance
                if minDistance != float('inf'):
                    self.statisticsDistancesRequestGA[minDistance] = self.statisticsDistancesRequestGA.get(minDistance, 0) + 1

    def computeUnavailableGArnd(self, failuresObj):
        """Ambil unavailableGArnd dari objek failures."""
        # Asumsi failuresObj sudah punya unavailableGArnd setelah createFails()
        self.unavailableGArnd = getattr(failuresObj, "unavailableGArnd", [])


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


# =======================
# Main GA Class (following CN/ILP pattern)
# =======================
class GA:
    """
    Implementation of the Genetic Algorithm optimization
    Args:
        ec: The modeling of the system (environment configuration)
        cnf: Configuration parameters for the GA
    """
    
    def __init__(self, ec, cnf):
        self.ec = ec
        self.cnf = cnf
        
        # Initialize GA-specific attributes following CN/ILP pattern
        self.networkdistances = {}
        self.nodeResUseGA = list()
        
        # deviceId: total usage resources
        self.nodeBussyResourcesGA = {}
        
        # (centrality,resources):occurrences
        self.statisticsCentralityResourcesGA = {}
        
        # Statistics for distance vs request
        self.statisticsDistancesRequestGA = {}
        
        # For availability analysis
        self.unavailableGArnd = []
        
        print("[GA] GA optimizer initialized")

    def save_allocation_to_json(self, best_solution, app_json_path, net_json_path, output_path):
        """Save the best GA solution allocation to JSON format"""
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

    def run_GA(self):
        """
        Main GA execution method following CN/ILP pattern
        Returns the best solution found
        """
        print("[GA] Starting Genetic Algorithm optimization...")
        
        # Get parameters from configuration
        pop_size = self.cnf.numberOfSolutionsInWorkers
        generations = self.cnf.numberOfGenerations
        randomseed = self.cnf.randomSeed4Optimization[0] if hasattr(self.cnf, "randomSeed4Optimization") else 42
        
        # Initialize random number generator
        rng = numpy.random.RandomState(randomseed)
        
        # Create initial population
        ga_pop = GAPopulation(pop_size, rng, self.ec, self.cnf)

        print(f"[GA] Mulai evolusi selama {generations} generasi...")
        start_time = time.time()
        
        # Evolution loop
        for gen in range(generations):
            print(f"[GA] Generasi {gen+1} dimulai...")
            ga_pop.evolve()
            best = ga_pop.getBest()
            print(f"[GA] Generasi {gen+1} selesai. Fitness terbaik: {best.getFitness()}")

        end_time = time.time()
        execution_time = end_time - start_time
        
        print("[GA] Evolusi selesai.")
        print(f"[GA] Waktu eksekusi: {execution_time:.2f} detik")
        print("[GA] Solusi terbaik akhir:")
        print(ga_pop.getBest().getChromosome())
        print("Fitness:", ga_pop.getBest().getFitness())

        # Get the best solution
        best_solution = ga_pop.getBest()
        
        # Compute statistics following CN/ILP pattern
        self.computeStatistics(best_solution)
        
        # Save allocation to JSON file
        self.save_allocation_to_json(
            best_solution,
            "data/appDefinition.json",
            "data/networkDefinition.json",
            "data/allocDefinitionGA.json"
        )
        
        print("[GA] GA optimization completed successfully")
        return best_solution

    def computeStatistics(self, best_solution):
        """
        Compute various statistics from the best solution
        Following the pattern used in CN/ILP optimization
        """
        print("[GA] Computing solution statistics...")
        
        # Compute node resource usage
        best_solution.computeNodeResUseGA()
        self.nodeResUseGA = best_solution.nodeResUseGA
        
        # Compute distance statistics
        best_solution.computeStatisticsDistancesRequestGA()
        self.statisticsDistancesRequestGA = best_solution.statisticsDistancesRequestGA
        
        # Compute node busy resources
        self.nodeBussyResourcesGA = {}
        for i, usage in enumerate(self.nodeResUseGA):
            self.nodeBussyResourcesGA[i] = usage
        
        print("[GA] Statistics computation completed")

    def createFails(self):
        """
        Create failure scenarios for availability analysis
        Following the pattern used in CN/ILP optimization
        """
        print("[GA] Creating failure scenarios...")
        # This would implement failure scenario generation
        # For now, initialize empty list
        self.unavailableGArnd = []
        print("[GA] Failure scenarios created")

    def getResults(self):
        """
        Return the optimization results in a standardized format
        Following the pattern used in CN/ILP optimization
        """
        return {
            'nodeResUseGA': self.nodeResUseGA,
            'nodeBussyResourcesGA': self.nodeBussyResourcesGA,
            'statisticsDistancesRequestGA': self.statisticsDistancesRequestGA,
            'unavailableGArnd': self.unavailableGArnd
        }

    def getObjectiveValue(self):
        """
        Get the objective value of the best solution
        """
        # This would return the objective value
        # Implementation depends on specific objective function
        return 0.0


# =======================
# Helper Functions
# =======================
def run_GA_optimization(ec, cnf):
    """
    Wrapper function to run GA optimization
    Args:
        ec: Environment configuration
        cnf: Configuration parameters
    Returns:
        Best solution found by GA
    """
    ga_optimizer = GA(ec, cnf)
    best_solution = ga_optimizer.run_GA()
    return best_solution


# =======================
# Main execution
# =======================
if __name__ == "__main__":
    print("GA Optimization module loaded")
    print("Use run_GA_optimization(ec, cnf) to run the optimization")
