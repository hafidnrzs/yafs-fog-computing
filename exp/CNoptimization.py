# ============================================================
# CNoptimization.py
# Community-based, Availability-aware Greedy Placement
# (style seragam + robust IO, tanpa mengubah file lain)
# ============================================================

from __future__ import annotations
import os
import json
import time
from collections import defaultdict

import networkx as nx


class CNoptimization:
    """
    Heuristik dua tahap:
      1) Map App -> Komunitas (yang berisi gateway peminta), urut komunitas/level.
      2) Place Services -> Perangkat di komunitas dengan Greedy First-Fit
         (urut device berdasarkan fitness = latency(gw,i) + exec_time(i)),
         mencoba menempatkan kelompok layanan (closure) pada device yang sama.
    Output:
      - Matriks biner [num_services x num_devices]
      - allocDefinitionCN.json (format identik ILP)
      - Fallback: satu entri Cloud per service
    """

    # -------------------------------------------------------
    # INIT
    # -------------------------------------------------------
    def __init__(self, ec, cnf):
        self.ec = ec
        self.cnf = cnf

        # himpunan dasar
        self.S = list(range(self.ec.numberOfServices))      # service ids
        self.I = list(self.ec.G.nodes())                    # device ids (fog + cloud)
        self.cloud = getattr(self.ec, "cloudId", None)

        # mapping service <-> app & nama service (boleh dict/list)
        self.s2app = getattr(self.ec, "mapService2App", {})
        self.sname = getattr(self.ec, "mapServiceId2ServiceName", {})

        # resource skalar (RAM) & kapasitas node (boleh dict/list)
        self.CR = getattr(self.ec, "servicesResources", [])
        self.AR = getattr(self.ec, "nodeResources", {})

        # kecepatan device (MIPS/IPT) untuk estimasi exec time
        self.IPT = getattr(self.ec, "nodeSpeed", {})

        # beban kerja per service (instruksi); fallback ke CR
        servicesWork = getattr(self.ec, "servicesWork", None)
        if servicesWork is not None and len(servicesWork) == len(self.S):
            self.WORK = servicesWork
        else:
            self.WORK = [max(1.0, float(self._cr_of(s))) for s in self.S]

        # daftar request: (app_id:int, user_idx:int, gateway_id:int)
        self.A = self._build_requests()

        # precompute shortest path latency gateway -> device
        self.L = self._precompute_latencies()

        # komunitas (list of sets of node ids), berlevel jika memungkinkan
        self.communities_levels = self._compute_communities()

        self._t0 = time.time()

    # -------------------------------------------------------
    # Helper umum: akses aman dict/list
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

    # -------------------------------------------------------
    # Normalisasi app_id jika app_key adalah object/graph
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
    # Build requests dari ec.appsRequests (robust)
    # -------------------------------------------------------
    def _build_requests(self):
        """
        Return list (app_id:int, user_idx:int, gateway_id:int) dari ec.appsRequests.
        Mendukung:
        - dict: {app_key: [gw...]} atau {app_key: {"gateways":[...]}}
        - list of dict: [{"app": app_key, "gateways":[...]}]
        - list of list/tuple: [[gw...], [gw...], ...] (index list = app_id)
        - list sederhana: [gw1, gw2, ...] (diasumsikan app_id = 0)
        Fallback: 1 request per app di semua gateway bertipe FG/FOG/Gateway (atau semua node).
        """
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

        if getattr(self.cnf, "verbose_log", False):
            print(f"[CN] appsRequests parsed → {len(A)} requests; sample={A[:min(5,len(A))]}")
        return A

    # -------------------------------------------------------
    # Precompute latency gateway->device
    # -------------------------------------------------------
    def _precompute_latencies(self):
        L = {}
        BIG = 10**6
        gateways = sorted({gw for (_, _, gw) in self.A})
        for g in gateways:
            try:
                lengths = nx.single_source_dijkstra_path_length(self.ec.G, g, weight="weight")
            except Exception:
                lengths = {}
            for i in self.I:
                L[(g, i)] = float(lengths.get(i, BIG))
        return L

    # -------------------------------------------------------
    # Community detection & ordering
    # -------------------------------------------------------
    def _compute_communities(self):
        """
        Kembalikan list level komunitas: [ [set(nodes), ...], level2, ... ]
        - Coba greedy_modularity_communities terlebih dahulu (satu level).
        - Jika gagal, jatuhkan ke girvan_newman beberapa level pertama.
        """
        G = self.ec.G
        levels = []

        try:
            from networkx.algorithms.community import greedy_modularity_communities
            comms = list(greedy_modularity_communities(G, weight="weight"))
            if comms:
                levels.append([set(c) for c in comms])
        except Exception:
            pass

        if not levels:
            try:
                from networkx.algorithms.community import girvan_newman
                gen = girvan_newman(G)
                # ambil 3 level pertama (bila ada)
                for _ in range(3):
                    parts = next(gen, None)
                    if not parts:
                        break
                    levels.append([set(p) for p in parts])
            except Exception:
                pass

        # fallback: satu komunitas berisi semua node
        if not levels:
            levels = [[set(self.I)]]

        if getattr(self.cnf, "verbose_log", False):
            sizes = [[len(c) for c in lvl] for lvl in levels]
            print(f"[CN] communities levels: {sizes}")
        return levels

    # -------------------------------------------------------
    # Device scoring (fitness) w.r.t. a gateway
    # -------------------------------------------------------
    def _device_fitness(self, gw, dev, services_subset):
        """
        Fitness lebih kecil lebih baik.
        = latency(gw->dev) + sum( WORK[s]/IPT[dev] ) untuk semua s dalam subset
        """
        lat = self.L.get((gw, dev), 1e6)
        ipt = max(1.0, self._ipt_of(dev))
        exec_time = sum(float(self.WORK[s]) / ipt for s in services_subset) if services_subset else 0.0
        return lat + exec_time

    # -------------------------------------------------------
    # Transitive closures (fallback aman jika info DAG tidak ada)
    # -------------------------------------------------------
    def _closures_for_app(self, services_of_app):
        """
        Kembalikan list closures (set of service ids), urut dari besar -> kecil.
        Jika tidak ada info DAG aplikasi, gunakan:
          [ set(all_services),  {s1}, {s2}, ... ]
        Tujuannya mendorong ko-lokasi sebanyak mungkin, lalu fallback ke singletons.
        """
        allset = set(services_of_app)
        closures = [allset] + [{s} for s in services_of_app]
        return closures

    # -------------------------------------------------------
    # Greedy placement di satu komunitas untuk satu app request
    # -------------------------------------------------------
    def _place_app_in_community(self, app_services, community_nodes, gw, S2D, remCap):
        """
        Coba tempatkan services app ke perangkat di community_nodes (set of node ids).
        - Urut devices berdasarkan fitness terhadap gateway gw (subset besar dulu).
        - Coba tempatkan closures dari besar ke kecil pada device terbaik.
        - Update S2D dan remCap jika berhasil.
        Return: jumlah services baru yang berhasil ditempatkan.
        """
        placed_now = 0
        # services yang belum ditempatkan sama sekali (di mana pun)
        remaining = [s for s in app_services if not any(S2D[s][idx] for idx, i in enumerate(self.I))]
        if not remaining:
            return 0

        closures = self._closures_for_app(remaining)

        # urut device dalam komunitas menurut fitness untuk closure terbesar
        largest = list(closures[0])
        devs = [i for i in community_nodes if i in self.I]
        devs_sorted = sorted(
            devs, key=lambda i: self._device_fitness(gw, i, largest)
        )

        # indeks node -> index kolom pada S2D
        node2col = {i: idx for idx, i in enumerate(self.I)}

        for dev in devs_sorted:
            if dev not in node2col:
                continue
            did_place_any = False
            for closure in closures:
                # filter hanya services yang masih belum ditempatkan
                needs = [s for s in closure if not any(S2D[s][k] for k in range(len(self.I)))]
                if not needs:
                    continue
                total_demand = sum(self._cr_of(s) for s in needs)
                if remCap.get(dev, 0.0) >= total_demand:
                    # tempatkan semua services 'needs' di device ini
                    col = node2col[dev]
                    for s in needs:
                        S2D[s][col] = 1
                        remCap[dev] -= self._cr_of(s)
                        placed_now += 1
                        did_place_any = True
                # kalau closure besar tidak muat, biarkan closure lebih kecil mencoba
            # jika di device ini tidak menempatkan apa pun, lanjut ke device berikutnya
            # bila sudah menempatkan sebagian, tetap lanjut agar menutup sisa services
        return placed_now

    # -------------------------------------------------------
    # Statistik
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

    # -------------------------------------------------------
    # Output helpers
    # -------------------------------------------------------
    def _buildAllocationList(self, S2D):
        """
        Bangun list initialAllocation dengan key yang sesuai YAFS:
        - "app"          : id/nama aplikasi (string)
        - "module_name"  : NAMA SERVICE/MODUL (harus cocok dengan appDefinition.json)
        - "id_resource"  : id device tempat modul ditempatkan
        Plus: satu entri fallback Cloud per service (sesuai pola kamu).
        """
        alloc = []
        for s, row in enumerate(S2D):
            app_id = self._app_of(s)
            module_name = self._service_name(s)   # pastikan nama modul persis seperti di appDefinition

            # placements di fog (semua bit 1 kecuali cloud)
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

            # fallback Cloud: satu entri per service
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
        path = os.path.join(outdir, "allocDefinitionCN.json")
        with open(path, "w") as f:
            json.dump({"initialAllocation": alloc}, f)
        return path

    # -------------------------------------------------------
    # SOLVE
    # -------------------------------------------------------
    def solve(self):
        verbose = bool(getattr(self.cnf, "verbose_log", False))
        if verbose:
            print("[CN] Start solve...")

        n_serv = len(self.S)
        n_dev = len(self.I)
        S2D = [[0 for _ in range(n_dev)] for _ in range(n_serv)]

        # kapasitas sisa per device (akan berkurang saat menempatkan)
        remCap = {i: self._cap_of(i) for i in self.I}

        # layanan per app
        services_by_app = defaultdict(list)
        for s in self.S:
            services_by_app[self._app_of(s)].append(s)

        # urut aplikasi menurut deadline (jika ada), atau by app_id
        apps_deadlines = getattr(self.ec, "appsDeadlines", {})
        def _dl_of(app_id):  # kecil = prioritas tinggi
            try:
                return float(apps_deadlines.get(app_id, 1e9))
            except Exception:
                return 1e9
        apps_sorted = sorted(services_by_app.keys(), key=lambda a: _dl_of(a))

        # iterasi tiap request (app, gateway) mengikuti urutan app
        # mapping: app -> semua requestnya (a = (app_id,user_idx,gw))
        req_by_app = defaultdict(list)
        for a in self.A:
            req_by_app[int(a[0])].append(a)

        # flatten communities per level → urut level terdalam lebih dulu (heuristik “kompak/dalam”)
        # jika ada banyak level: proses dari level terakhir ke pertama
        levels = list(self.communities_levels)
        levels_ordered = []
        if levels:
            for lvl in reversed(levels):
                # sort komunitas di level ini by ukuran ascending (lebih kecil lebih “dalam”)
                levels_ordered.append(sorted([set(c) for c in lvl], key=lambda s: len(s)))
        else:
            levels_ordered = [[set(self.I)]]

        # indeks node -> kolom S2D
        node2col = {i: idx for idx, i in enumerate(self.I)}

        for app_id in apps_sorted:
            app_services = services_by_app[app_id]
            # untuk tiap request (user,gw) dari app ini
            for (_, _, gw) in req_by_app.get(app_id, []):
                # 1) coba di komunitas yang memuat gateway, dari level terdalam -> ke atas
                placed_this_app = 0
                for lvl in levels_ordered:
                    # urutkan: komunitas yang memuat gw → prioritas
                    candidate_comms = []
                    holder_comms = []
                    for comm in lvl:
                        if gw in comm:
                            candidate_comms.append(comm)
                        else:
                            holder_comms.append(comm)
                    # proses komunitas yang berisi gw dulu, lalu sisanya (tetap di level ini)
                    for comm in candidate_comms + holder_comms:
                        placed_now = self._place_app_in_community(
                            app_services, comm, gw, S2D, remCap
                        )
                        placed_this_app += placed_now
                        # bila sudah semua services app terpasang, hentikan komunitas level ini
                        if all(any(S2D[s][k] for k in range(n_dev)) for s in app_services):
                            break
                    # check setelah satu level
                    if all(any(S2D[s][k] for k in range(n_dev)) for s in app_services):
                        break

                # 2) jika masih ada services app yang belum terpasang → fallback Cloud
                if self.cloud is not None and not all(any(S2D[s][k] for k in range(n_dev)) for s in app_services):
                    cloud_idx = node2col.get(self.cloud, None)
                    if cloud_idx is not None:
                        for s in app_services:
                            if not any(S2D[s][k] for k in range(n_dev)):
                                S2D[s][cloud_idx] = 1  # cloud dianggap selalu cukup (sesuai pola)
                    # tidak mengurangi remCap untuk cloud (tak dibatasi)

        # statistik
        nodeResUse, nodeNumServ = self.calculateNodeUsage(S2D)
        if verbose:
            fog_count = 0
            if self.cloud in self.I:
                cloud_idx = self.I.index(self.cloud)
                fog_count = sum(sum(row) for row in S2D) - sum(S2D[s][cloud_idx] for s in self.S)
            else:
                fog_count = sum(sum(row) for row in S2D)
            cloud_services = len(self.S)  # fallback cloud per service (satu entri)
            print(f"[CN] Number of services in fog (partition): {fog_count}")
            print(f"[CN] Number of services in cloud (partition): {cloud_services}")
            print(f"[CN] Finished CN in {time.time()-self._t0:.3f}s")

        # tulis JSON
        alloc = self._buildAllocationList(S2D)
        out_json = self._writeAllocationJson(alloc)
        if verbose:
            print(f"[CN] allocation json: {out_json}")

        return S2D
