# ======= file: GA_GameServerOptimization.py =======
import time, random, json, itertools
import networkx as nx
from collections import defaultdict
from copy import deepcopy

class GA_GameServer:
    """
    Genetic Algorithm with penalties for latency-sensitive placement
    ec  : experimentConfiguration (G, devices, apps, requests, deadlines, resources)
    cnf : myConfig
    Asumsi: setiap 'app' mewakili satu 'group/session' (bisa kamu map sesuai datasetmu).
    """
    def __init__(self, ec, cnf,
                 pop_size=40, max_gen=80, elite_ratio=0.1,
                 crossover_rate=0.9, mutation_rate=0.01,
                 lambda_cap=10.0, lambda_lat=10.0, seed=8):
        self.ec  = ec
        self.cnf = cnf
        self.rng = random.Random(seed)
        self.pop_size = pop_size
        self.max_gen  = max_gen
        self.elite_ratio = elite_ratio
        self.crossover_rate = crossover_rate
        self.mutation_rate  = mutation_rate
        # penalty multipliers
        self.lam_cap = lambda_cap
        self.lam_lat = lambda_lat

        self.service2DevicePlacementMatrix = defaultdict(lambda: defaultdict(int))
        self.nodeStatistics = defaultdict(lambda: {"RAM_used":0,"n_services":0})
        self.allocations = []

    # ---------- util ----------
    def _weight_network_for_avg(self):
        # set weight global dengan rata-rata bytes agar shortest path mewakili latency
        if hasattr(self.ec, "appsSourceMessage") and len(self.ec.appsSourceMessage)>0:
            avg_bytes = sum(m["bytes"] for m in self.ec.appsSourceMessage)/float(len(self.ec.appsSourceMessage))
        else:
            avg_bytes = 10000.0
        for u,v in self.ec.G.edges:
            PR = float(self.ec.G[u][v].get("PR",1.0))
            BW = float(self.ec.G[u][v].get("BW",1.0))
            self.ec.G[u][v]["weight"] = PR + (avg_bytes / BW)

    # ---------- encoding ----------
    def _build_groups(self):
        """
        Sederhana: treat setiap app sebagai satu 'group'.
        Gen = device tempat 'server' group tsb diletakkan.
        """
        groups = list(self.ec.apps.keys())
        devices = [d for d in self.ec.devices.keys()]
        return groups, devices

    def _random_solution(self, groups, devices):
        return {g: self.rng.choice(devices) for g in groups}

    def _two_point_crossover(self, p1, p2, groups):
        if self.rng.random() > self.crossover_rate:
            return deepcopy(p1), deepcopy(p2)
        idxs = list(groups)
        i, j = sorted(self.rng.sample(range(len(idxs)), 2))
        c1, c2 = {}, {}
        for k, g in enumerate(idxs):
            if i <= k <= j:
                c1[g] = p2[g]
                c2[g] = p1[g]
            else:
                c1[g] = p1[g]
                c2[g] = p2[g]
        return c1, c2

    def _mutation(self, z, devices):
        if self.rng.random() < self.mutation_rate:
            g = self.rng.choice(list(z.keys()))
            z[g] = self.rng.choice(devices)

    # ---------- evaluasi ----------
    def _latency_group(self, group, dev):
        # latensi rata2 dari semua client group ke dev (pakai shortest path 'weight')
        clients = self.ec.appsRequests[group]
        if not clients: 
            return 0.0
        lat = 0.0; cnt=0
        for c in clients:
            try:
                d = nx.shortest_path_length(self.ec.G, source=c, target=dev, weight="weight")
            except nx.NetworkXNoPath:
                d = 1e9
            lat += d; cnt += 1
        return lat/float(cnt)

    def _cpu_cost(self, group, dev):
        # proxy biaya resource: RAM + 1/IPT (kecil lebih murah)
        ram = 0.0
        for servId in self.ec.apps[group].nodes:
            ram += float(self.ec.appsResources[group][servId])
        IPT = float(self.ec.devices[dev].get("IPT",1.0))
        return ram + (1.0/max(IPT,1e-6))

    def _penalty_capacity(self, z):
        # hitung total RAM per device
        usage = defaultdict(float)
        for g, dev in z.items():
            for s in self.ec.apps[g].nodes:
                usage[dev] += float(self.ec.appsResources[g][s])
        pen = 0.0
        for dev, used in usage.items():
            cap = float(self.ec.devices[dev].get("RAM",0))
            if used > cap:
                pen += (used - cap)  # linear excess
        return pen

    def _penalty_latency(self, z, Lmax_map=None):
        """
        Penalti jika latency rata2 group > Lmax (bisa bervariasi per group).
        Jika tidak ada Lmax_map, gunakan quantile-based dari jaringan secara global.
        """
        pen = 0.0
        for g, dev in z.items():
            lat = self._latency_group(g, dev)
            Lmax = Lmax_map[g] if Lmax_map and g in Lmax_map else 50.0  # default 50ms
            if lat > Lmax:
                pen += (lat - Lmax)
        return pen

    def _fitness(self, z, Lmax_map=None):
        # biaya resource + penalti kapasitas + penalti latency
        cost = 0.0
        for g, dev in z.items():
            cost += self._cpu_cost(g, dev)
            cost += self._latency_group(g, dev) * 0.1  # bobot kecil utk prefer dev dekat
        pen = self.lam_cap * self._penalty_capacity(z) + self.lam_lat * self._penalty_latency(z, Lmax_map)
        return cost + pen

    # ---------- GA utama ----------
    def solve(self):
        t0 = time.time()
        self._weight_network_for_avg()
        groups, devices = self._build_groups()

        # inisialisasi populasi: 80% feasible (kapasitas kira2), 20% acak
        P = []
        for _ in range(self.pop_size):
            if self.rng.random() < 0.8:
                # simple greedy untuk dapat feasible awal
                z = {}
                ram_left = {d: float(self.ec.devices[d].get("RAM",0)) for d in devices}
                for g in groups:
                    # pilih dev dengan RAM masih besar + dekat rata2
                    cand = []
                    for d in devices:
                        lat = self._latency_group(g, d)
                        cand.append((-(ram_left[d]) + lat, d))
                    cand.sort(key=lambda x: x[0])
                    for _, d in cand:
                        need = sum(float(self.ec.appsResources[g][s]) for s in self.ec.apps[g].nodes)
                        if ram_left[d] >= need:
                            z[g] = d
                            ram_left[d] -= need
                            break
                    if g not in z:
                        z[g] = self.rng.choice(devices)
                P.append(z)
            else:
                P.append(self._random_solution(groups, devices))

        # evolusi
        best = None; best_f = float("inf")
        for _ in range(self.max_gen):
            scored = [(self._fitness(z), z) for z in P]
            scored.sort(key=lambda x: x[0])
            if scored[0][0] < best_f:
                best_f, best = scored[0][0], deepcopy(scored[0][1])

            # elitism
            k_elite = max(1, int(self.elite_ratio*self.pop_size))
            Next = [deepcopy(z) for _,z in scored[:k_elite]]

            # crossover
            parents = [z for _,z in scored[:max(2, 2*k_elite)]]
            while len(Next) < self.pop_size:
                p1, p2 = self.rng.sample(parents, 2)
                c1, c2 = self._two_point_crossover(p1, p2, groups)
                self._mutation(c1, devices)
                if len(Next) < self.pop_size:
                    Next.append(c1)
                self._mutation(c2, devices)
                if len(Next) < self.pop_size:
                    Next.append(c2)
            P = Next

        # tulis solusi terbaik ke struktur YAFS
        # mapping service->device (semua service sebuah group ditempatkan di device yang sama)
        for g, dev in best.items():
            for s in self.ec.apps[g].nodes:
                self.service2DevicePlacementMatrix[s][dev] = 1
                self.nodeStatistics[dev]["n_services"] += 1
                need = float(self.ec.appsResources[g][s])
                self.nodeStatistics[dev]["RAM_used"] += need
                self.allocations.append({
                    "app": g,
                    "module_name": self.ec.mapServiceId2ServiceName[s],
                    "id_resource": dev
                })

        # export
        out = {"initialAllocation": self.allocations}
        with open(self.cnf.resultFolder + "/allocDefinitionGA_GameServer.json", "w") as f:
            f.write(json.dumps(out, indent=2))

        if self.cnf.verbose_log:
            print(f"[GA_GameServer] Done in {time.time()-t0:.2f}s; best_f={best_f:.3f}; alloc n={len(self.allocations)}")
        return self.service2DevicePlacementMatrix
