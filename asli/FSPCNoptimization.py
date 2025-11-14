
from typing import List, Dict, Set
import random
import math
import json
import time
import operator

class FSPCNoptimization:
    def __init__(self, ec, cnf):
        self.ec = ec
        self.cnf = cnf
        self.service2DevicePlacementMatrix = [
            [0 for _ in range(len(self.ec.G.nodes))] for _ in range(self.ec.numberOfServices)
        ]
        self.populationSize = getattr(self.cnf, "populationSize", 40)
        self.generations = getattr(self.cnf, "generations", 60)
        self.crossoverProbability = getattr(self.cnf, "crossoverProbability", 0.9)
        self.mutationProbability = getattr(self.cnf, "mutationProbability", 0.2)
        self.NC = getattr(self.cnf, "nominalCommunities", max(4, int(math.sqrt(len(self.ec.G.nodes)))))
        random.seed(getattr(self.cnf, "randomSeed", 8))
        self.cloudId = getattr(self.ec, "cloudId", len(self.ec.G.nodes) - 1)
        self._shortest_path_cache = {}

        # ---- Compatibility shims ----
        if not hasattr(self.ec, "numberOfApps"):
            try:
                self.ec.numberOfApps = len(self.ec.apps)
            except Exception:
                try:
                    self.ec.numberOfApps = max(self.ec.mapService2App.values()) + 1
                except Exception:
                    raise AttributeError("Cannot infer numberOfApps")
        if not hasattr(self.ec, "appsUsers"):
            try:
                self.ec.appsUsers = getattr(self.ec, "mapApp2Users")
            except Exception:
                self.ec.appsUsers = {a: [0] for a in range(self.ec.numberOfApps)}
        if not hasattr(self.ec, "appsSourceMessage"):
            self.ec.appsSourceMessage = {a: {"bytes": 1.0} for a in range(self.ec.numberOfApps)}
        if not hasattr(self.ec, "appsTotalMIPS"):
            try:
                self.ec.appsTotalMIPS = {
                    a: sum(float(self.ec.appsServiceMIPS[a][s]) for s in self.ec.apps[a].nodes)
                    for a in range(self.ec.numberOfApps)
                }
            except Exception:
                self.ec.appsTotalMIPS = {a: 1.0 for a in range(self.ec.numberOfApps)}
        if not hasattr(self.ec, "appsServiceRAM"):
            try:
                self.ec.appsServiceRAM = {
                    a: {s: 1.0 for s in self.ec.apps[a].nodes} for a in range(self.ec.numberOfApps)
                }
            except Exception:
                nserv = getattr(self.ec, "numberOfServices", None)
                if nserv is None:
                    nserv = len(getattr(self.ec, "mapService2App", {}))
                self.ec.appsServiceRAM = {0: {s: 1.0 for s in range(nserv)}}
        if not hasattr(self.ec, "cloudId"):
            self.ec.cloudId = len(self.ec.G.nodes) - 1
    
    def solve(self):
        t0 = time.time()
        print("Starting FSPCN optimization...", flush=True)
        print("Phase 1: GA-based community formation...", flush=True)

        best_chrom, comm2nodes = self._ga_build_balanced_communities()

        print(f"Phase 1 done. #communities={len(comm2nodes)}", flush=True)
        print("Phase 2: Priority placement (ranking by SP + common-neighbors) ...", flush=True)

        self._priority_placement(comm2nodes)
        self._reorganize_free_nodes_and_retry(comm2nodes)
        self._ensure_fallback_to_cloud()
        self._write_allocation_json()

        print(f"{time.time()-t0:.2f}s time for FSPCN optimization", flush=True)

        return self.service2DevicePlacementMatrix

    # -------------------- GA COMMUNITY FORMATION --------------------
    def _ga_build_balanced_communities(self):
        num_nodes = len(self.ec.G.nodes)
        population = [self._random_chrom(num_nodes) for _ in range(self.populationSize)]
        scores = [self._fitness(ch) for ch in population]
        best_idx = min(range(len(scores)), key=lambda i: scores[i])
        best = population[best_idx][:]
        best_score = scores[best_idx]
        print(f"[FSPCN] init best fitness={best_score:.4f}", flush=True)
        
        for g in range(self.generations):
            if ((g+1) % max(1, self.generations//5) == 0) or g == 0:
                print(f"[FSPCN][GA] generation {g+1}/{self.generations} ...", flush=True)

            new_pop = []
            new_pop.append(best[:])  # elitism
            while len(new_pop) < self.populationSize:
                p1 = self._tournament(population, scores)
                p2 = self._tournament(population, scores)
                c1, c2 = p1[:], p2[:]
                if random.random() < self.crossoverProbability:
                    c1, c2 = self._two_point_crossover(p1, p2)
                if random.random() < self.mutationProbability:
                    self._mutate_inplace(c1)
                if random.random() < self.mutationProbability:
                    self._mutate_inplace(c2)
                new_pop.extend([c1, c2])
            population = new_pop[: self.populationSize]
            scores = [self._fitness(ch) for ch in population]
            bi = min(range(len(scores)), key=lambda i: scores[i])
            if scores[bi] < best_score:
                best, best_score = population[bi][:], scores[bi]
        comm2nodes = self._decode_chromosome(best)
        return best, comm2nodes

    def _random_chrom(self, n: int):
        return [random.randrange(self.NC) for _ in range(n)]
    
    def _two_point_crossover(self, a: List[int], b: List[int]):
        if len(a) < 3:
            return a[:], b[:]
        i = random.randint(1, len(a)-2)
        j = random.randint(i+1, len(a)-1)
        c1 = a[:i] + b[i:j] + a[j:]
        c2 = b[:i] + a[i:j] + b[j:]
        return c1, c2
    
    def _mutate_inplace(self, chrom: List[int]):
        idx = random.randrange(len(chrom))
        chrom[idx] = random.randrange(self.NC)
    
    def _tournament(self, pop: List[List[int]], scores: List[float], k=2):
        cand = random.sample(range(len(pop)), k)
        best = min(cand, key=lambda i: scores[i])
        return pop[best][:]
    
    def _decode_chromosome(self, chrom: List[int]) -> Dict[int, Set[int]]:
        import networkx as nx
        label2nodes: Dict[int, list] = {}
        for node_id, label in enumerate(chrom):
            label2nodes.setdefault(label, []).append(node_id)
        comm2nodes: Dict[int, Set[int]] = {}
        new_id = 0
        for _, nodes in label2nodes.items():
            if not nodes:
                continue
            sub = self.ec.G.subgraph(nodes)
            for cc in nx.connected_components(sub.to_undirected()):
                if len(cc) == 0:
                    continue
                comm2nodes[new_id] = set(cc)
                new_id += 1
        return comm2nodes

    def _fitness(self, chrom: List[int]):
        import statistics
        comm2nodes = self._decode_chromosome(chrom)
        if not comm2nodes:
            return 1e9
        
        cpu_totals, ram_totals, stor_totals, sizes = [], [], [], []
        for _, nodes in comm2nodes.items():
            sizes.append(len(nodes))
            cpu = sum(float(self.ec.devices[n]["IPT"]) for n in nodes)
            ram = sum(float(self.ec.devices[n]["RAM"]) for n in nodes)
            sto = sum(float(self.ec.devices[n].get("STO", 0.0)) for n in nodes)
            cpu_totals.append(cpu); ram_totals.append(ram); stor_totals.append(sto)
        def cv(x):
            if len(x) <= 1:
                return 0.0
            m = sum(x)/len(x)
            if m == 0: 
                return 0.0
            var = statistics.pvariance(x)
            return math.sqrt(var)/m
        cpu_cv = cv(cpu_totals); ram_cv = cv(ram_totals); stor_cv = cv(stor_totals); size_cv = cv(sizes)
        
        bw_vals, pr_vals = [], []
        subgraph = self.ec.G
        for _, nodes in comm2nodes.items():
            sub = subgraph.subgraph(nodes)
            if sub.number_of_edges() == 0:
                pr_vals.append(1.0); bw_vals.append(0.0); continue
            bw_sum, pr_sum, cnt = 0.0, 0.0, 0
            for u, v, attrs in sub.edges(data=True):
                bw_sum += float(attrs.get("BW", 1.0))
                pr_sum += float(attrs.get("PR", 1.0))
                cnt += 1
            bw_vals.append(bw_sum / max(cnt, 1))
            pr_vals.append(pr_sum / max(cnt, 1))
        def safe_avg(x):
            return sum(x)/len(x) if len(x)>0 else 0.0
        def safe_cv(x):
            return 0.0 if len(x) <= 1 else cv(x)
        bw_cv = safe_cv(bw_vals); pr_cv = safe_cv(pr_vals)
        pr_global_pen = safe_avg(pr_vals)
        bw_global_pen = - safe_avg(bw_vals)
        w_cpu, w_ram, w_sto, w_size = 1.0, 1.0, 0.5, 0.5
        w_bwcv, w_prcv, w_prg, w_bwg = 0.5, 0.5, 0.25, 0.25
        fitness = (
            w_cpu*cpu_cv + w_ram*ram_cv + w_sto*stor_cv + w_size*size_cv +
            w_bwcv*bw_cv + w_prcv*pr_cv + w_prg*pr_global_pen + w_bwg*bw_global_pen
        )
        return fitness

    # -------------------- PRIORITY PLACEMENT --------------------
    def _priority_placement(self, comm2nodes: Dict[int, Set[int]]):
        placed_apps = 0
        total_apps = int(self.ec.numberOfApps)
        for appId in range(self.ec.numberOfApps):
            t_app = time.time()
            self._weight_network(appId)
            placed_for_app = False
            for userId in self.ec.appsUsers[appId]:
                ranked = self._rank_communities_for_user(userId, comm2nodes)
                for cid in ranked:
                    if self._place_app_in_community(appId, userId, sorted(list(comm2nodes[cid]))):
                        placed_for_app = True
                        break
                if placed_for_app:
                    break
            dt = time.time() - t_app
            status = "placed" if placed_for_app else "fallback/cloud"
            print(f"App {appId} {status} in {dt:.2f} seconds", flush=True)
            if placed_for_app:
                placed_apps += 1
        print(f"FSPCN placed apps: {placed_apps}/{total_apps}", flush=True)
        return

    def _rank_communities_for_user(self, userId: int, comm2nodes: Dict[int, Set[int]]):
        scores = []
        for cid, nodes in comm2nodes.items():
            dmin = min(self._sp(userId, n) for n in nodes)
            cn_count = self._avg_common_neighbors(userId, nodes)
            internal_edges = self._internal_edges_count(nodes)
            scores.append((cid, dmin, -cn_count, -internal_edges))
        scores.sort(key=lambda x: (x[1], x[2], x[3]))
        return [cid for cid, *_ in scores]

    def _sp(self, a: int, b: int):
        key = (a, b)
        if key in self._shortest_path_cache:
            return self._shortest_path_cache[key]
        try:
            import networkx as nx
            d = nx.shortest_path_length(self.ec.G, source=a, target=b, weight="weight")
        except Exception:
            d = 1e6
        self._shortest_path_cache[key] = d
        return d

    def _avg_common_neighbors(self, userId: int, nodes: Set[int]):
        import networkx as nx
        G = self.ec.G.to_undirected()
        user_neighbors = set(G.neighbors(userId)) if userId in G else set()
        s = 0.0; c = 0
        for n in nodes:
            nn = set(G.neighbors(n)) if n in G else set()
            s += len(user_neighbors.intersection(nn))
            c += 1
        return s / max(c, 1)

    def _internal_edges_count(self, nodes: Set[int]):
        G = self.ec.G
        cnt = 0
        for u in nodes:
            for v in nodes:
                if u < v and G.has_edge(u, v):
                    cnt += 1
        return cnt

    def _weight_network(self, appId: int):
        size = float(self.ec.appsSourceMessage[appId]["bytes"])
        for e in self.ec.G.edges:
            self.ec.G[e[0]][e[1]]["weight"] = float(self.ec.G[e[0]][e[1]]["PR"]) + (size / float(self.ec.G[e[0]][e[1]]["BW"]))

    def _place_app_in_community(self, appId: int, clientId: int, candidateCommunity: List[int]):
        servicesToPlace = set(self.ec.apps[appId].nodes)
        orderedDevices = self._devices_first_fit_desc(candidateCommunity, clientId, appId)
        availableResourcesNodes: Dict[int, float] = {}
        for dev in orderedDevices:
            availableResourcesNodes[dev] = float(self.ec.devices[dev]["RAM"])
        tc_layers = self._generate_tc_partitions(appId)
        placed = set()
        for dev in orderedDevices:
            for partition in tc_layers:
                for closure in partition:
                    if closure.issubset(placed):
                        continue
                    total_ram = sum(self.ec.appsServiceRAM[appId][s] for s in closure)
                    if total_ram <= availableResourcesNodes[dev]:
                        for sid in closure:
                            self._place_service(sid, dev)
                        availableResourcesNodes[dev] -= total_ram
                        placed |= closure
                        if placed == servicesToPlace:
                            return True
        return False

    def _devices_first_fit_desc(self, community: List[int], clientId: int, appId: int):
        mips_ = float(self.ec.appsTotalMIPS[appId])
        nodeFitness: Dict[int, float] = {}
        for devId in community:
            processTime = mips_ / float(self.ec.devices[devId]["IPT"])
            netTime = self._sp(clientId, devId)
            nodeFitness[devId] = processTime + netTime
        sorted_ = sorted(nodeFitness.items(), key=operator.itemgetter(1))
        return [i[0] for i in sorted_]

    def _generate_tc_partitions(self, appId: int):
        import networkx as nx
        G = self.ec.apps[appId]
        entries = [n for n in G.nodes if G.in_degree(n) == 0]
        if not entries:
            entries = [list(G.nodes)[0]]
        layers = []
        first = set()
        for e in entries:
            first |= nx.descendants(G, e) | {e}
        layers.append([first])
        visited = set(first)
        frontier = set()
        for e in entries:
            frontier |= set(G.successors(e))
        while frontier:
            layer_sets = []
            new_frontier = set()
            for n in frontier:
                clo = nx.descendants(G, n) | {n}
                layer_sets.append(clo)
                new_frontier |= set(G.successors(n))
            layers.append(layer_sets)
            frontier = new_frontier - visited
            for s in layer_sets:
                visited |= s
        remaining = set(G.nodes) - set().union(*[set().union(*layer) if isinstance(layer, list) else set() for layer in layers])
        if remaining:
            layers.append([{n} for n in remaining])
        layers = [sorted(layer, key=lambda s: -len(s)) for layer in layers]
        return layers

    def _place_service(self, serviceId: int, devId: int):
        self.service2DevicePlacementMatrix[serviceId][devId] = 1

    # -------------------- REORGANIZE & RETRY --------------------
    def _reorganize_free_nodes_and_retry(self, comm2nodes: Dict[int, Set[int]]):
        hosted_nodes = set()
        for sid, row in enumerate(self.service2DevicePlacementMatrix):
            for did, v in enumerate(row):
                if v == 1 and did != self.cloudId:
                    hosted_nodes.add(did)
        all_nodes = set(range(len(self.ec.G.nodes)))
        free_nodes = list(all_nodes - hosted_nodes - {self.cloudId})
        if not free_nodes:
            return
        import networkx as nx
        sub = self.ec.G.subgraph(free_nodes)
        start_cid = max(comm2nodes.keys(), default=-1) + 1
        for comp in nx.connected_components(sub.to_undirected()):
            if comp:
                comm2nodes[start_cid] = set(comp)
                start_cid += 1
        not_complete = self._apps_not_fully_placed()
        for appId in not_complete:
            for userId in self.ec.appsUsers[appId]:
                ranked = self._rank_communities_for_user(userId, comm2nodes)
                for cid in ranked:
                    if self._app_fully_placed(appId):
                        break
                    self._place_app_in_community(appId, userId, sorted(list(comm2nodes[cid])))

    def _apps_not_fully_placed(self):
        result = []
        for appId in range(self.ec.numberOfApps):
            servs = set(self.ec.apps[appId].nodes)
            if not self._all_services_have_device(servs):
                result.append(appId)
        return result

    def _app_fully_placed(self, appId: int):
        servs = set(self.ec.apps[appId].nodes)
        return self._all_services_have_device(servs)
    
    def _all_services_have_device(self, services: Set[int]):
        for sid in services:
            row = self.service2DevicePlacementMatrix[sid]
            if sum(int(x) for x in row) == 0:
                return False
        return True

    # -------------------- UTIL --------------------
    def _ensure_fallback_to_cloud(self):
        for servId, row in enumerate(self.service2DevicePlacementMatrix):
            if isinstance(row, list) and sum(int(x) for x in row) == 0:
                self.service2DevicePlacementMatrix[servId][self.cloudId] = 1

    def _write_allocation_json(self):
        allAlloc = {}
        myAllocationList = []
        servicesInFog = 0
        servicesInCloud = 0
        for idServ in range(self.ec.numberOfServices):
            placed_any = False
            for idDevice in range(len(self.ec.G.nodes)):
                if self.service2DevicePlacementMatrix[idServ][idDevice] == 1 and idDevice != self.cloudId:
                    myAllocation = {
                        "app": self.ec.mapService2App[idServ],
                        "module_name": self.ec.mapServiceId2ServiceName[idServ],
                        "id_resource": idDevice,
                    }
                    myAllocationList.append(myAllocation)
                    servicesInFog += 1
                    placed_any = True
            myAllocation = {
                "app": self.ec.mapService2App[idServ],
                "module_name": self.ec.mapServiceId2ServiceName[idServ],
                "id_resource": self.cloudId,
            }
            myAllocationList.append(myAllocation)
            servicesInCloud += 1 if not placed_any else 0

        allAlloc["initialAllocation"] = myAllocationList
        with open(self.cnf.resultFolder + "/allocDefinitionFSPCN.json", "w") as f:
            f.write(json.dumps(allAlloc))
        print("Number of services in cloud (FSPCN):", servicesInCloud, flush=True)
        print("Number of services in fog (FSPCN):", servicesInFog, flush=True)
