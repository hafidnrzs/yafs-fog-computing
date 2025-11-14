# ============================================================
# GAoptimization.py
# Genetic Algorithm for Fog Service Placement
# Style seragam + robust IO (module_name + Cloud fallback)
# ============================================================

from __future__ import annotations
import os
import json
import time
import random
from collections import defaultdict

import networkx as nx


class GAoptimization:
    """
    Genetic Algorithm (minimization) untuk penempatan service:
      - Kromosom: mapping service -> device (integer id device)
      - Fitness: weighted sum (normalized) + penalty kapasitas
           fitness = α*normLatency + β*normUtilPenalty + γ*normRisk
         di mana:
           * normLatency = rata-rata latency gw->device untuk seluruh (s, request s)
           * utilPenalty  = Σ_i max(0, (demand_i - cap_i)/cap_i)
           * risk         = rata-rata ((1-AVAIL[device]) + Σ(1-REL(edge)) path gw->device)
      - Seleksi: tournament
      - Crossover: one-point
      - Mutasi: reassign ke kandidat top-K

    Output:
      - Matriks biner [num_services x num_devices]
      - allocDefinitionGA.json (YAFS expects 'module_name')
      - Cloud fallback: satu entri per service
    """

    # -------------------------------------------------------
    # INIT
    # -------------------------------------------------------
    def __init__(self, ec, cnf):
        self.ec = ec
        self.cnf = cnf

        # himpunan dasar
        self.S = list(range(self.ec.numberOfServices))      # service ids
        self.I = list(self.ec.G.nodes())                    # device ids
        self.cloud = getattr(self.ec, "cloudId", None)

        # mapping service <-> app & nama service (dict/list OK)
        self.s2app = getattr(self.ec, "mapService2App", {})
        self.sname = getattr(self.ec, "mapServiceId2ServiceName", {})

        # resource skalar (RAM) dan kapasitas node (dict/list OK)
        self.CR = getattr(self.ec, "servicesResources", [])
        self.AR = getattr(self.ec, "nodeResources", {})

        # kecepatan, availability, reliabilitas (opsional)
        self.IPT   = getattr(self.ec, "nodeSpeed", {})
        self.AVAIL = getattr(self.ec, "nodeAvailability", {})
        self.REL   = getattr(self.ec, "edgeReliability", {})

        # beban kerja per service (instruksi); fallback ~ CR
        servicesWork = getattr(self.ec, "servicesWork", None)
        if servicesWork is not None and len(servicesWork) == len(self.S):
            self.WORK = servicesWork
        else:
            self.WORK = [max(1.0, float(self._cr_of(s))) for s in self.S]

        # deadline per app (opsional, untuk ordering request)
        self.DL = getattr(self.ec, "appsDeadlines", {})

        # daftar user-requests: (app_id:int, user_idx:int, gateway_id:int)
        self.A = self._build_requests()

        # precompute shortest path latency & paths
        self.L, self.PATH = self._precompute_latencies_and_paths()

        # Bobot fitness (override via cnf.ga_weights = {"lat":..., "util":..., "risk":...})
        self.WEIGHTS = {"lat": 0.4, "util": 0.3, "risk": 0.3}
        custom_w = getattr(self.cnf, "ga_weights", None)
        if isinstance(custom_w, dict):
            for k in ("lat", "util", "risk"):
                if k in custom_w:
                    try:
                        self.WEIGHTS[k] = float(custom_w[k])
                    except Exception:
                        pass

        # Kandidat Top-K per service (override via cnf.candidate_k)
        self.K = int(getattr(self.cnf, "candidate_k", 10))

        # Parameter GA (override via cnf)
        self.POP_SIZE    = int(getattr(self.cnf, "ga_pop_size", 40))
        self.GENERATIONS = int(getattr(self.cnf, "ga_generations", 60))
        self.TOURN_K     = int(getattr(self.cnf, "ga_tourn_k", 3))
        self.CX_RATE     = float(getattr(self.cnf, "ga_crossover_rate", 0.9))
        self.MUT_RATE    = float(getattr(self.cnf, "ga_mutation_rate", 0.2))
        self.SEED        = getattr(self.cnf, "ga_seed", None)
        if self.SEED is not None:
            random.seed(self.SEED)

        # Precompute struktur bantu
        self.services_by_app = defaultdict(list)
        for s in self.S:
            self.services_by_app[self._app_of(s)].append(s)

        self.req_by_app = defaultdict(list)
        for a in self.A:
            self.req_by_app[int(a[0])].append(a)

        # Kandidat device per service (Top-K by avg latency across app requests)
        self.CAND = self._build_candidates_topk()

        self._t0 = time.time()

    # -------------------------------------------------------
    # Helper aman dict/list
    # -------------------------------------------------------
    def _app_of(self, s: int) -> int:
        m = self.s2app
        try:
            if isinstance(m, dict):
                return int(m.get(s, 0))
            elif isinstance(m, (list, tuple)):
                return int(m[s]) if 0 <= s < len(m) else 0
        except Exception:
            pass
        return 0

    def _service_name(self, s: int) -> str:
        m = self.sname
        try:
            if isinstance(m, dict):
                return str(m.get(s, str(s)))
            elif isinstance(m, (list, tuple)):
                return str(m[s]) if 0 <= s < len(m) else str(s)
        except Exception:
            pass
        return str(s)

    def _cr_of(self, s: int) -> float:
        m = self.CR
        try:
            if isinstance(m, dict):
                return float(m.get(s, 0.0))
            elif isinstance(m, (list, tuple)):
                return float(m[s]) if 0 <= s < len(m) else 0.0
        except Exception:
            pass
        return 0.0

    def _cap_of(self, i) -> float:
        m = self.AR
        try:
            if isinstance(m, dict):
                return float(m.get(i, 0.0))
            elif isinstance(m, (list, tuple)):
                if isinstance(i, int) and 0 <= i < len(m):
                    return float(m[i])
        except Exception:
            pass
        return 0.0

    def _ipt_of(self, i) -> float:
        m = self.IPT
        try:
            if isinstance(m, dict):
                return float(m.get(i, 1.0))
            elif isinstance(m, (list, tuple)):
                if isinstance(i, int) and 0 <= i < len(m):
                    return float(m[i])
        except Exception:
            pass
        return 1.0

    def _avail_of(self, i) -> float:
        m = self.AVAIL
        try:
            if isinstance(m, dict):
                return float(m.get(i, 1.0))
            elif isinstance(m, (list, tuple)):
                if isinstance(i, int) and 0 <= i < len(m):
                    return float(m[i])
        except Exception:
            pass
        return 1.0

    # -------------------------------------------------------
    # Normalisasi app_id jika app_key objek/graph
    # -------------------------------------------------------
    def _normalize_app_id(self, app_key) -> int:
        try:
            return int(app_key)
        except Exception:
            pass
        apps = getattr(self.ec, "apps", None)
        if isinstance(apps, (list, tuple)) and apps:
            for idx, app_obj in enumerate(apps):
                if app_obj is app_key:
                    return idx
                try:
                    if app_obj == app_key:
                        return idx
                except Exception:
                    pass
                try:
                    if hasattr(app_obj, "name") and hasattr(app_key, "name"):
                        if app_obj.name == app_key.name:
                            return idx
                except Exception:
                    pass
        return 0

    # -------------------------------------------------------
    # Build requests (robust)
    # -------------------------------------------------------
    def _build_requests(self):
        A = []
        appsRequests = getattr(self.ec, "appsRequests", None)

        def _as_gateway_id(g):
            try:
                return int(g)
            except Exception:
                pass
            if isinstance(g, dict) and "id" in g:
                try:
                    return int(g["id"])
                except Exception:
                    return 0
            if isinstance(g, (list, tuple)) and len(g) > 0:
                try:
                    return int(g[0])
                except Exception:
                    return 0
            try:
                if isinstance(g, tuple) and len(g) == 2 and isinstance(g[0], (int, str)):
                    return int(g[0])
            except Exception:
                pass
            return 0

        def _append(app_key, gateways):
            app_id = self._normalize_app_id(app_key)
            for idx, g in enumerate(gateways):
                A.append((int(app_id), int(idx), int(_as_gateway_id(g))))

        if isinstance(appsRequests, dict) and appsRequests:
            for app_key, reqs in appsRequests.items():
                if isinstance(reqs, dict) and "gateways" in reqs:
                    _append(app_key, reqs["gateways"])
                else:
                    _append(app_key, reqs)
        elif isinstance(appsRequests, list) and appsRequests:
            if all(isinstance(x, dict) for x in appsRequests) and all(("gateways" in x) for x in appsRequests):
                for item in appsRequests:
                    _append(item.get("app", 0), item["gateways"])
            elif all(isinstance(x, (list, tuple)) for x in appsRequests):
                for app_idx, gateways in enumerate(appsRequests):
                    _append(app_idx, gateways)
            else:
                _append(0, appsRequests)

        if not A:
            gateways = [n for n, data in self.ec.G.nodes(data=True)
                        if str(data.get("type", "")).lower() in ("fg", "fog", "gateway")]
            if not gateways:
                gateways = list(self.ec.G.nodes())
            apps = getattr(self.ec, "apps", [])
            if apps:
                for app_idx, _app in enumerate(apps):
                    _append(app_idx, gateways)
            else:
                _append(0, gateways)

        # de-dup (app,gw): ambil satu user_idx
        dedup = {}
        for (app_id, user_idx, gw) in A:
            dedup[(int(app_id), int(gw))] = (int(app_id), 0, int(gw))
        A = list(dedup.values())

        if getattr(self.cnf, "verbose_log", False):
            print(f"[GA] appsRequests parsed → {len(A)} requests; sample={A[:min(5,len(A))]}")
        return A

    # -------------------------------------------------------
    # Precompute latency & paths
    # -------------------------------------------------------
    def _precompute_latencies_and_paths(self):
        L, PATH = {}, {}
        BIG = 10**6
        gateways = sorted({gw for (_, _, gw) in self.A})
        for g in gateways:
            try:
                lengths, paths = nx.single_source_dijkstra(self.ec.G, g, weight="weight")
            except Exception:
                lengths, paths = ({}, {})
            for i in self.I:
                if i in lengths:
                    L[(g, i)] = float(lengths[i])
                    p = paths[i]
                    PATH[(g, i)] = list(zip(p[:-1], p[1:]))
                else:
                    L[(g, i)] = float(BIG)
                    PATH[(g, i)] = []
        return L, PATH

    # -------------------------------------------------------
    # Build Top-K candidates per service (by avg latency across its app requests)
    # -------------------------------------------------------
    def _build_candidates_topk(self):
        K = max(1, int(self.K))
        CAND = {}
        for s in self.S:
            app_id = self._app_of(s)
            reqs = self.req_by_app.get(app_id, [])
            # jika tidak ada request, gunakan semua node
            if not reqs:
                sorted_nodes = sorted(self.I)[:K]
                if self.cloud is not None and self.cloud not in sorted_nodes:
                    sorted_nodes.append(self.cloud)
                CAND[s] = list(dict.fromkeys(sorted_nodes))
                continue

            # rata-rata latency ke setiap device
            avg_lat = []
            for i in self.I:
                lats = [self.L.get((gw, i), 1e9) for (_, _, gw) in reqs]
                if lats:
                    avg_lat.append((i, sum(lats)/len(lats)))
            avg_lat.sort(key=lambda t: t[1])
            topk = [i for (i, _) in avg_lat[:K]]
            if self.cloud is not None and self.cloud not in topk:
                topk.append(self.cloud)
            CAND[s] = topk
        return CAND

    # -------------------------------------------------------
    # GA primitives
    # -------------------------------------------------------
    def _random_individual(self):
        """
        Individu = list device_id per service s.
        Pilih dari kandidat Top-K; jika tak ada, pilih cloud atau random node.
        """
        chrom = []
        for s in self.S:
            cand = self.CAND.get(s, [])
            if not cand:
                if self.cloud is not None:
                    chrom.append(self.cloud)
                else:
                    chrom.append(random.choice(self.I))
            else:
                chrom.append(random.choice(cand))
        return chrom

    def _tournament_select(self, population, fitnesses):
        k = max(2, int(self.TOURN_K))
        best = None
        for _ in range(k):
            idx = random.randrange(len(population))
            fit = fitnesses[idx]
            if (best is None) or (fit < best[0]):
                best = (fit, population[idx])
        return list(best[1])

    def _crossover(self, p1, p2):
        if random.random() > self.CX_RATE or len(p1) < 2:
            return list(p1), list(p2)
        cut = random.randint(1, len(p1) - 1)
        c1 = p1[:cut] + p2[cut:]
        c2 = p2[:cut] + p1[cut:]
        return c1, c2

    def _mutate(self, ind):
        mutated = False
        for s in range(len(ind)):
            if random.random() < self.MUT_RATE:
                cand = self.CAND.get(s, [])
                if cand:
                    ind[s] = random.choice(cand)
                    mutated = True
                elif self.cloud is not None:
                    ind[s] = self.cloud
                    mutated = True
                else:
                    ind[s] = random.choice(self.I)
                    mutated = True
        return mutated

    # -------------------------------------------------------
    # Fitness & repair
    # -------------------------------------------------------
    def _fitness(self, chrom):
        """
        Hitung fitness individu (lebih kecil lebih baik).
        Komponen:
          - avg latency per service (di-aggregate di seluruh request app)
          - risk (device + link) avg
          - utilization overflow penalty (global)
        Semua komponen dinormalisasi min-max di level individu (aman untuk perbandingan).
        """
        eps = 1e-12
        # compute per-device demand
        demand_by_dev = defaultdict(float)
        for s, dev in enumerate(chrom):
            demand_by_dev[dev] += self._cr_of(s)

        # utilization overflow penalty
        over_list = []
        for i in self.I:
            cap = self._cap_of(i)
            if cap <= 0:
                continue
            overflow = max(0.0, (demand_by_dev.get(i, 0.0) - cap) / cap)
            over_list.append(overflow)
        util_penalty = sum(over_list)  # skalar

        # latency & risk per service (aggregate over its app requests)
        lat_vals = []
        risk_vals = []
        for s, dev in enumerate(chrom):
            app_id = self._app_of(s)
            reqs = self.req_by_app.get(app_id, [])
            if not reqs:
                continue
            lats = []
            risks = []
            for (_, _, gw) in reqs:
                lat = float(self.L.get((gw, dev), 1e9))
                # risk
                dev_risk = 1.0 - self._avail_of(dev)
                link_risk = 0.0
                if self.REL:
                    for (u, v) in self.PATH.get((gw, dev), []):
                        rel = self.REL.get((u, v), self.REL.get((v, u), 1.0))
                        link_risk += (1.0 - float(rel))
                risks.append(dev_risk + link_risk)
                lats.append(lat)
            lat_vals.append(sum(lats) / len(lats))
            risk_vals.append(sum(risks) / len(risks))

        # jika tak ada lat/risk (kasus ekstrem), set nol
        avg_lat = (sum(lat_vals) / len(lat_vals)) if lat_vals else 0.0
        avg_risk = (sum(risk_vals) / len(risk_vals)) if risk_vals else 0.0

        # normalisasi sederhana (per individu)
        # Note: normalization per individu menjaga skala konsisten antar komponen
        # tanpa memerlukan data populasi global.
        # Untuk lat/risk: gunakan min=max=avg → hasil 0; kita pakai skala linear ke [0,1] via faktor heuristik.
        # Agar stabil, gunakan faktor pembagi tetap (mis. 1e3) bila tak ada variasi.
        lat_norm = avg_lat / (1000.0 + eps)  # asumsikan ms; sesuaikan jika perlu
        risk_norm = avg_risk / (1.0 + eps)   # risk biasanya ~O(1)
        util_norm = util_penalty / (len(self.I) + eps)

        fitness = (
            self.WEIGHTS["lat"]  * lat_norm +
            self.WEIGHTS["risk"] * risk_norm +
            self.WEIGHTS["util"] * util_norm
        )
        return fitness

    def _repair_capacity(self, chrom):
        """
        Perbaiki individu agar tidak overload:
          - untuk setiap device yang overload, pindahkan service CR terbesar
            ke device feasible terbaik (min latency) atau Cloud.
        """
        changed = False
        # compute per-device service lists
        services_on = defaultdict(list)
        for s, dev in enumerate(chrom):
            services_on[dev].append(s)

        # iterate overload devices
        for i in self.I:
            cap = self._cap_of(i)
            if cap <= 0:
                continue
            demand = sum(self._cr_of(s) for s in services_on.get(i, []))
            while demand > cap + 1e-9:
                # pilih service dengan CR terbesar untuk dipindahkan
                s_move = max(services_on[i], key=lambda s: self._cr_of(s))
                services_on[i].remove(s_move)
                demand -= self._cr_of(s_move)

                # cari device alternatif terbaik
                app_id = self._app_of(s_move)
                reqs = self.req_by_app.get(app_id, [])
                cand = self.CAND.get(s_move, []) + ([self.cloud] if (self.cloud is not None) else [])
                best = None
                for j in cand:
                    if j == i:
                        continue
                    cap_j = self._cap_of(j)
                    # cek demand pada j jika s_move dipindah
                    dem_j = sum(self._cr_of(s) for s in services_on.get(j, []))
                    if j != self.cloud and dem_j + self._cr_of(s_move) > cap_j + 1e-9:
                        continue
                    # skor: rata-rata latency dari semua req app_id
                    lat_sum = 0.0
                    cnt = 0
                    for (_, _, gw) in reqs:
                        lat_sum += float(self.L.get((gw, j), 1e9))
                        cnt += 1
                    avg_lat = (lat_sum / cnt) if cnt else 0.0
                    if (best is None) or (avg_lat < best[0]):
                        best = (avg_lat, j)
                if best is None:
                    # tak ada alternatif feasible: paksa cloud jika ada
                    if self.cloud is not None:
                        j = self.cloud
                    else:
                        # jika tidak ada cloud, pilih device dengan tambahan demand terkecil
                        opts = []
                        for j in self.I:
                            dem_j = sum(self._cr_of(s) for s in services_on.get(j, []))
                            opts.append((dem_j, j))
                        j = min(opts)[1]
                # pindahkan
                chrom[s_move] = best[1] if isinstance(best, tuple) else j
                services_on[chrom[s_move]].append(s_move)
                changed = True
        return changed

    # -------------------------------------------------------
    # SOLVE (GA loop)
    # -------------------------------------------------------
    def solve(self):
        verbose = bool(getattr(self.cnf, "verbose_log", False))
        if verbose:
            print(f"[GA] pop={self.POP_SIZE}, gen={self.GENERATIONS}, "
                  f"cx={self.CX_RATE}, mut={self.MUT_RATE}, K={self.K}, weights={self.WEIGHTS}")

        # Inisialisasi populasi
        population = [self._random_individual() for _ in range(self.POP_SIZE)]
        # Repair awal (opsional)
        for ind in population:
            self._repair_capacity(ind)

        # Evaluasi awal
        fitnesses = [self._fitness(ind) for ind in population]
        best_ind = list(population[min(range(len(population)), key=lambda i: fitnesses[i])])
        best_fit = min(fitnesses)

        # Evolusi
        for gen in range(self.GENERATIONS):
            new_pop = []

            # Elitism: keep best
            new_pop.append(list(best_ind))

            # offspring
            while len(new_pop) < self.POP_SIZE:
                p1 = self._tournament_select(population, fitnesses)
                p2 = self._tournament_select(population, fitnesses)
                c1, c2 = self._crossover(p1, p2)
                self._mutate(c1)
                self._mutate(c2)
                # repair kapasitas
                self._repair_capacity(c1)
                self._repair_capacity(c2)
                new_pop.extend([c1, c2])

            population = new_pop[:self.POP_SIZE]
            fitnesses = [self._fitness(ind) for ind in population]

            # update best
            idx = min(range(len(population)), key=lambda i: fitnesses[i])
            if fitnesses[idx] < best_fit:
                best_fit = fitnesses[idx]
                best_ind = list(population[idx])

            if verbose and (gen % max(1, self.GENERATIONS // 10) == 0 or gen == self.GENERATIONS - 1):
                print(f"[GA] gen {gen+1}/{self.GENERATIONS} | best_fit={best_fit:.6f}")

        # Bangun matriks S2D dari best_ind
        n_serv = len(self.S)
        n_dev = len(self.I)
        S2D = [[0 for _ in range(n_dev)] for _ in range(n_serv)]
        node2col = {i: idx for idx, i in enumerate(self.I)}
        for s, dev in enumerate(best_ind):
            j = node2col.get(dev)
            if j is not None:
                S2D[s][j] = 1

        # Statistik
        nodeResUse, nodeNumServ = self.calculateNodeUsage(S2D)
        if verbose:
            fog_count = 0
            if self.cloud in self.I:
                cloud_idx = self.I.index(self.cloud)
                fog_count = sum(sum(row) for row in S2D) - sum(S2D[s][cloud_idx] for s in self.S)
            else:
                fog_count = sum(sum(row) for row in S2D)
            cloud_services = len(self.S)
            print(f"[GA] Number of services in fog (GA): {fog_count}")
            print(f"[GA] Number of services in cloud (GA): {cloud_services}")
            print(f"[GA] Finished GA in {time.time()-self._t0:.3f}s | best_fit={best_fit:.6f}")

        # Tulis JSON
        alloc = self._buildAllocationList(S2D)
        out_json = self._writeAllocationJson(alloc)
        if verbose:
            print(f"[GA] allocation json: {out_json}")

        return S2D

    # -------------------------------------------------------
    # Statistik & Output helpers
    # -------------------------------------------------------
    def calculateNodeUsage(self, S2D):
        nodeResUse = {i: 0.0 for i in self.I}
        nodeNumServ = {i: 0 for i in self.I}
        for s, row in enumerate(S2D):
            for j, bit in enumerate(row):
                if bit:
                    dev = self.I[j]
                    nodeNumServ[dev] += 1
                    nodeResUse[dev] += float(self._cr_of(s))
        for i in self.I:
            cap = self._cap_of(i) or 1.0
            nodeResUse[i] = min(1.0, nodeResUse[i] / cap)
        return nodeResUse, nodeNumServ

    def _buildAllocationList(self, S2D):
        alloc = []
        for s, row in enumerate(S2D):
            app_id = self._app_of(s)
            module_name = self._service_name(s)
            for j, bit in enumerate(row):
                if not bit:
                    continue
                dev = int(self.I[j])
                if self.cloud is not None and dev == self.cloud:
                    continue
                alloc.append({
                    "app": str(app_id),
                    "module_name": module_name,
                    "id_resource": dev
                })
            if self.cloud is not None:
                alloc.append({
                    "app": str(app_id),
                    "module_name": module_name,
                    "id_resource": int(self.cloud)
                })
        return alloc

    def _writeAllocationJson(self, alloc):
        outdir = getattr(self.cnf, "resultFolder", "./results")
        os.makedirs(outdir, exist_ok=True)
        path = os.path.join(outdir, "allocDefinitionGA.json")
        with open(path, "w") as f:
            json.dump({"initialAllocation": alloc}, f)
        return path
