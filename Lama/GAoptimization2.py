
import time
import json
import random
import operator
import networkx as nx
from networkx.exception import NetworkXNoPath

class GAoptimization:
    """
    Single-file Genetic Algorithm placement with the same interface/style as CNoptimization/ILPoptimization.

    Usage:
        ga = GAoptimization(ec, cnf)
        matrix = ga.solve()  # also writes allocDefinitionGA.json to cnf.resultFolder

    Expects:
        - ec: experimentConfiguration instance with attributes used by CN/ILP, e.g.:
            G (nx.Graph), apps (list of DiGraph), numberOfServices (int),
            nodeResources (list[float]), nodeSpeed (list[float]), cloudId (int),
            mapService2App (dict[int->int]), mapServiceId2ServiceName (dict[int->str]),
            appsTotalMIPS (dict[int->float]), appsResources (dict[int->{servId:res}]),
            devices (dict[int->{'IPT':float,...}]), appsDeadlines (dict), appsRequests (dict[appId]->list[gatewayIds])
        - cnf: config object with fields used elsewhere:
            resultFolder (str), verbose_log (bool) optional GA params:
            populationSize, generations, crossoverProbability, mutationProbability, populationSeed, evolutionSeed
    """

    # ------------------------------ API -------------------------------------
    def __init__(self, ec, cnf):
        self.ec = ec
        self.cnf = cnf
        self.nodeBussyResources = {}

        # GA params with sensible defaults
        self.populationSize = getattr(cnf, "populationSize", 40)
        self.generations = getattr(cnf, "generations", 60)
        self.crossoverProb = getattr(cnf, "crossoverProbability", 0.8)
        self.mutationProb = getattr(cnf, "mutationProbability", 0.15)
        pop_seed = getattr(cnf, "populationSeed", 8)
        evo_seed = getattr(cnf, "evolutionSeed", 13)
        self.rndPOP = random.Random(pop_seed)
        self.rndEVOL = random.Random(evo_seed)

    def solve(self):
        t0 = time.time()

        # init
        for i in self.ec.G.nodes:
            self.nodeBussyResources[i] = 0.0

        self.service2DevicePlacementMatrix = [
            [0 for _ in range(len(self.ec.G.nodes))]
            for _ in range(self.ec.numberOfServices)
        ]

        # Build a list of service ids to place
        service_ids = list(range(self.ec.numberOfServices))

        # Seed population from greedy heuristic (CN-like ordering) to accelerate convergence
        population = [ self._greedy_chromosome(service_ids) ]
        while len(population) < self.populationSize:
            population.append(self._random_feasible_chromosome(service_ids))

        best = min(population, key=self._fitness)

        # GA loop
        for _gen in range(self.generations):
            new_pop = []
            # Elitism: keep the best
            new_pop.append(best.copy())

            # Fill rest via selection+crossover+mutation
            while len(new_pop) < self.populationSize:
                p1 = self._tournament(population, k=3)
                p2 = self._tournament(population, k=3)
                c1, c2 = self._crossover(p1, p2) if self.rndEVOL.random() < self.crossoverProb else (p1.copy(), p2.copy())
                if self.rndEVOL.random() < self.mutationProb:
                    self._mutate(c1)
                if self.rndEVOL.random() < self.mutationProb:
                    self._mutate(c2)
                # Repair infeasible
                self._repair(c1)
                self._repair(c2)
                new_pop.extend([c1, c2])

            population = new_pop[:self.populationSize]
            current_best = min(population, key=self._fitness)
            if self._fitness(current_best) < self._fitness(best):
                best = current_best

        # Apply best to matrix
        self._apply_chromosome(best)

        # Ensure cloud fallback for any unplaced service
        self._ensure_fallback_to_cloud()

        # Write JSON allocation definition (same style as CN)
        self._write_allocation_json()

        if getattr(self.cnf, "verbose_log", False):
            print("GA placement finished in {:.3f}s".format(time.time() - t0))

        return self.service2DevicePlacementMatrix

    # -------------------------- Chromosome ops ------------------------------
    # Chromosome representation: dict {servId: devId}

    def _random_feasible_chromosome(self, service_ids):
        chrom = {}
        for servId in service_ids:
            appId = int(self.ec.mapService2App[servId])
            req = self.ec.appsResources[appId][servId]
            # pick random device, prefer fog devices (all nodes except cloud)
            candidates = list(self.ec.G.nodes)
            self.rndPOP.shuffle(candidates)
            devId = None
            for d in candidates:
                if self._device_feasible_for(chrom, d, req):
                    devId = d; break
            if devId is None:
                devId = self.ec.cloudId
            chrom[servId] = devId
        return chrom

    def _greedy_chromosome(self, service_ids):
        chrom = {}
        # approximate CN ordering by apps with shortest deadline first
        for appId, _deadline in sorted(self.ec.appsDeadlines.items(), key=operator.itemgetter(1)):
            nodesWithClients = self.ec.appsRequests[appId]
            for servId in [s for s in service_ids if int(self.ec.mapService2App[s]) == appId]:
                # take best device wrt net+proc for any client of this app
                order = sorted(self.ec.G.nodes, key=lambda d: self._device_score(appId, nodesWithClients, d))
                chosen = None
                req = self.ec.appsResources[appId][servId]
                for d in order:
                    if self._device_feasible_for(chrom, d, req):
                        chosen = d; break
                chrom[servId] = chosen if chosen is not None else self.ec.cloudId
        return chrom

    def _apply_chromosome(self, chrom):
        # reset busy map & matrix
        for i in self.ec.G.nodes:
            self.nodeBussyResources[i] = 0.0
        for r in self.service2DevicePlacementMatrix:
            for j in range(len(r)):
                r[j] = 0

        for servId, devId in chrom.items():
            self.service2DevicePlacementMatrix[servId][devId] = 1
            appId = int(self.ec.mapService2App[servId])
            req = self.ec.appsResources[appId][servId]
            self.nodeBussyResources[devId] += req

    # ------------------------------- Fitness --------------------------------

    def _fitness(self, chrom):
        # lower is better
        total, count, penalty = 0.0, 0, 0.0
        # build temporary device loads
        loads = {d:0.0 for d in self.ec.G.nodes}
        for servId, devId in chrom.items():
            appId = int(self.ec.mapService2App[servId])
            req = self.ec.appsResources[appId][servId]
            loads[devId] += req
            # penalty if over-capacity
            if loads[devId] - self.ec.nodeResources[devId] > 1e-9:
                penalty += 10.0

            clients = self.ec.appsRequests[appId]
            net = min(self._net_time(c, devId) for c in clients) if clients else 0.0
            proc = self._proc_time(appId, devId)
            total += (net + proc)
            count += 1
            if devId == self.ec.cloudId:
                penalty += 1.0
        return (total / max(count,1)) + penalty

    def _device_score(self, appId, clients, devId):
        proc = self._proc_time(appId, devId)
        if not clients: return proc
        best_net = float('inf')
        for c in clients:
            try:
                best_net = min(best_net, nx.shortest_path_length(self.ec.G, source=c, target=devId, weight="weight"))
            except NetworkXNoPath:
                pass
        return proc + (best_net if best_net!=float('inf') else 1e9)

    # --------------------------- GA primitives ------------------------------

    def _tournament(self, population, k=3):
        contestants = self.rndEVOL.sample(population, k=min(k, len(population)))
        return min(contestants, key=self._fitness).copy()

    def _crossover(self, p1, p2):
        # uniform crossover per service
        c1, c2 = {}, {}
        for servId in p1.keys():
            if self.rndEVOL.random() < 0.5:
                c1[servId] = p1[servId]
                c2[servId] = p2.get(servId, p1[servId])
            else:
                c1[servId] = p2.get(servId, p1[servId])
                c2[servId] = p1[servId]
        return c1, c2

    def _mutate(self, chrom):
        # random service -> random nearby device (bias to lower net+proc)
        if not chrom: return
        servId = self.rndEVOL.choice(list(chrom.keys()))
        appId = int(self.ec.mapService2App[servId])
        clients = self.ec.appsRequests[appId]
        order = sorted(self.ec.G.nodes, key=lambda d: self._device_score(appId, clients, d))
        # choose one among top-k candidates
        k = max(1, int(0.2 * len(order)))
        chrom[servId] = self.rndEVOL.choice(order[:k])

    def _repair(self, chrom):
        # ensure capacity by moving overloaded services to cloud as last resort
        loads = {d:0.0 for d in self.ec.G.nodes}
        for servId, devId in chrom.items():
            appId = int(self.ec.mapService2App[servId])
            loads[devId] += self.ec.appsResources[appId][servId]
        for servId, devId in list(chrom.items()):
            appId = int(self.ec.mapService2App[servId])
            req = self.ec.appsResources[appId][servId]
            if loads[devId] - self.ec.nodeResources[devId] > 1e-9:
                # move to a feasible device if possible, else cloud
                moved = False
                for d in self.ec.G.nodes:
                    if loads.get(d,0.0) + req <= self.ec.nodeResources[d] + 1e-9:
                        chrom[servId] = d
                        loads[devId] -= req
                        loads[d] += req
                        moved = True
                        break
                if not moved:
                    chrom[servId] = self.ec.cloudId

    # ------------------------------ Helpers ---------------------------------

    def _net_time(self, clientId, devId):
        try:
            return nx.shortest_path_length(self.ec.G, source=clientId, target=devId, weight="weight")
        except NetworkXNoPath:
            return float("inf")

    def _proc_time(self, appId, devId):
        mips_ = float(self.ec.appsTotalMIPS[appId])
        ipt = float(self.ec.devices[devId].get("IPT", 1.0))
        return mips_ / ipt if ipt > 0 else float("inf")

    def _device_feasible_for(self, chrom, devId, req):
        # compute temp load including items already assigned in chrom
        load = sum(self.ec.appsResources[int(self.ec.mapService2App[s])][s]
                   for s, d in chrom.items() if d == devId)
        return (self.ec.nodeResources[devId] - load) >= req

    def _ensure_fallback_to_cloud(self):
        cloud = self.ec.cloudId
        for servId in range(self.ec.numberOfServices):
            if sum(self.service2DevicePlacementMatrix[servId]) == 0:
                self.service2DevicePlacementMatrix[servId][cloud] = 1

    def _write_allocation_json(self):
        allAlloc = {}
        myAllocationList = []

        for idServ in range(self.ec.numberOfServices):
            for idDevice in range(len(self.ec.G.nodes)):
                if self.service2DevicePlacementMatrix[idServ][idDevice] == 1:
                    myAllocation = {
                        "app": self.ec.mapService2App[idServ],
                        "module_name": self.ec.mapServiceId2ServiceName[idServ],
                        "id_resource": idDevice
                    }
                    myAllocationList.append(myAllocation)

            # CN style: also add cloud entry
            myAllocation = {
                "app": self.ec.mapService2App[idServ],
                "module_name": self.ec.mapServiceId2ServiceName[idServ],
                "id_resource": self.ec.cloudId
            }
            myAllocationList.append(myAllocation)

        allAlloc["initialAllocation"] = myAllocationList

        out_path = self.cnf.resultFolder + "/allocDefinitionGA.json"
        with open(out_path, "w") as f:
            f.write(json.dumps(allAlloc))
