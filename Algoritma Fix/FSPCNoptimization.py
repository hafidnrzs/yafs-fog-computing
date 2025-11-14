import time
import json
import math
import random
import statistics
import networkx as nx

class FSPCNoptimization:
    """
    FSPCN (Genetic-based, Complex-Network Features) placement
    ----------------------------------------------------------
    Phase 1: Community creation via a lightweight Genetic Algorithm (GA)
      - Chromosome: community assignment per node (0..K-1)
      - Fitness components (to minimize):
          * inter-community edge weight (cut)
          * imbalance of RAM capacity across communities (stddev)
          * avg distance from gateways to community nodes
    Phase 2: Service placement
      - Rank communities by proximity to gateways
      - For each service (per app): pick best community with enough RAM (first-fit),
        choose node with highest IPT in that community; fallback to neighbor community, then cloud.

    Notes:
      * Compact GA (small population/generations) to keep runtime light.
      * Attributes are read best-effort from ec.devices or G.nodes.
      * Output: allocDefinitionFSPCN.json (YAFS-compatible).
    """

    def __init__(self, ec, cnf):
        self.ec = ec
        self.cnf = cnf

        # statistics (prefixed to avoid name collision)
        self.statisticsDistancesRequestFSPCN = {}   # dist -> count
        self.statisticsNodesServicesFSPCN    = {}   # (nodeId, serviceId) -> count
        self.statisticsNodesRequestFSPCN     = {}   # nodeId -> count

        self.service2DevicePlacementMatrixFSPCN = []

    # -------------------- utilities --------------------
    def _vprint(self, *args):
        if getattr(self.cnf, "verbose_log", False):
            print(*args)

    def _get_device_attr(self, node_id, key, default=None):
        # try ec.devices first
        try:
            if hasattr(self.ec, "devices") and node_id in self.ec.devices:
                val = self.ec.devices[node_id].get(key, None)
                if val is not None:
                    return val
        except Exception:
            pass
        # then graph node attrs
        try:
            val = self.ec.G.nodes[node_id].get(key, None)
            if val is not None:
                return val
        except Exception:
            pass
        return default

    def _get_service_ram(self, serv_id):
        for key in ("serviceRAM", "servicesRAM", "serviceResources", "service_ram", "services_ram"):
            if hasattr(self.ec, key):
                try:
                    container = getattr(self.ec, key)
                    if isinstance(container, dict) and serv_id in container:
                        return int(container[serv_id])
                    if isinstance(container, list) and serv_id < len(container):
                        return int(container[serv_id])
                except Exception:
                    pass
        return 1  # minimal need if unknown

    def _pick_gateways(self):
        gws = []
        try:
            if hasattr(self.ec, "usersGateways") and self.ec.usersGateways:
                if isinstance(self.ec.usersGateways, dict):
                    for v in self.ec.usersGateways.values():
                        if isinstance(v, list):
                            gws.extend([x for x in v if isinstance(x, int)])
                        elif isinstance(v, int):
                            gws.append(v)
                elif isinstance(self.ec.usersGateways, list):
                    gws.extend([x for x in self.ec.usersGateways if isinstance(x, int)])
        except Exception:
            pass
        return list(dict.fromkeys(gws))

    def _min_distance_to_gateways(self, node_id, gateways):
        if not gateways:
            return math.inf
        dmin = math.inf
        for gw in gateways:
            try:
                d = nx.shortest_path_length(self.ec.G, source=gw, target=node_id, weight="weight")
                if d < dmin:
                    dmin = d
            except Exception:
                continue
        return dmin

    def _write_stats_allocation(self, srcId, servId, devId):
        try:
            if srcId is not None and devId is not None and devId in self.ec.G and srcId in self.ec.G:
                dist = nx.shortest_path_length(self.ec.G, source=srcId, target=devId, weight="weight")
                self.statisticsDistancesRequestFSPCN[dist] = self.statisticsDistancesRequestFSPCN.get(dist, 0) + 1
        except Exception:
            pass
        key = (devId, servId)
        self.statisticsNodesServicesFSPCN[key] = self.statisticsNodesServicesFSPCN.get(key, 0) + 1
        self.statisticsNodesRequestFSPCN[devId] = self.statisticsNodesRequestFSPCN.get(devId, 0) + 1

    # -------------------- GA for community creation --------------------
    
    def _ga_create_communities(self, nodes, K, pop_size=20, generations=10, mut_rate=0.05):
        # Precompute measurements
        gateways = self._pick_gateways()
        ram = {n: self._get_device_attr(n, "RAM", 0) for n in nodes}
        dist_gw = {n: self._min_distance_to_gateways(n, gateways) for n in nodes}
        nbrs = {u: list(self.ec.G[u]) for u in nodes}

        def fitness(assign):
            # 1) inter-community cut weight
            cut = 0.0
            for u in nodes:
                cu = assign[u]
                for v in nbrs[u]:
                    if v not in assign:
                        continue
                    if assign[v] != cu:
                        try:
                            w = self.ec.G[u][v].get("weight", 1.0)
                        except Exception:
                            w = 1.0
                        cut += w
            cut *= 0.5  # undirected graph

            # 2) RAM balance
            ram_per_c = [0]*K
            for n in nodes:
                ram_per_c[assign[n]] += ram.get(n, 0)
            ram_std = statistics.pstdev(ram_per_c) if K >= 2 else 0.0

            # 3) gateway proximity
            avg_dist_per_c = []
            for c in range(K):
                members = [n for n in nodes if assign[n] == c]
                if members:
                    avg_dist = sum(dist_gw[m] for m in members) / len(members)
                    avg_dist_per_c.append(avg_dist)
            gw_term = sum(avg_dist_per_c) / len(avg_dist_per_c) if avg_dist_per_c else 0.0

            return cut + ram_std + gw_term

        # Initialization
        population = []
        for _ in range(max(1, pop_size)):
            assign = {n: random.randrange(max(1, K)) for n in nodes}
            population.append(assign)

        # ---- Evaluate initial population (handles generations == 0) ----
        best_assign = None
        best_fit = math.inf
        scored = []
        for a in population:
            f = fitness(a)
            scored.append((f, a))
            if f < best_fit:
                best_fit, best_assign = f, a
        scored.sort(key=lambda x: x[0])

        # Evolution (if requested)
        for gen in range(max(0, generations)):
            new_pop = [scored[0][1]]
            if len(scored) > 1:
                new_pop.append(scored[1][1])
            while len(new_pop) < max(1, pop_size):
                a = min(random.sample(scored, k=min(3, len(scored))), key=lambda x: x[0])[1]
                b = min(random.sample(scored, k=min(3, len(scored))), key=lambda x: x[0])[1]

                # one-point crossover
                node_order = list(nodes)
                if len(node_order) > 1:
                    idx = random.randrange(1, len(node_order))
                    left = set(node_order[:idx])
                else:
                    left = set(node_order)

                child = {}
                for n in node_order:
                    child[n] = a[n] if n in left else b[n]

                # mutation
                for n in node_order:
                    if random.random() < mut_rate:
                        child[n] = random.randrange(max(1, K))

                # evaluate child
                f_child = fitness(child)
                new_pop.append(child)
                if f_child < best_fit:
                    best_fit, best_assign = f_child, child

            # prepare next generation
            scored = []
            for a in new_pop:
                f = fitness(a)
                scored.append((f, a))
            scored.sort(key=lambda x: x[0])

            self._vprint(f"[GA] gen {gen+1}/{max(0, generations)}, best_fitness={best_fit:.4f}")

        # Final guard: if best_assign somehow None (empty nodes etc.), assign all to community 0
        if best_assign is None:
            best_assign = {n: 0 for n in nodes}

        comms = [[] for _ in range(max(1, K))]
        for n in nodes:
            comms[best_assign[n]].append(n)
        return comms, best_fit

    # -------------------- placement --------------------
    def solve(self):
        t = time.time()
        print("Starting FSPCN optimization....")

        G = self.ec.G
        nodes = list(G.nodes)
        cloudId = getattr(self.ec, "cloudId", None)

        num_services = int(self.ec.numberOfServices)
        num_nodes    = len(nodes)
        print(f"Preparing node sets: {num_nodes} devices (cloud: {cloudId})")
        print(f"Preparing services and allocation structures: {num_services} services")

        # Placement matrix
        self.service2DevicePlacementMatrixFSPCN = [[0 for _ in range(num_nodes)] for _ in range(num_services)]

        # Phase 1: GA-based community creation
        print("Phase 1: Community creation (GA over complex-network features)")
        K = getattr(self.cnf, "fspcn_num_communities", None)
        if not isinstance(K, int) or K <= 0:
            K = max(2, int(math.sqrt(len(nodes)) // 2))
        pop = getattr(self.cnf, "fspcn_pop_size", 20)
        gens= getattr(self.cnf, "fspcn_generations", 10)
        mut = getattr(self.cnf, "fspcn_mutation", 0.05)

        comms, best_fit = self._ga_create_communities(nodes, K, pop_size=pop, generations=gens, mut_rate=mut)
        print(f"GA finished: K={K}, best_fitness={best_fit:.4f}")
        for i, c in enumerate(comms):
            self._vprint(f"  community {i}: size={len(c)}")

        # Rank communities by proximity to gateways
        gateways = self._pick_gateways()
        def comm_distance(cnodes):
            if not cnodes:
                return math.inf
            vals = []
            for n in cnodes:
                try:
                    d = min(nx.shortest_path_length(G, source=gw, target=n, weight="weight") for gw in gateways) if gateways else math.inf
                except Exception:
                    d = math.inf
                vals.append(d)
            return sum(vals)/len(vals) if vals else math.inf

        comm_order = list(range(K))
        comm_order.sort(key=lambda ci: comm_distance(comms[ci]))

        # Per-community ranking by IPT (desc)
        comm_ranked_nodes = {}
        for ci in range(K):
            cnodes = comms[ci]
            ranked = sorted(cnodes, key=lambda n: self._get_device_attr(n, "IPT", 0), reverse=True)
            comm_ranked_nodes[ci] = ranked

        # RAM left per node
        ram_left = {n: self._get_device_attr(n, "RAM", 10**12) for n in nodes}

        # Phase 2: placement
        print("Phase 2: Service placement over ranked communities")
        myAllocationList = []
        servicesInCloud = 0
        servicesInFog   = 0

        # app iteration
        sortedAppsDeadlines = sorted(getattr(self.ec, "appsDeadlines", {}).items(), key=lambda kv: kv[1]) \
                              if hasattr(self.ec, "appsDeadlines") else [(i, 0) for i in range(len(self.ec.apps))]

        app_to_services = {}
        if hasattr(self.ec, "apps"):
            for app_idx, APP in enumerate(self.ec.apps):
                try:
                    app_to_services[app_idx] = list(APP.nodes)
                except Exception:
                    app_to_services[app_idx] = list(list(APP.nodes))

        stat_src = gateways[0] if gateways else None
        print("Starting placement policy.....")

        for appId, _deadline in sortedAppsDeadlines:
            if appId not in app_to_services:
                self._vprint(f"Skipping app {appId}: not found in app_to_services")
                continue

            services_of_app = app_to_services[appId]
            num_serv_app = len(services_of_app)
            app_start = time.time()
            print(f"Solving app {appId}: {num_serv_app} services")

            for servId in services_of_app:
                need_ram = self._get_service_ram(servId)
                placed = False
                for ci in comm_order:
                    for dev in comm_ranked_nodes[ci]:
                        if cloudId is not None and dev == cloudId:
                            continue
                        if ram_left.get(dev, 0) >= need_ram:
                            ram_left[dev] = ram_left.get(dev, 0) - need_ram
                            try:
                                self.service2DevicePlacementMatrixFSPCN[servId][nodes.index(dev)] = 1
                            except Exception:
                                pass
                            try:
                                mod_name = str(self.ec.mapServiceId2ServiceName[servId])
                            except Exception:
                                mod_name = str(servId)
                            myAllocationList.append({
                                "app": str(appId),
                                "module_name": mod_name,
                                "id_resource": int(dev)
                            })
                            servicesInFog += 1
                            self._write_stats_allocation(stat_src, servId, dev)
                            placed = True
                            break
                    if placed:
                        break

                if not placed:
                    dev = cloudId
                    try:
                        self.service2DevicePlacementMatrixFSPCN[servId][nodes.index(dev)] = 1
                    except Exception:
                        pass
                    try:
                        mod_name = str(self.ec.mapServiceId2ServiceName[servId])
                    except Exception:
                        mod_name = str(servId)
                    myAllocationList.append({
                        "app": str(appId),
                        "module_name": mod_name,
                        "id_resource": int(dev) if dev is not None else int(nodes[0])
                    })
                    servicesInCloud += 1
                    self._write_stats_allocation(stat_src, servId, dev)

            print(f"App {appId} solved in {time.time() - app_start:.2f} seconds")

        # write JSON with safe resultFolder fallback
        allAlloc = {"initialAllocation": myAllocationList}
        result_folder = getattr(self.ec, "resultFolder", getattr(self.cnf, "resultFolder", "./"))
        out_path = result_folder + "/allocDefinitionFSPCN.json"
        with open(out_path, "w") as f:
            f.write(json.dumps(allAlloc))

        # summary
        print("Number of services in cloud (fspcn) (servicesInCloud): " + str(servicesInCloud))
        print("Number of services in fog (fspcn) (servicesInFog): " + str(servicesInFog))
        print(str(time.time() - t) + " time for FSPCN-based optimization")

        return self.service2DevicePlacementMatrixFSPCN
