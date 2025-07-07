"""
Genetic Algorithm Optimization for Service Placement in Fog Computing

This module implements a genetic algorithm for optimizing service placement in fog computing environments.
It is integrated with the PartitionILPPlacement framework and produces compatible output with spaguetti.py.

The main components are:
- SolutionGA: Represents a single solution (chromosome) in the population
- GAPopulation: Manages the population of solutions and evolution operations
- GAoptimization: Main optimization class that integrates with the system

Usage:
    The GA optimization is designed to be called from spaguetti.py or main_nf.py
    with the same parameter structure as ILP optimization.
"""

import numpy as np
import random
import json
import logging
from typing import List, Dict, Tuple, Optional, Any
import copy
import time
import networkx as nx

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SolutionGA:
    """
    Represents a single solution (chromosome) in the genetic algorithm population.
    
    Each solution contains:
    - A placement matrix indicating which services are placed on which nodes
    - Fitness values for multiple objectives (latency, resource usage, etc.)
    - Methods for fitness calculation and constraint validation
    """
    
    def __init__(self, nodes: int, services: int, node_resources: List[int], 
                 service_resources: List[int], user_constraints: List[Dict], 
                 cloudId: int, ga_optimizer):
        """
        Initialize a solution with random placement.
        
        Args:
            nodes: Number of nodes in the network
            services: Number of services to place
            node_resources: List of available resources per node
            service_resources: List of required resources per service
            user_constraints: List of user constraint dictionaries
            cloudId: ID of the cloud node
            ga_optimizer: Reference to the GA optimizer for network calculations
        """
        self.nodes = nodes
        self.services = services
        self.node_resources = node_resources
        self.service_resources = service_resources
        self.user_constraints = user_constraints
        self.cloudId = cloudId
        self.ga_optimizer = ga_optimizer
        
        # Initialize placement matrix randomly
        self.placement_matrix = np.zeros((services, nodes), dtype=int)
        self.generate_random_placement()
        
        # Initialize fitness values
        self.fitness = float('inf')
        self.is_feasible = False
        self.calculate_fitness()
    
    def generate_random_placement(self):
        """Generate a random valid placement ensuring each service is placed on exactly one node."""
        for service in range(self.services):
            # Exclude cloud node from initial random placement
            available_nodes = [i for i in range(self.nodes) if i != self.cloudId]
            if available_nodes:
                node = random.choice(available_nodes)
            else:
                node = random.randint(0, self.nodes - 1)
            self.placement_matrix[service, node] = 1
    
    def calculate_fitness(self):
        """
        Calculate fitness value for the solution using network delay optimization.
        
        Returns:
            Fitness value (lower is better)
        """
        try:
            total_delay = 0.0
            constraint_penalty = 0.0
            
            # Calculate total network delay for user service assignments
            for constraint in self.user_constraints:
                service_id = constraint.get('service_id', 0)
                user_id = constraint.get('user_id', 0)
                
                if service_id < self.services:
                    # Find which node this service is placed on
                    placed_nodes = np.where(self.placement_matrix[service_id] == 1)[0]
                    if len(placed_nodes) > 0:
                        node_id = placed_nodes[0]
                        
                        # Calculate network delay using GA optimizer's method
                        delay = self.ga_optimizer.calculate_network_delay((user_id, service_id), node_id)
                        total_delay += delay
            
            # Calculate constraint violation penalty
            constraint_penalty = self.calculate_constraint_penalty()
            
            # Combined fitness (network delay + constraint penalty)
            self.fitness = total_delay + constraint_penalty * 1000  # Heavy penalty for constraint violations
            
            # Check if solution is feasible
            self.is_feasible = self.check_feasibility()
            
            return self.fitness
        
        except Exception as e:
            logger.error(f"Error in fitness calculation: {e}")
            self.fitness = float('inf')
            self.is_feasible = False
            return self.fitness
    
    def calculate_constraint_penalty(self) -> float:
        """Calculate penalty for constraint violations."""
        penalty = 0.0
        
        try:
            # Check resource constraints
            node_usage = np.zeros(self.nodes)
            for service in range(self.services):
                for node in range(self.nodes):
                    if self.placement_matrix[service, node] == 1:
                        if service < len(self.service_resources):
                            node_usage[node] += self.service_resources[service]
            
            # Add penalty for resource overuse
            for node in range(self.nodes):
                if node < len(self.node_resources):
                    if node_usage[node] > self.node_resources[node]:
                        penalty += (node_usage[node] - self.node_resources[node]) / self.node_resources[node]
            
            # Check placement constraints (each service must be placed exactly once)
            for service in range(self.services):
                placements = np.sum(self.placement_matrix[service])
                if placements != 1:
                    penalty += abs(placements - 1) * 10  # High penalty for invalid placements
            
            return penalty
        
        except Exception as e:
            logger.error(f"Error calculating constraint penalty: {e}")
            return float('inf')
    
    def check_feasibility(self) -> bool:
        """Check if the solution is feasible."""
        try:
            # Check if each service is placed exactly once
            for service in range(self.services):
                if np.sum(self.placement_matrix[service]) != 1:
                    return False
            
            # Check resource constraints
            node_usage = np.zeros(self.nodes)
            for service in range(self.services):
                for node in range(self.nodes):
                    if self.placement_matrix[service, node] == 1:
                        if service < len(self.service_resources):
                            node_usage[node] += self.service_resources[service]
            
            for node in range(self.nodes):
                if node < len(self.node_resources):
                    if node_usage[node] > self.node_resources[node]:
                        return False
            
            return True
        
        except Exception as e:
            logger.error(f"Error checking feasibility: {e}")
            return False
    
    def mutate(self, mutation_rate: float = 0.1):
        """
        Perform mutation on the solution.
        
        Args:
            mutation_rate: Probability of mutation for each gene
        """
        try:
            for service in range(self.services):
                if random.random() < mutation_rate:
                    # Find current placement
                    current_node = np.where(self.placement_matrix[service] == 1)[0]
                    if len(current_node) > 0:
                        # Remove current placement
                        self.placement_matrix[service, current_node[0]] = 0
                        
                        # Place on a new random node (exclude cloud for diversity)
                        available_nodes = [i for i in range(self.nodes) if i != self.cloudId]
                        if available_nodes:
                            new_node = random.choice(available_nodes)
                        else:
                            new_node = random.randint(0, self.nodes - 1)
                        self.placement_matrix[service, new_node] = 1
            
            # Recalculate fitness after mutation
            self.calculate_fitness()
        
        except Exception as e:
            logger.error(f"Error in mutation: {e}")
    
    def copy(self):
        """Create a deep copy of the solution."""
        try:
            new_solution = SolutionGA(
                self.nodes, self.services, self.node_resources,
                self.service_resources, self.user_constraints, 
                self.cloudId, self.ga_optimizer
            )
            new_solution.placement_matrix = self.placement_matrix.copy()
            new_solution.fitness = self.fitness
            new_solution.is_feasible = self.is_feasible
            return new_solution
        
        except Exception as e:
            logger.error(f"Error copying solution: {e}")
            return None
    
    def get_placement_dict(self) -> Dict[str, int]:
        """
        Convert placement matrix to dictionary format.
        
        Returns:
            Dictionary mapping service IDs to node IDs
        """
        placement_dict = {}
        for service in range(self.services):
            placed_nodes = np.where(self.placement_matrix[service] == 1)[0]
            if len(placed_nodes) > 0:
                placement_dict[str(service)] = int(placed_nodes[0])
        return placement_dict


