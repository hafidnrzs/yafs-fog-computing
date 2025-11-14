# FSPCNoptimization.py
import os
import json
import time
import random
import networkx as nx


class FSPCN:
    """
    FSPCN: Fog Service Placement via Complex-network & GA (Azimzadeh et al., 2022 inspired)
    Phase 1 (GA): build communities (partitions) that group devices considering structure (links) and attributes (MIPS/RAM, link bw/latency).
    Phase 2: place services per application inside communities using neighborhood distance to users and resource constraints.

    Inputs (under cnf.resultFolder or "data"):
      - networkDefinition.json
      - appDefinition.json
      - usersDefinition.json

    Output:
      - allocDefinitionFSPCN.json
    """

    def __init__(self, ec, cnf):
        self.ec = ec
        self.cnf = cnf
        self.data_dir = getattr(cnf, "resultFolder", "data")
        random.seed(8)

        # GA hyperparameters
        self.K = getattr(cnf, "FSPCN_K", 3)                  # number of communities
        self.population_size = getattr(cnf, "FSPCN_POP", 40)
        self.generations = getattr(cnf, "FSPCN_GEN", 60)
        self.tournament_k = getattr(cnf, "FSPCN_TOUR", 3)
        self.elite_size = getattr(cnf, "FSPCN_ELITE", 2)
        self.mutation_rate = getattr(cnf, "FSPCN_MUT", 0.10)

        # fitness weights
        self.w_interior = 1.0
        self.w_cut = 1.0
        self.w_balance = 0.2

        # Load JSONs
        self.net = self._safe_load(os.path.join(self.data_dir, "networkDefinition.json"))
        self.app = self._safe_load(os.path.join(self.data_dir, "appDefinition.json"))
        self.users = self._safe_load(os.path.join(self.data_dir, "usersDefinition.json"))

        # Parse devices and graph
        self.devices = self._parse_devices(self.net)
        self.device_ids = [d["id"] for d in self.devices]
        self.device_index = {did: i for i, did in enumerate(self.device_ids)}
        self.devices_not_iot = [d for d in self.devices if str(d.get("type","")).upper() != "IOT"]
        if not self.devices_not_iot:
            self.devices_not_iot = self.devices[:]

        self.dev_type = {d["id"]: str(d.get("type","")).upper() for d in self.devices}
        self.dev_MIPS = {d["id"]: float(d.get("MIPS", 0.0)) for d in self.devices}
        self.dev_RAM  = {d["id"]: float(d.get("RAM", 0.0))  for d in self.devices}

        self.G = self._build_graph(self.net)

        # Parse application & mapping service->app
        self.services, self.service_RAM, self.service_to_app = self._parse_services(self.app)
        self.service_names = [s["name"] for s in self.services]

        # User sources
        self.source_nodes = self._parse_sources(self.users)
        if not self.source_nodes:
            cloud_nodes = [d["id"] for d in self.devices if self.dev_type[d["id"]] in ("CLOUD","CFG")]
            self.source_nodes = cloud_nodes if cloud_nodes else self.device_ids[:]

    # ---------------- utils ----------------
    def _safe_load(self, path):
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
        return {}

    def _parse_devices(self, net_json):
        res = []
        for d in net_json.get("entity", []):
            res.append({
                "id": int(d["id"]),
                "type": d.get("type","FOG"),
                "MIPS": float(d.get("MIPS", d.get("IPT", 0))),
                "RAM":  float(d.get("RAM", 0))
            })
        return res

    def _build_graph(self, net_json):
        G = nx.Graph()
        for d in self.devices:
            G.add_node(d["id"])
        for e in net_json.get("link", net_json.get("links", [])):
            if "s" not in e or "d" not in e: 
                continue
            s, d = int(e["s"]), int(e["d"])
            latency = float(e.get("latency", e.get("PR", 1.0)))
            bw = float(e.get("bw", e.get("BW", 1.0)))
            weight = latency / max(bw, 1e-9)
            G.add_edge(s, d, latency=latency, bw=bw, w=weight)
        return G

    def _parse_services(self, app_json):
        services, ram_map, svc2app = [], {}, {}
        apps = app_json if isinstance(app_json, list) else app_json.get("apps",[app_json]) if app_json else []
        for app in apps:
            app_name = app.get("name", "App0")
            for mod in app.get("module", []):
                t = str(mod.get("type","")).upper()
                if t in ("SERVICE","MODULE"):
                    name = mod.get("name")
                    if not name: 
                        continue
                    services.append({"name": name})
                    ram_map[name] = float(mod.get("RAM", 0))
                    svc2app[name] = app_name
        return services, ram_map, svc2app

    def _parse_sources(self, users_json):
        ids = []
        for s in users_json.get("sources", []):
            if "id_resource" in s:
                ids.append(int(s["id_resource"]))
        return sorted(set(i for i in ids if i in self.device_ids))

    # ---------------- Phase 1: GA ----------------
    def _init_population(self):
        non_iot_ids = [d["id"] for d in self.devices_not_iot]
        pop = []
        for _ in range(self.population_size):
            chrom = {}
            for did in non_iot_ids:
                chrom[did] = random.randint(0, max(0, self.K - 1))
            pop.append(chrom)
        return pop

    def _fitness_partition(self, chrom):
        label = {}
        for d in self.device_ids:
            label[d] = chrom.get(d, 0)  # IOT→0
        cut_cost, interior_reward = 0.0, 0.0
        for u, v, data in self.G.edges(data=True):
            w = float(data.get("w", 1.0))
            if label[u] == label[v]:
                interior_reward += 1.0 / (w + 1e-9)
            else:
                cut_cost += w
        cap = [0.0] * self.K
        for d in self.device_ids:
            cap[min(label[d], self.K-1)] += self.dev_MIPS.get(d, 0.0)
        mean_cap = sum(cap)/max(1,self.K)
        var_cap = sum((c - mean_cap)**2 for c in cap)/max(1,self.K)
        return (self.w_cut * cut_cost) - (self.w_interior * interior_reward) + (self.w_balance * var_cap)

    def _tournament(self, population, k):
        contestants = random.sample(population, k)
        return min(contestants, key=self._fitness_partition).copy()

    def _crossover(self, p1, p2):
        child1, child2 = {}, {}
        for d in self.device_ids:
            if d not in p1 and d not in p2:
                continue
            if random.random() < 0.5:
                child1[d], child2[d] = p1.get(d, 0), p2.get(d, 0)
            else:
                child1[d], child2[d] = p2.get(d, 0), p1.get(d, 0)
        return child1, child2

    def _mutate(self, chrom):
        for d in list(chrom.keys()):
            if random.random() < self.mutation_rate:
                chrom[d] = random.randint(0, max(0, self.K - 1))
        return chrom

    def _ga_partition(self):
        pop = self._init_population()
        best, best_fit = None, float("inf")
        for g in range(self.generations):
            scored = sorted(((self._fitness_partition(c), c) for c in pop), key=lambda x: x[0])
            if scored[0][0] < best_fit:
                best_fit, best = scored[0][0], scored[0][1].copy()
            elites = [c for _, c in scored[: self.elite_size]]
            new_pop = elites[:]
            while len(new_pop) < self.population_size:
                p1, p2 = self._tournament(pop, self.tournament_k), self._tournament(pop, self.tournament_k)
                c1, c2 = self._crossover(p1, p2)
                self._mutate(c1); self._mutate(c2)
                new_pop.append(c1)
                if len(new_pop) < self.population_size: new_pop.append(c2)
            pop = new_pop
        return best, best_fit

    # ---------------- Phase 2: placement ----------------
    def _shortest_paths_from_sources(self):
        cache = {}
        for s in self.source_nodes:
            try:
                cache[s] = nx.single_source_dijkstra_path_length(self.G, s, weight="w")
            except Exception:
                cache[s] = {}
        return cache

    def _community_labels_to_members(self, labels):
        com2nodes = {k: [] for k in range(self.K)}
        for d, c in labels.items():
            com2nodes[min(c, self.K-1)].append(d)
        return com2nodes

    def _place_services(self, labels):
        residual_RAM = self.dev_RAM.copy()
        user_score = [0.0] * self.K
        for s in self.users.get("sources", []):
            node = int(s.get("id_resource", -1))
            if node in self.device_ids:
                lam = float(s.get("lambda", 1))
                user_score[min(labels.get(node, 0), self.K-1)] += lam
        sp = self._shortest_paths_from_sources()

        def dev_dist(dev):
            return min((sp.get(s, {}).get(dev, float("inf")) for s in self.source_nodes), default=float("inf"))

        com2nodes = self._community_labels_to_members(labels)
        placements = []
        for sname in self.service_names:
            need_ram = self.service_RAM.get(sname, 0.0)
            order_com = sorted(range(self.K), key=lambda k: user_score[k], reverse=True)
            chosen, best_score = None, float("inf")
            for k in order_com:
                candidates = [d for d in com2nodes[k] if self.dev_type.get(d,"") != "IOT"]
                for dev in candidates:
                    if residual_RAM.get(dev,0.0) < need_ram: continue
                    score = dev_dist(dev) - 1e-6*self.dev_MIPS.get(dev,0.0)
                    if score < best_score: best_score, chosen = score, dev
                if chosen: break
            if not chosen:
                candidates = [d for d in self.device_ids if self.dev_type.get(d,"") in ("CLOUD","CFG") and residual_RAM.get(d,0.0) >= need_ram]
                for dev in candidates:
                    score = dev_dist(dev) - 1e-6*self.dev_MIPS.get(dev,0.0)
                    if score < best_score: best_score, chosen = score, dev
            if not chosen:
                chosen = max(self.device_ids, key=lambda d: self.dev_MIPS.get(d,0.0))
            residual_RAM[chosen] = max(0.0, residual_RAM.get(chosen,0.0) - need_ram)
            placements.append((sname, chosen))
        return placements

    # ---------------- API ----------------
    def solve(self):
        t0 = time.time()
        print("Starting FSPCN optimization....")
        best_labels, best_fit = self._ga_partition()
        print(f"[FSPCN] Best fitness: {best_fit:.6f}")
        placements = self._place_services(best_labels)

        initial_allocation = []
        for sname, dev in placements:
            initial_allocation.append({
                "app": self.service_to_app.get(sname, "App0"),
                "module_name": sname,
                "module": sname,
                "id_resource": int(dev)
            })
        cloud_types, fog_types = {"CLOUD","CFG"}, {"FOG"}
        n_cloud = sum(1 for _,d in placements if self.dev_type.get(d,"") in cloud_types)
        n_fog   = sum(1 for _,d in placements if self.dev_type.get(d,"") in fog_types)

        out = {
            "initialAllocation": initial_allocation,
            "info": {"optimizer":"FSPCN","K":self.K,"best_fitness":best_fit}
        }
        os.makedirs(self.data_dir, exist_ok=True)
        out_path = os.path.join(self.data_dir, "allocDefinitionFSPCN.json")
        with open(out_path,"w") as f: json.dump(out,f,indent=2)
        print(f"Services in cloud={n_cloud}, fog={n_fog}")
        print(f"{time.time()-t0:.3f}s for FSPCN optimization; saved {out_path}")

        nS, nD = len(self.service_names), len(self.device_ids)
        matrix = [[0]*nD for _ in range(nS)]
        for sid,(sname,dev) in enumerate(placements):
            j = self.device_index[int(dev)]
            matrix[sid][j] = 1
        return matrix
