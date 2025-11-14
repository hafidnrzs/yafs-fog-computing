# GAoptimization.py
import os
import json
import time
import random
import networkx as nx


class GA:
    """
    Genetic Algorithm (GA) untuk penempatan modul layanan pada topologi YAFS-style.
    - Input  : networkDefinition.json, appDefinition.json, usersDefinition.json (di cnf.resultFolder)
    - Output : data/allocDefinitionGA.json (berisi initialAllocation dengan field 'app', 'module_name', 'id_resource')
    - Logging: menampilkan progress mirip ILP (fitness terbaik, jumlah service di cloud/fog, durasi)
    """

    def __init__(self, ec, cnf):
        self.ec = ec
        self.cnf = cnf

        # Hyperparameter GA (silakan sesuaikan kebutuhanmu)
        self.population_size = 40
        self.num_generations = 60
        self.mutation_rate = 0.10
        self.elite_size = 2
        self.tournament_k = 3
        self.random_seed = 8
        random.seed(self.random_seed)

        # Lokasi data JSON
        self.data_dir = getattr(self.cnf, "resultFolder", "data")

        # Muat JSON
        self.network = self._safe_load(os.path.join(self.data_dir, "networkDefinition.json"))
        self.app = self._safe_load(os.path.join(self.data_dir, "appDefinition.json"))
        self.users = self._safe_load(os.path.join(self.data_dir, "usersDefinition.json"))

        # Parse perangkat, graf, layanan, sumber
        self.devices = self._parse_devices(self.network)
        self.device_ids = [d["id"] for d in self.devices]
        self.device_index = {did: i for i, did in enumerate(self.device_ids)}
        self.devices_not_iot = [d for d in self.devices if str(d.get("type", "")).upper() != "IOT"]
        if not self.devices_not_iot:
            self.devices_not_iot = self.devices[:]  # fallback kalau semua IOT

        self.G = self._build_graph(self.network)

        self.services, self.service_RAM = self._parse_services(self.app)  # juga set self.service_to_app
        self.service_names = [s["name"] for s in self.services]

        self.source_nodes = self._parse_sources(self.users)
        if not self.source_nodes:
            # fallback: anggap node CLOUD/CFG sebagai sumber; jika tak ada, pakai semua
            cloud_nodes = [d["id"] for d in self.devices if str(d.get("type", "")).upper() in ("CLOUD", "CFG") ]
            self.source_nodes = cloud_nodes if cloud_nodes else self.device_ids[:]

        # Kapasitas RAM per device (0 => tidak dibatasi)
        self.device_RAM_capacity = {d["id"]: float(d.get("RAM", 0)) for d in self.devices}

    # ---------------- Utilities pemuatan & parsing ----------------

    def _safe_load(self, path):
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
        return {}

    def _parse_devices(self, net_json):
        nodes = []
        for key in ("entity", "devices", "JSONDevices"):
            if key in net_json and isinstance(net_json[key], list):
                for d in net_json[key]:
                    if "id" not in d:
                        continue
                    nodes.append({
                        "id": int(d["id"]),
                        "type": d.get("type", "FOG"),
                        "RAM": d.get("RAM", 0)
                    })
                break
        return nodes

    def _build_graph(self, net_json):
        G = nx.Graph()
        for d in self.devices:
            G.add_node(d["id"])

        links = []
        if "link" in net_json:
            links = net_json["link"]
        elif "links" in net_json:
            links = net_json["links"]

        for e in links:
            if "s" not in e or "d" not in e:
                continue
            s = int(e["s"]); d = int(e["d"])  # undirected untuk jarak
            w = float(e.get("PR", e.get("latency", 1.0)))
            G.add_edge(s, d, weight=w)
        return G

    def _parse_services(self, app_json):
        """
        Banyak pipeline menandai node layanan sebagai 'MODULE' (bukan 'SERVICE').
        Di sini kita anggap keduanya adalah service yang perlu ditempatkan.
        Selain itu, kita bangun mapping service -> app_name untuk dipakai saat menyimpan JSON.
        """
        services = []
        ram_map = {}
        svc2app = {}   # service_name -> app_name

        if isinstance(app_json, dict):
            app_list = app_json.get("apps", [app_json])
        elif isinstance(app_json, list):
            app_list = app_json
        else:
            app_list = []

        for app in app_list:
            app_name = app.get("name", "App0")
            for mod in app.get("module", []):
                t = str(mod.get("type", "")).upper()
                if t in ("SERVICE", "MODULE"):
                    name = mod.get("name")
                    if not name:
                        continue
                    services.append({"name": name})
                    ram_map[name] = float(mod.get("RAM", 0))
                    svc2app[name] = app_name

        self.service_to_app = svc2app
        return services, ram_map

    def _parse_sources(self, users_json):
        ids = []
        if not users_json:
            return ids
        for s in users_json.get("sources", []):
            if "id_resource" in s:
                ids.append(int(s["id_resource"]))
            elif "id" in s:
                ids.append(int(s["id"]))
        ids = [i for i in set(ids) if i in self.device_ids]
        return ids

    # ---------------- GA operators ----------------

    def _init_population(self):
        eligible = [d["id"] for d in self.devices_not_iot]
        nS = len(self.services)
        pop = []
        for _ in range(self.population_size):
            chrom = [random.choice(eligible) for _ in range(nS)]
            pop.append(chrom)
        return pop

    def _fitness(self, chrom):
        """
        Lebih kecil lebih baik.
        Komponen:
        - Jarak terpendek (berbobot) dari salah satu sumber ke device host service.
        - Penalti jika total RAM service pada device melebihi kapasitas.
        """
        INF = 1e6
        total = 0.0

        # precompute jarak dari tiap sumber
        sp_cache = {}
        for s in self.source_nodes:
            try:
                sp_cache[s] = nx.single_source_dijkstra_path_length(self.G, s, weight="weight")
            except Exception:
                sp_cache[s] = {}

        # komponen jaringan
        for dev in chrom:
            mind = INF
            for s in self.source_nodes:
                dist = sp_cache.get(s, {}).get(dev, INF)
                if dist < mind:
                    mind = dist
            total += mind

        # penalti RAM
        used = {}
        for i, dev in enumerate(chrom):
            sname = self.service_names[i]
            need = float(self.service_RAM.get(sname, 0))
            used[dev] = used.get(dev, 0.0) + need

        for dev, u in used.items():
            cap = float(self.device_RAM_capacity.get(dev, 0))
            if cap > 0 and u > cap:
                total += (u - cap) * 100.0
        return total

    def _tournament(self, population, k):
        contestants = random.sample(population, k)
        best = min(contestants, key=self._fitness)
        return best[:]

    def _crossover(self, p1, p2):
        if len(p1) <= 1:
            return p1[:], p2[:]
        point = random.randint(1, len(p1) - 1)
        return p1[:point] + p2[point:], p2[:point] + p1[point:]

    def _mutate(self, chrom):
        eligible = [d["id"] for d in self.devices_not_iot]
        for i in range(len(chrom)):
            if random.random() < self.mutation_rate:
                chrom[i] = random.choice(eligible)
        return chrom

    def _get_device_type(self, dev_id):
        for d in self.devices:
            if d["id"] == dev_id:
                return str(d.get("type", "")).upper()
        return ""

    # ---------------- Solver dengan log seperti ILP ----------------

    def solve(self):
        """Jalankan GA, tulis allocDefinitionGA.json, dan cetak log proses."""
        t0 = time.time()
        print("Starting GA optimization....")
        print("Pre-computing network distances...")

        if not self.devices:
            print("[GA] No devices found. Abort.")
            return []
        if not self.services:
            print("[GA] No services found in appDefinition.json. Abort.")
            return []

        nS = len(self.services)
        nD = len(self.device_ids)
        print(f"Solving GA: {nS} services, {nD} devices | population={self.population_size}, "
              f"generations={self.num_generations}, mutation={self.mutation_rate}, elite={self.elite_size}")

        pop = self._init_population()
        best_fit = float("inf")
        best_sol = None

        for gen in range(self.num_generations):
            scored = sorted(((self._fitness(c), c) for c in pop), key=lambda x: x[0])
            if scored[0][0] < best_fit:
                best_fit, best_sol = scored[0][0], scored[0][1][:]
            # progress tiap ~20% generasi
            if gen == 0 or (gen + 1) % max(1, self.num_generations // 5) == 0:
                print(f"[GA] Gen {gen+1}/{self.num_generations} | best_fitness={best_fit:.6f}")

            elites = [c for _, c in scored[: self.elite_size]]
            new_pop = elites[:]
            while len(new_pop) < self.population_size:
                p1 = self._tournament(pop, self.tournament_k)
                p2 = self._tournament(pop, self.tournament_k)
                c1, c2 = self._crossover(p1, p2)
                self._mutate(c1)
                self._mutate(c2)
                new_pop.append(c1)
                if len(new_pop) < self.population_size:
                    new_pop.append(c2)
            pop = new_pop

        if best_sol is None:
            best_sol = min(pop, key=self._fitness)
            best_fit = self._fitness(best_sol)

        # Bangun matriks penempatan & initialAllocation (dengan 'app')
        placement = [[0 for _ in range(nD)] for _ in range(nS)]
        initial_allocation = []
        for sid, dev in enumerate(best_sol):
            j = self.device_index[dev]
            placement[sid][j] = 1
            sname = self.service_names[sid]
            initial_allocation.append({
                "app": self.service_to_app.get(sname, "App0"),
                "module_name": sname,
                "id_resource": int(dev)
            })

        # Statistik cloud/fog
        cloud_types = {"CLOUD", "CFG"}  # di dataset-mu CLOUD sering dicatat 'CFG'
        fog_types = {"FOG"}
        n_cloud = sum(1 for dev in best_sol if self._get_device_type(dev) in cloud_types)
        n_fog = sum(1 for dev in best_sol if self._get_device_type(dev) in fog_types)

        # Persist
        out = {
            "initialAllocation": initial_allocation,
            "info": {
                "optimizer": "GA",
                "fitness": best_fit,
                "nServices": nS,
                "nDevices": nD
            }
        }
        os.makedirs(self.data_dir, exist_ok=True)
        out_path = os.path.join(self.data_dir, "allocDefinitionGA.json")
        with open(out_path, "w") as f:
            json.dump(out, f, indent=2)

        # Log ringkas
        print(f"Best fitness (GA): {best_fit:.6f}")
        print(f"Number of services in cloud (GA) (servicesInCloud): {n_cloud}")
        print(f"Number of services in fog (GA) (servicesInFog): {n_fog}")
        print(f"{time.time() - t0:.6f} time for GA-based optimization")
        print(f"GA allocation saved to {out_path}")

        return placement