class GAPopulation:
    """
    Manages the population of GA solutions and evolution operations.
    
    This class handles:
    - Population initialization
    - Selection operations (tournament selection)
    - Crossover operations (uniform crossover)
    - Mutation operations
    - Population evolution
    """
    
    def __init__(self, population_size: int, nodes: int, services: int,
                 node_resources: List[int], service_resources: List[int],
                 user_constraints: List[Dict], cloudId: int, ga_optimizer):
        """
        Initialize the GA population.
        
        Args:
            population_size: Number of individuals in the population
            nodes: Number of nodes in the network
            services: Number of services to place
            node_resources: List of available resources per node
            service_resources: List of required resources per service
            user_constraints: List of user constraint dictionaries
            cloudId: ID of the cloud node
            ga_optimizer: Reference to the GA optimizer
        """
        self.population_size = population_size
        self.nodes = nodes
        self.services = services
        self.node_resources = node_resources
        self.service_resources = service_resources
        self.user_constraints = user_constraints
        self.cloudId = cloudId
        self.ga_optimizer = ga_optimizer
        
        # Initialize random number generator
        self.rng = np.random.RandomState(42)
        
        # Initialize population
        self.population: List[SolutionGA] = []
        self.best_solution: Optional[SolutionGA] = None
        self.generation = 0
        
        # Initialize population
        self.initialize_population()
    
    def initialize_population(self):
        """Initialize the population with random solutions."""
        logger.info(f"[GA] Initializing population ({self.population_size} individuals)...")
        
        self.population = []
        for i in range(self.population_size):
            solution = SolutionGA(
                self.nodes, self.services, self.node_resources,
                self.service_resources, self.user_constraints,
                self.cloudId, self.ga_optimizer
            )
            self.population.append(solution)
        
        logger.info(f"[GA] Population: {len(self.population)}/{self.population_size} individuals initialized.")
        
        # Find initial best solution
        self.update_best_solution()
    
    def update_best_solution(self):
        """Update the best solution in the population."""
        if not self.population:
            return
        
        # Find the best solution based on fitness value (lower is better)
        best_candidate = self.population[0]
        
        for solution in self.population[1:]:
            if solution.fitness < best_candidate.fitness:
                best_candidate = solution
        
        # Update best solution if improved
        if (self.best_solution is None or 
            best_candidate.fitness < self.best_solution.fitness):
            self.best_solution = best_candidate.copy()
            logger.debug(f"[GA] New best solution found: fitness = {best_candidate.fitness:.4f}")
    
    def tournament_selection(self, tournament_size: int = 3) -> SolutionGA:
        """
        Perform tournament selection to choose a parent.
        
        Args:
            tournament_size: Number of individuals in the tournament
            
        Returns:
            Selected parent solution
        """
        if len(self.population) < tournament_size:
            tournament_size = len(self.population)
        
        # Select random individuals for tournament
        tournament_indices = self.rng.choice(len(self.population), tournament_size, replace=False)
        tournament = [self.population[i] for i in tournament_indices]
        
        # Find the best individual in the tournament (lowest fitness)
        best = tournament[0]
        for candidate in tournament[1:]:
            if candidate.fitness < best.fitness:
                best = candidate
        
        return best
    
    def crossover(self, parent1: SolutionGA, parent2: SolutionGA) -> Tuple[SolutionGA, SolutionGA]:
        """
        Perform uniform crossover between two parents.
        
        Args:
            parent1: First parent
            parent2: Second parent
            
        Returns:
            Tuple of two offspring solutions
        """
        try:
            # Create offspring by copying parents
            offspring1 = parent1.copy()
            offspring2 = parent2.copy()
            
            # Perform uniform crossover
            for service in range(self.services):
                if self.rng.random() < 0.5:
                    # Swap placements for this service
                    temp = offspring1.placement_matrix[service].copy()
                    offspring1.placement_matrix[service] = offspring2.placement_matrix[service].copy()
                    offspring2.placement_matrix[service] = temp
            
            # Recalculate fitness
            offspring1.calculate_fitness()
            offspring2.calculate_fitness()
            
            return offspring1, offspring2
        
        except Exception as e:
            logger.error(f"Error in crossover: {e}")
            return parent1.copy(), parent2.copy()
    
    def evolve(self):
        """Evolve the population for one generation."""
        logger.debug("[GA] Evolution generation...")
        
        new_population = []
        
        # Elitism: keep best solutions
        elite_size = max(1, self.population_size // 10)  # Keep top 10%
        sorted_population = sorted(self.population, key=lambda x: x.fitness)
        new_population.extend([sol.copy() for sol in sorted_population[:elite_size]])
        
        # Generate rest of the population through crossover and mutation
        while len(new_population) < self.population_size:
            # Selection
            parent1 = self.tournament_selection()
            parent2 = self.tournament_selection()
            
            # Crossover
            offspring1, offspring2 = self.crossover(parent1, parent2)
            
            # Mutation
            mutation_rate = 0.1  # Default mutation rate
            offspring1.mutate(mutation_rate)
            offspring2.mutate(mutation_rate)
            
            # Add to new population
            new_population.append(offspring1)
            if len(new_population) < self.population_size:
                new_population.append(offspring2)
        
        # Update population
        self.population = new_population[:self.population_size]
        self.generation += 1
        
        # Update best solution
        self.update_best_solution()
    
    def get_best_fitness(self) -> float:
        """Get the fitness of the best solution."""
        if self.best_solution:
            return self.best_solution.fitness
        return float('inf')
    
    def get_population_stats(self) -> Dict[str, Any]:
        """Get statistics about the current population."""
        if not self.population:
            return {}
        
        fitnesses = [sol.fitness for sol in self.population]
        
        return {
            'generation': self.generation,
            'population_size': len(self.population),
            'best_fitness': min(fitnesses),
            'average_fitness': np.mean(fitnesses),
            'worst_fitness': max(fitnesses),
            'feasible_solutions': sum(1 for sol in self.population if sol.is_feasible)
        }


class GAoptimization:
    """
    Main Genetic Algorithm optimization class.
    
    This class provides the main interface for GA optimization, compatible with
    the PartitionILPPlacement framework and spaguetti.py parameters.
    """
    
    def __init__(self, 
                 G,                      # Network graph
                 numberOfServices,       # Total number of services
                 mapService2App,         # Service to app mapping
                 mapServiceId2ServiceName, # Service ID to service name mapping
                 servicesResources,      # Service resource requirements
                 myDevices,              # Device information
                 cloudId,                # Cloud ID
                 allTheGtws,             # Gateway devices
                 userServices,           # User service requests
                 myServicesResources,    # Service resource requirements dict
                 networkdistances,       # Network distances
                 ):
        """
        Initialize the GA optimization with spaguetti.py compatible parameters.
        
        Args:
            G: NetworkX graph representing the network topology
            numberOfServices: Total number of services
            mapService2App: List mapping service IDs to app IDs
            mapServiceId2ServiceName: List mapping service IDs to service names
            servicesResources: Dict of service resource requirements
            myDevices: Dict of device information
            cloudId: ID of the cloud node
            allTheGtws: List of gateway devices
            userServices: List of user service requests
            myServicesResources: Dict of service resource requirements
            networkdistances: Dict of network distances
        """
        self.G = G
        self.numberOfServices = numberOfServices
        self.mapService2App = mapService2App
        self.mapServiceId2ServiceName = mapServiceId2ServiceName
        self.servicesResources = servicesResources
        self.myDevices = myDevices
        self.cloudId = cloudId
        self.allTheGtws = allTheGtws
        self.userServices = userServices
        self.myServicesResources = myServicesResources
        self.networkdistances = networkdistances
        
        # Extract basic parameters
        self.nodes = len(G.nodes)
        self.services = numberOfServices
        
        # Convert device resources to list format
        self.node_resources = []
        for i in range(self.nodes):
            if i in myDevices:
                self.node_resources.append(myDevices[i]["RAM"])
            else:
                self.node_resources.append(0)
        
        # Convert service resources to list format
        self.service_resources = []
        for i in range(self.services):
            if i in servicesResources:
                self.service_resources.append(servicesResources[i])
            else:
                self.service_resources.append(1)
        
        # Create user constraints from userServices
        self.user_constraints = []
        for user_service in userServices:
            user_id, service_id = user_service
            self.user_constraints.append({
                'app': self.mapService2App[service_id] if service_id < len(self.mapService2App) else str(service_id),
                'service_id': service_id,
                'user_id': user_id
            })
        
        # GA-specific parameters (can be made configurable)
        self.population_size = 20
        self.max_generations = 50
        self.mutation_rate = 0.2  # Increased mutation rate
        self.tournament_size = 3
        self.elite_size = 2
        
        # Initialize population
        self.ga_population = None
        self.best_solution = None
        self.optimization_time = 0.0
        
        # Results storage
        self.results = {
            'best_fitness': None,
            'optimization_time': 0.0,
            'generations': 0,
            'population_size': self.population_size,
            'final_placement': None,
            'allocation_json': None
        }
        
        logger.info(f"[GA] Initialized with {self.nodes} nodes, {self.services} services")
        logger.info(f"[GA] User constraints: {len(self.user_constraints)}")
        logger.info(f"[GA] Population size: {self.population_size}, Generations: {self.max_generations}")
    
    def calculate_network_delay(self, user_service_tuple, device_id):
        """
        Calculate network delay for a user service placed on a device.
        
        Args:
            user_service_tuple: (user_id, service_id) tuple
            device_id: Device ID where service is placed
            
        Returns:
            Network delay value
        """
        user_id, service_id = user_service_tuple
        
        # Use networkdistances if available
        if (user_id, device_id) in self.networkdistances:
            return self.networkdistances[(user_id, device_id)]
        
        # Fallback to graph distance
        try:
            if user_id in self.G.nodes and device_id in self.G.nodes:
                path_length = nx.shortest_path_length(self.G, user_id, device_id, weight='weight')
                return path_length
            else:
                return 1000  # High penalty for invalid nodes
        except:
            return 1000  # High penalty if no path exists
    
    def runOptimization(self):
        """
        Run the genetic algorithm optimization.
        
        Returns:
            Best solution found, or None if optimization failed
        """
        try:
            start_time = time.time()
            
            logger.info(f"[GA] Starting GA optimization with {self.population_size} individuals for {self.max_generations} generations")
            
            # Initialize population
            self.ga_population = GAPopulation(
                self.population_size, self.nodes, self.services,
                self.node_resources, self.service_resources,
                self.user_constraints, self.cloudId, self
            )
            
            # Evolution loop
            for generation in range(self.max_generations):
                logger.info(f"[GA] Generation {generation + 1}/{self.max_generations}")
                
                # Evolve population
                self.ga_population.evolve()
                
                # Log progress
                best_fitness = self.ga_population.get_best_fitness()
                logger.info(f"[GA] Generation {generation + 1} - Best fitness: {best_fitness:.4f}")
                
                # Optional: Early stopping if solution is good enough
                if self.ga_population.best_solution and self.ga_population.best_solution.is_feasible:
                    if best_fitness < 100:  # Good enough solution
                        logger.info(f"[GA] Early stopping at generation {generation + 1}")
                        break
            
            # Get best solution
            self.best_solution = self.ga_population.best_solution
            self.optimization_time = time.time() - start_time
            
            # Update results
            if self.best_solution:
                self.results['best_fitness'] = self.best_solution.fitness
                self.results['final_placement'] = self.best_solution.get_placement_dict()
                
                # Generate allocation JSON in the expected format
                self.results['allocation_json'] = self.generate_allocation_json()
            
            self.results['generations'] = generation + 1
            self.results['optimization_time'] = self.optimization_time
            
            logger.info(f"[GA] Optimization completed in {self.optimization_time:.2f} seconds")
            if self.best_solution:
                logger.info(f"[GA] Best fitness: {self.best_solution.fitness:.4f}")
                logger.info(f"[GA] Feasible: {self.best_solution.is_feasible}")
            
            return self.best_solution
        
        except Exception as e:
            logger.error(f"[GA] Error in optimization: {e}")
            return None
    
    def generate_allocation_json(self):
        """
        Generate allocation JSON in the format expected by main_nf.py.
        
        Returns:
            Dictionary with allocation information
        """
        if not self.best_solution:
            return {"initialAllocation": []}
        
        allocation_list = []
        
        # Get valid service indices that actually exist in mapServiceId2ServiceName
        valid_service_indices = len(self.mapServiceId2ServiceName)
        
        # For each valid service, add allocation entries
        for service_idx in range(min(self.services, valid_service_indices)):
            if service_idx < len(self.mapServiceId2ServiceName):
                placed_nodes = np.where(self.best_solution.placement_matrix[service_idx] == 1)[0]
                if len(placed_nodes) > 0:
                    node_id = placed_nodes[0]
                    
                    # Only add fog placement (not cloud)
                    if node_id != self.cloudId:
                        allocation = {
                            "app": self.mapService2App[service_idx],
                            "module_name": self.mapServiceId2ServiceName[service_idx],
                            "id_resource": int(node_id)
                        }
                        allocation_list.append(allocation)
        
        # Add cloud allocations for all valid services (as done in spaguetti.py)
        for service_idx in range(min(self.services, valid_service_indices)):
            if service_idx < len(self.mapServiceId2ServiceName):
                allocation = {
                    "app": self.mapService2App[service_idx],
                    "module_name": self.mapServiceId2ServiceName[service_idx],
                    "id_resource": self.cloudId
                }
                allocation_list.append(allocation)
        
        return {"initialAllocation": allocation_list}
    
    def solve(self):
        """
        Solve the optimization problem and return the placement solution.
        
        Returns:
            Dictionary with allocation information compatible with main_nf.py
        """
        try:
            # Run optimization
            best_solution = self.runOptimization()
            
            if best_solution:
                # Generate and save allocation JSON
                allocation_json = self.generate_allocation_json()
                
                # Save to file as expected by main_nf.py
                with open("exp_rev/allocDefinitionGA.json", "w") as f:
                    json.dump(allocation_json, f, indent=2)
                
                logger.info("[GA] Allocation saved to exp_rev/allocDefinitionGA.json")
                
                return allocation_json
            else:
                logger.error("[GA] No solution found")
                # Return empty allocation
                empty_allocation = {"initialAllocation": []}
                with open("exp_rev/allocDefinitionGA.json", "w") as f:
                    json.dump(empty_allocation, f, indent=2)
                return empty_allocation
        
        except Exception as e:
            logger.error(f"[GA] Error in solve: {e}")
            # Return empty allocation on error
            empty_allocation = {"initialAllocation": []}
            with open("exp_rev/allocDefinitionGA.json", "w") as f:
                json.dump(empty_allocation, f, indent=2)
            return empty_allocation
    
    def get_best_solution(self):
        """Get the best solution found."""
        return self.best_solution
    
    def get_optimization_results(self):
        """Get detailed optimization results."""
        return self.results.copy()
    
    def save_results(self, filename: str):
        """
        Save optimization results to a JSON file.
        
        Args:
            filename: Output filename
        """
        try:
            with open(filename, 'w') as f:
                json.dump(self.results, f, indent=2)
            logger.info(f"[GA] Results saved to {filename}")
        except Exception as e:
            logger.error(f"[GA] Error saving results: {e}")


def load_network_definition(file_path):
    """
    Load network definition from JSON file.
    
    Args:
        file_path (str): Path to the network definition JSON file
        
    Returns:
        dict: Network definition data or None if error
    """
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        return data
    except Exception as e:
        logger.error(f"Error loading network definition: {e}")
        return None


def create_network_from_definition(network_data):
    """
    Create NetworkX graph from network definition.
    
    Args:
        network_data (dict): Network definition data
        
    Returns:
        networkx.Graph: Created network graph
    """
    G = nx.Graph()
    
    # Handle different formats of network definition
    if 'entity' in network_data:
        # Format: {"entity": [...], "link": [...]}
        # Add nodes
        for entity in network_data['entity']:
            G.add_node(entity['id'], **entity)
        
        # Add edges
        for link in network_data['link']:
            G.add_edge(link['s'], link['d'], **link)
    
    elif 'nodes' in network_data:
        # Format: {"nodes": [...], "edges": [...]}
        # Add nodes
        for node in network_data['nodes']:
            G.add_node(node['id'], **node)
        
        # Add edges
        for edge in network_data['edges']:
            G.add_edge(edge['src'], edge['dst'], **edge)
    
    return G


def load_app_definition(app_path):
    """
    Load application definition from JSON file and extract service information.
    
    Args:
        app_path (str): Path to the application definition JSON file
        
    Returns:
        tuple: (mapService2App, mapServiceId2ServiceName, serviceResources_list)
    """
    try:
        with open(app_path, 'r') as f:
            app_data = json.load(f)
        
        mapService2App = []
        mapServiceId2ServiceName = {}
        serviceResources_list = []
        
        # Create a mapping from module ID to service info
        module_id_to_service = {}
        
        # First pass: collect all modules and their service IDs
        for app in app_data:
            app_name = app['name']
            
            # Process modules (services) - use the module ID from the JSON
            for module in app['module']:
                module_id = module['id']
                module_name = module['name']
                module_ram = module['RAM']
                
                module_id_to_service[module_id] = {
                    'app_name': app_name,
                    'module_name': module_name,
                    'ram': module_ram
                }
        
        # Second pass: create ordered lists based on module IDs
        max_module_id = max(module_id_to_service.keys()) if module_id_to_service else -1
        
        for service_id in range(max_module_id + 1):
            if service_id in module_id_to_service:
                service_info = module_id_to_service[service_id]
                mapService2App.append(service_info['app_name'])
                mapServiceId2ServiceName[service_id] = service_info['module_name']
                serviceResources_list.append(service_info['ram'])
            else:
                # Fill gaps with dummy services to maintain indexing
                mapService2App.append('dummy')
                mapServiceId2ServiceName[service_id] = f'dummy_{service_id}'
                serviceResources_list.append(1)
        
        return mapService2App, mapServiceId2ServiceName, serviceResources_list
        
    except Exception as e:
        logger.error(f"Error loading application definition: {e}")
        return [], {}, []


def create_ga_optimization(G, numberOfServices, mapService2App, mapServiceId2ServiceName, 
                          servicesResources, myDevices, cloudId, allTheGtws, userServices,
                          myServicesResources, networkdistances):
    """
    Create GA optimization instance with the provided parameters.
    
    Args:
        G: NetworkX graph representing the network topology
        numberOfServices: Number of services to place
        mapService2App: Mapping from service ID to application name
        mapServiceId2ServiceName: Mapping from service ID to service name
        servicesResources: Dictionary of service resource requirements
        myDevices: Dictionary of device specifications
        cloudId: ID of the cloud node
        allTheGtws: List of gateway node IDs
        userServices: List of (user_id, service_id) tuples
        myServicesResources: Dictionary of service resource requirements
        networkdistances: Dictionary of network distances between nodes
        
    Returns:
        GAoptimization instance
    """
    return GAoptimization(
        G=G,
        numberOfServices=numberOfServices,
        mapService2App=mapService2App,
        mapServiceId2ServiceName=mapServiceId2ServiceName,
        servicesResources=servicesResources,
        myDevices=myDevices,
        cloudId=cloudId,
        allTheGtws=allTheGtws,
        userServices=userServices,
        myServicesResources=myServicesResources,
        networkdistances=networkdistances
    )


def run_ga_optimization_standalone():
    """
    Run GA optimization sebagai standalone function.
    Fungsi ini menggabungkan semua yang ada di run_ga_optimization.py
    """
    import os
    
    print("Starting GA optimization...")
    
    # Load network definition
    network_path = os.path.join('exp_rev', 'networkDefinition.json')
    network_data = load_network_definition(network_path)
    if not network_data:
        print("Failed to load network definition")
        return False
    
    # Create network graph
    G = create_network_from_definition(network_data)
    print(f"Network loaded: {len(G.nodes)} nodes, {len(G.edges)} edges")
    
    # Load application definition
    app_path = os.path.join('exp_rev', 'appDefinition.json')
    if not os.path.exists(app_path):
        print(f"Application definition not found at {app_path}")
        return False
    
    mapService2App, mapServiceId2ServiceName, serviceResources_list = load_app_definition(app_path)
    numberOfServices = len(mapServiceId2ServiceName)
    servicesResources = {i: serviceResources_list[i] for i in range(numberOfServices)}
    
    print(f"Loaded {numberOfServices} services from {len(set(mapService2App))} apps")
    
    # Create device definitions
    myDevices = {}
    if 'entity' in network_data:
        # Format: {"entity": [...], "link": [...]}
        for entity in network_data['entity']:
            entity_id = entity['id']
            myDevices[entity_id] = {
                "RAM": entity.get('RAM', 10),
                "IPT": entity.get('IPT', 1000)
            }
    elif 'nodes' in network_data:
        # Format: {"nodes": [...], "edges": [...]}
        for node in network_data['nodes']:
            node_id = node['id']
            myDevices[node_id] = {
                "RAM": node.get('RAM', 10),
                "IPT": node.get('IPT', 1000)
            }
    
    # Find cloud node (usually the highest ID or type="CLOUD")
    cloudId = max(G.nodes())
    entities = network_data.get('entity', network_data.get('nodes', []))
    for entity in entities:
        if entity.get('type') == 'CLOUD':
            cloudId = entity['id']
            break
    
    # Find gateways
    allTheGtws = []
    for entity in entities:
        if entity.get('type') == 'GATEWAY':
            allTheGtws.append(entity['id'])
    
    if not allTheGtws:
        # Use first few nodes as gateways
        allTheGtws = list(G.nodes())[:min(3, len(G.nodes()))]
    
    # Load user services from usersDefinition.json
    users_path = os.path.join('exp_rev', 'usersDefinition.json')
    userServices = []
    if os.path.exists(users_path):
        with open(users_path, 'r') as f:
            users_data = json.load(f)
        
        # Extract user-service mappings
        for source in users_data['sources']:
            user_id = source['id_resource']
            app_name = source['app']
            # Find service ID for this app
            for service_id, app_id in enumerate(mapService2App):
                if app_id == app_name:
                    userServices.append((user_id, service_id))
                    break
    else:
        print("No user definition found, using generated user services")
        # Generate some user services
        for i in range(min(20, numberOfServices * 2)):
            user_id = random.choice(list(G.nodes()))
            service_id = random.randint(0, numberOfServices - 1)
            userServices.append((user_id, service_id))
    
    myServicesResources = {i: servicesResources[i] for i in range(numberOfServices)}
    
    # Create network distances
    networkdistances = {}
    for i in G.nodes():
        for j in G.nodes():
            try:
                # Use edge weights if available, otherwise use hop count
                if G.has_edge(i, j) and 'weight' in G[i][j]:
                    dist = G[i][j]['weight']
                else:
                    dist = nx.shortest_path_length(G, i, j)
                networkdistances[(i, j)] = dist
            except:
                networkdistances[(i, j)] = 1000  # Very large distance for unreachable nodes
    
    print(f"Created {len(userServices)} user service requests")
    print(f"Cloud node: {cloudId}")
    print(f"Gateway nodes: {allTheGtws}")
    
    # Create and run GA optimization
    try:
        ga_optimizer = create_ga_optimization(
            G=G,
            numberOfServices=numberOfServices,
            mapService2App=mapService2App,
            mapServiceId2ServiceName=mapServiceId2ServiceName,
            servicesResources=servicesResources,
            myDevices=myDevices,
            cloudId=cloudId,
            allTheGtws=allTheGtws,
            userServices=userServices,
            myServicesResources=myServicesResources,
            networkdistances=networkdistances
        )
        
        print("Running GA optimization...")
        result = ga_optimizer.solve()
        
        if result and result.get('initialAllocation'):
            print(f"GA optimization completed successfully!")
            print(f"Best fitness: {ga_optimizer.best_solution.fitness:.4f}")
            print(f"Number of allocations: {len(result['initialAllocation'])}")
            
            # Save to the expected location
            output_path = os.path.join('exp_rev', 'allocDefinitionGA.json')
            with open(output_path, 'w') as f:
                json.dump(result, f, indent=2)
            print(f"Allocation saved to {output_path}")
            
            return True
        else:
            print("No solution found or empty allocation")
            return False
            
    except Exception as e:
        print(f"Error during GA optimization: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # Set random seed for reproducibility
    random.seed(42)
    np.random.seed(42)
    
    print("Running GA optimization standalone...")
    success = run_ga_optimization_standalone()
    if success:
        print("\nGA optimization completed successfully!")
    else:
        print("\nGA optimization failed!")
        import sys
        sys.exit(1)
