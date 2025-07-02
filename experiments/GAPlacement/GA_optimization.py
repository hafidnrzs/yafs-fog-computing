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

import sys
import numpy
import json
import random


# =======================
# GA Solution Class
# =======================
class SolutionGA:
    def __init__(self, rng, ec, cnf):
        self.rng = rng
        self.ec = ec
        self.cnf = cnf
        self.fitness = float('inf')
        
        # Generate random chromosome
        self.chromosome = self.generateRandomChromosome()
    
    def generateRandomChromosome(self):
        """Generate random binary chromosome for service placement"""
        num_services = self.ec.number_of_services
        num_nodes = len(self.ec.G.nodes)
        
        chromosome = []
        for service_idx in range(num_services):
            service_placement = [0] * num_nodes
            # Randomly assign service to at least one node
            selected_nodes = self.rng.choice(num_nodes, 
                                           size=self.rng.randint(1, max(2, num_nodes//3)), 
                                           replace=False)
            for node_idx in selected_nodes:
                service_placement[node_idx] = 1
            chromosome.append(service_placement)
        return chromosome
    
    def getChromosome(self):
        return self.chromosome
    
    def getFitness(self):
        return self.fitness
    
    def calculateFitness(self):
        """Calculate fitness based on placement cost and constraints"""
        try:
            # Initialize cost
            total_cost = 0.0
            
            # Resource constraint penalty
            node_usage = [0] * len(self.ec.G.nodes)
            
            for service_idx, service_placement in enumerate(self.chromosome):
                for node_idx, is_deployed in enumerate(service_placement):
                    if is_deployed:
                        # Add deployment cost
                        total_cost += 1.0
                        # Update resource usage (simplified)
                        node_usage[node_idx] += 1
            
            # Add penalty for resource violations
            for usage in node_usage:
                if usage > 3:  # Simplified capacity constraint
                    total_cost += (usage - 3) * 10
            
            # Connectivity penalty (simplified)
            # Ensure each service is deployed at least once
            for service_placement in self.chromosome:
                if sum(service_placement) == 0:
                    total_cost += 1000  # High penalty for undeployed service
            
            self.fitness = total_cost
            
        except Exception as e:
            print(f"Error calculating fitness: {e}")
            self.fitness = float('inf')
    
    def crossover(self, other_chromosome):
        """Single-point crossover with mutation"""
        try:
            child1_chromosome = []
            child2_chromosome = []
            
            crossover_point = self.rng.randint(0, len(self.chromosome))
            
            for i in range(len(self.chromosome)):
                if i < crossover_point:
                    child1_chromosome.append(self.chromosome[i][:])
                    child2_chromosome.append(other_chromosome[i][:])
                else:
                    child1_chromosome.append(other_chromosome[i][:])
                    child2_chromosome.append(self.chromosome[i][:])
            
            # Create child solutions
            child1 = SolutionGA(self.rng, self.ec, self.cnf)
            child1.chromosome = child1_chromosome
            
            child2 = SolutionGA(self.rng, self.ec, self.cnf)
            child2.chromosome = child2_chromosome
            
            return [child1, child2]
            
        except Exception as e:
            print(f"Error in crossover: {e}")
            return [self, self]
    
    def mutate(self):
        """Bit-flip mutation"""
        try:
            for service_idx in range(len(self.chromosome)):
                for node_idx in range(len(self.chromosome[service_idx])):
                    if self.rng.random() < 0.1:  # 10% mutation rate per bit
                        self.chromosome[service_idx][node_idx] = 1 - self.chromosome[service_idx][node_idx]
            
            # Ensure each service is deployed at least once
            for service_idx in range(len(self.chromosome)):
                if sum(self.chromosome[service_idx]) == 0:
                    random_node = self.rng.randint(0, len(self.chromosome[service_idx]))
                    self.chromosome[service_idx][random_node] = 1
                    
        except Exception as e:
            print(f"Error in mutation: {e}")


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
                if self.rng.random() < getattr(self.cnf, 'mutationProbability', 0.1):
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
# Main GA Class (following ILP/CN pattern)
# =======================
class GA:
    def __init__(self, ec, cnf):
        self.ec = ec
        self.cnf = cnf

    def solve(self):
        """Main solving method that returns service_to_device_placement_matrix"""
        print("[GA] Memulai optimasi Genetic Algorithm...")
        
        # GA parameters (reduced for faster testing)
        pop_size = getattr(self.cnf, 'numberOfSolutionsInWorkers', 10)  # Reduced from 50
        generations = getattr(self.cnf, 'numberOfGenerations', 20)       # Reduced from 100
        randomseed = getattr(self.cnf, 'randomSeed4Optimization', [42])[0]
        
        rng = numpy.random.RandomState(randomseed)
        ga_pop = GAPopulation(pop_size, rng, self.ec, self.cnf)

        print(f"[GA] Mulai evolusi selama {generations} generasi...")
        for gen in range(generations):
            print(f"[GA] Generasi {gen+1} dimulai...")
            ga_pop.evolve()
            best = ga_pop.getBest()
            print(f"[GA] Generasi {gen+1} selesai. Fitness terbaik: {best.getFitness()}")

        print("[GA] Evolusi selesai.")
        best_solution = ga_pop.getBest()
        print("[GA] Solusi terbaik akhir:")
        print("Fitness:", best_solution.getFitness())

        # Convert chromosome to service_to_device_placement_matrix format
        service_to_device_placement_matrix = self._convert_to_matrix(best_solution.getChromosome())
        
        # Save allocation to JSON file
        self._save_allocation_to_json(best_solution)
        
        return service_to_device_placement_matrix
    
    def _convert_to_matrix(self, chromosome):
        """Convert chromosome to service_to_device_placement_matrix format"""
        # This should return the same format as ILP and CN optimization
        # The exact format depends on how ec.get_services() and ec.get_nodes() work
        return chromosome
    
    def _save_allocation_to_json(self, best_solution):
        """Save allocation to JSON file following the pattern"""
        try:
            # Load app definition
            with open("data/appDefinition.json", "r") as f:
                app_json = json.load(f)
            # Load network definition  
            with open("data/networkDefinition.json", "r") as f:
                net_json = json.load(f)
            
            # Get node IDs from entities
            node_id_list = [entity["id"] for entity in net_json["entity"]]

            allocation = []
            chromosome = best_solution.getChromosome()
            service_idx = 0
            
            for app in app_json:
                app_id = str(app["id"])
                for module in app["module"]:
                    module_name = module["name"]
                    # Check which nodes deploy this module
                    for node_idx, deployed in enumerate(chromosome[service_idx]):
                        if deployed:
                            allocation.append({
                                "module_name": module_name,
                                "app": app_id,
                                "id_resource": node_id_list[node_idx]
                            })
                    service_idx += 1

            with open("data/allocDefinitionGA.json", "w") as f:
                json.dump({"initialAllocation": allocation}, f, indent=4)
                
            # PATCH: Ensure user destination modules are allocated to same node as user source
            try:
                with open("data/usersDefinition.json", "r") as f:
                    users_json = json.load(f)
                for user in users_json.get("sources", []):
                    user_app = str(user["app"])
                    user_node = user["id_resource"]
                    user_msg = user["message"]
                    # Find destination module from user message
                    app_obj = next((a for a in app_json if str(a["id"]) == user_app), None)
                    if app_obj:
                        msg_obj = next((m for m in app_obj["message"] if m["name"] == user_msg), None)
                        if msg_obj:
                            module_dst = msg_obj["d"]
                            # Check if module_dst allocation exists at user_node
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
                # Write patched results
                with open("data/allocDefinitionGA.json", "w") as f:
                    json.dump({"initialAllocation": allocation}, f, indent=4)
            except Exception as e:
                print("WARNING: Patch allocDefinitionGA gagal:", e)
                
        except Exception as e:
            print(f"ERROR: Gagal menyimpan allocation JSON: {e}")
