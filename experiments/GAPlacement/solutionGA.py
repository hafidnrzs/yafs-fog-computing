import numpy
from typing import List, Tuple
import random

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
                
                self.repairChromosome()  # <--- Tambahkan repair di sini
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
                    
                    sol.repairChromosome()  # <--- Tambahkan repair di sini
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