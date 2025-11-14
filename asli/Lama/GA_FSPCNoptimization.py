# ======= file: GA_FSPCNoptimization.py =======
import time, random, json, itertools, operator
import networkx as nx
from collections import defaultdict
from copy import deepcopy

class GA_FSPCN:
    """
    Genetic-based partition + placement (FSPCN-style)
    ec  : experimentConfiguration (punya G, devices, apps, resources, deadlines, requests, dll.)
    cnf : myConfig (folder hasil, flags)
    """
    def __init__(self, ec, cnf,
                 pop_size=30, max_gen=50, n_communities=6,
                 crossover_rate=0.9, mutation_rate=0.05, elite_ratio=0.2, seed=8):
        self.ec  = ec
        self.cnf = cnf
        self.rng = random.Random(seed)
        self.pop_size = pop_size
        self.max_gen  = max_gen
        self.nC       = n_communities
        self.crossover_rate = crossover_rate
        self.mutation_rate  = mutation_rate
        self.elite_ratio    = elite_ratio

        # output & stats
        self.service2DevicePlacementMatrix = defaultdict(lambda: defaultdict(int))
        self.nodeStatistics = defaultdict(lambda: {"RAM_used":0,"n_services":0})
        self.allocations = []  # list of {"app":id,"module_name":name,"id_resource":dev}

    # ---------- GA FASE-1: Partisi Komunitas ----------
    def _encode_random_partition(self, nodes):
        # kromosom: dict node->community_id
        return {n: self.rng.randrange(self.nC) for n in nodes}

    def _two_point_crossover(self, p1, p2, nodes):
        # Jika tidak jadi crossover atau jumlah node < 2, kembalikan salinan orang tua
        if self.rng.random() > self.crossover_rate or len(nodes) < 2:
            return deepcopy(p1), deepcopy(p2)

        idxs_len = len(nodes)
        # aman karena idxs_len >= 2
        i, j = sorted(self.rng.sample(range(idxs_len), 2))
        c1, c2 = {}, {}
        # iterasi nodes dengan indeks stabil
        for k, nd in enumerate(list(nodes)):
            if i <= k <= j:
                c1[nd] = p2[nd]
                c2[nd] = p1[nd]
            else:
                c1[nd] = p1[nd]
                c2[nd] = p2[nd]
        return c1, c2

    def _single_point_mutation(self, crom, nodes):
        if self.rng.random() < self.mutation_rate and nodes:
            nd = self.rng.choice(list(nodes))
            crom[nd] = self.rng.randrange(self.nC)


    def _fitness_partition(self, crom):
        """
        Komunitas 'seimbang' diukur dari dev-attributes:
        RAM, IPT (IPT=devices[dev]["IPT"]), ST (Storage optional), link BW/PR sekitar komunitas.
        Semakin kecil deviasi antar-komunitas, semakin baik (pakai var/imbalance sederhana).
        """
        # aggr komunitas
        agg = {c: {"RAM":0.0, "IPT":0.0, "N":0} for c in range(self.nC)}
        for dev, c in crom.items():
            if dev not in self.ec.devices:  # skip node non-device (jika ada)
                continue
            agg[c]["N"] += 1
            agg[c]["RAM"] += float(self.ec.devices[dev].get("RAM", 0))
            agg[c]["IPT"] += float(self.ec.devices[dev].get("IPT", 1.0))
        # normalisasi rata-rata per komunitas lalu hitung ketakseimbangan
        means = []
        for c in range(self.nC):
            if agg[c]["N"] > 0:
                means.append((
                    agg[c]["RAM"]/agg[c]["N"],
                    agg[c]["IPT"]/agg[c]["N"],
                ))
            else:
                means.append((0.0, 0.0))
        # var sederhana atas RAM & IPT rata2
        if len(means) == 0: return 1e9
        ram_vals = [m[0] for m in means]
        ipt_vals = [m[1] for m in means]
        def var(x):
            if len(x)==0: return 0.0
            mu = sum(x)/len(x)
            return sum((xi-mu)**2 for xi in x)/max(1,len(x))
        imbalance = var(ram_vals) + var(ipt_vals)
        # bonus sedikit untuk komunitas yg terhubung (menghindari komunitas terpisah)
        connectivity_pen = 0.0
        for c in range(self.nC):
            members = [n for n,v in crom.items() if v==c]
            if len(members)>1:
                subG = self.ec.G.subgraph(members)
                if not nx.is_connected(subG.to_undirected()):
                    connectivity_pen += 1.0
        return imbalance + 10.0*connectivity_pen

    def _evolve_partition(self):
        nodes = [n for n in self.ec.G.nodes if n in self.ec.devices]  # hanya device
        nodes = [n for n in self.ec.G.nodes if n in self.ec.devices]  # hanya device

        # Jika device 0 atau 1, partisi trivial: satu komunitas berisi nodes (bisa kosong / 1)
        if len(nodes) <= 1:
            return [nodes]  # [[node]] atau [[]]

        # init populasi
        P = [self._encode_random_partition(nodes) for _ in range(self.pop_size)]
        # loop GA
        for _ in range(self.max_gen):
            scored = [(self._fitness_partition(c), c) for c in P]
            scored.sort(key=lambda x: x[0])  # rendah = baik
            elites = [deepcopy(c) for _,c in scored[:max(1,int(self.elite_ratio*self.pop_size))]]

            # reproduksi
            elites = [deepcopy(c) for _, c in scored[:max(1, int(self.elite_ratio*self.pop_size))]]

            Next = elites[:]
            # Pastikan ada >= 2 parent; kalau populasi kecil, gandakan elit agar bisa di-sample
            parent_count = max(2, min(len(scored), max(2, len(elites) * 2)))
            parents = [deepcopy(c) for _, c in scored[:parent_count]]

            while len(Next) < self.pop_size:
                p1, p2 = self.rng.sample(parents, 2)
                c1, c2 = self._two_point_crossover(p1, p2, nodes)
                self._single_point_mutation(c1, nodes)
                Next.append(c1)
                if len(Next) < self.pop_size:
                    self._single_point_mutation(c2, nodes)
                    Next.append(c2)
            P = Next

        
        # best partition
        best = min(P, key=lambda c: self._fitness_partition(c))
        
        # komunitas → list node
        communities = defaultdict(list)
        for n,c in best.items():
            communities[c].append(n)
        
        # urutkan komunitas by size desc
        sorted_comms = sorted(communities.items(), key=lambda kv: len(kv[1]), reverse=True)
        return [lst for _,lst in sorted_comms if len(lst)>0]
    
    # ---------- placement FASE-2 ----------
    def _weight_network_for_app(self, appId):
        size = float(self.ec.appsSourceMessage[appId]["bytes"])
        for u,v in self.ec.G.edges:
            PR = float(self.ec.G[u][v].get("PR",1.0))
            BW = float(self.ec.G[u][v].get("BW",1.0))
            self.ec.G[u][v]["weight"] = PR + (size / BW)

    def _devices_sorted_by_fitness(self, candidate_nodes, clientId, appId, mips_need):
        order = []
        for devId in candidate_nodes:
            if devId not in self.ec.devices: 
                continue
            IPT = float(self.ec.devices[devId].get("IPT",1.0))
            proc = (mips_need / IPT) if IPT>0 else 1e9
            try:
                net  = nx.shortest_path_length(self.ec.G, source=clientId, target=devId, weight="weight")
            except nx.NetworkXNoPath:
                net = 1e9
            order.append((proc + net, devId))
        order.sort(key=lambda x: x[0])
        return [d for _,d in order]

    def _place_app_in_community(self, appId, clientId, community_nodes, tmpRAM):
        """ Greedy first-fit by fitness for each service; return (placed_ok, placement_dict) """
        placement = {}
        # total instruksi/mips app (boleh ubah ke per-service jika tersedia)
        mips_app = float(self.ec.appsTotalMIPS[appId])
        # urutkan kandidat device
        dev_order = self._devices_sorted_by_fitness(community_nodes, clientId, appId, mips_app)
        # tempatkan tiap service
        for servId in self.ec.apps[appId].nodes:
            ram_need = float(self.ec.appsResources[appId][servId])
            placed = False
            for devId in dev_order:
                if tmpRAM[devId] >= ram_need:
                    placement[servId] = devId
                    tmpRAM[devId] -= ram_need
                    placed = True
                    break
            if not placed:
                return False, {}
        return True, placement

    def _write_alloc_and_stats(self, appId, placement):
        for servId, devId in placement.items():
            # mapping & statistik
            self.service2DevicePlacementMatrix[servId][devId] = 1
            self.nodeStatistics[devId]["RAM_used"] += float(self.ec.appsResources[appId][servId])
            self.nodeStatistics[devId]["n_services"] += 1
            self.allocations.append({
                "app": appId,
                "module_name": self.ec.mapServiceId2ServiceName[servId],
                "id_resource": devId
            })

    def solve(self):
        t0 = time.time()
        # Fase-1: GA komunitas
        communities = self._evolve_partition()

        # RAM sementara (sisa kapasitas)
        tmpRAM = {dev: float(self.ec.devices[dev].get("RAM",0)) for dev in self.ec.devices.keys()}

        # urut app by deadline
        sortedApps = sorted(self.ec.appsDeadlines.items(), key=operator.itemgetter(1))
        for appId, _ in sortedApps:
            self._weight_network_for_app(appId)
            # untuk tiap client yang minta app ini
            for clientId in self.ec.appsRequests[appId]:
                # coba di komunitas yang memuat client lebih dulu
                ordered = []
                for comm in communities:
                    if clientId in comm: 
                        ordered = [comm] + [c for c in communities if c is not comm]
                        break
                if not ordered: ordered = communities

                placed_any = False
                for comm in ordered:
                    ok, placement = self._place_app_in_community(appId, clientId, comm, tmpRAM)
                    if ok:
                        self._write_alloc_and_stats(appId, placement)
                        placed_any = True
                        break
                # fallback: cloud
                if not placed_any:
                    cloud = self.ec.cloudId
                    for servId in self.ec.apps[appId].nodes:
                        ram_need = float(self.ec.appsResources[appId][servId])
                        if tmpRAM.get(cloud, 1e9) >= ram_need:
                            self.service2DevicePlacementMatrix[servId][cloud] = 1
                            self.nodeStatistics[cloud]["RAM_used"] += ram_need
                            self.nodeStatistics[cloud]["n_services"] += 1
                            self.allocations.append({
                                "app": appId,
                                "module_name": self.ec.mapServiceId2ServiceName[servId],
                                "id_resource": cloud
                            })
                            tmpRAM[cloud] = tmpRAM.get(cloud, 1e9) - ram_need

        # export
        out = {"initialAllocation": self.allocations}
        with open(self.cnf.resultFolder + "/allocDefinitionGA_FSPCN.json", "w") as f:
            f.write(json.dumps(out, indent=2))
        if self.cnf.verbose_log:
            print(f"[GA_FSPCN] Done in {time.time()-t0:.2f}s; alloc n={len(self.allocations)}")
        return self.service2DevicePlacementMatrix
