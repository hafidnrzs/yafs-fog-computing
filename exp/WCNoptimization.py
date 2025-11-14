# ============================================================
# WCNoptimization.py
# Weighted Greedy Heuristic (WGH) for Fog Service Placement
# Style seragam + robust IO (module_name + fallback Cloud)
# ============================================================

from __future__ import annotations
import os
import json
import time
from collections import defaultdict

import networkx as nx


class WCNoptimization:
    """
    Weighted Greedy Heuristic (multi-parameter):
      SCORE(s,i,gw) = α * normLAT + β * normLOAD + γ * normRISK
      - LAT  : shortest-path latency gw -> device i
      - LOAD : CR[s] / remCap[i]   (semakin kecil semakin baik)
      - RISK : (1-availability[i]) + sum(1-rel) sepanjang path(gw,i)

    Penempatan per app & request:
      - urut service (opsional: by demand menurun)
      - pilih device dengan SCORE minimum di antara kandidat
      - perbarui remCap; fallback Cloud jika perlu

    Output:
      - Matriks biner [num_services x num_devices]
      - allocDefinitionWCN.json (YAFS expects 'module_name')
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

        # mapping service <-> app & nama service (bisa dict/list)
        self.s2app = getattr(self.ec, "mapService2App", {})
        self.sname = getattr(self.ec, "mapServiceId2ServiceName", {})

        # resource skalar (RAM) dan kapasitas node (bisa dict/list)
        self.CR = getattr(self.ec, "servicesResources", [])
        self.AR = getattr(self.ec, "nodeResources", {})

        # kecepatan device (MIPS/IPT), availability, reliabilitas edge
        self.IPT   = getattr(self.ec, "nodeSpeed", {})
        self.AVAIL = getattr(self.ec, "nodeAvailability", {})   # 0..1
        self.REL   = getattr(self.ec, "edgeReliability", {})    # {(u,v): 0..1}

        # beban kerja per service (instruksi); fallback ~ CR
        servicesWork = getattr(self.ec, "servicesWork", None)
        if servicesWork is not None and len(servicesWork) == len(self.S):
            self.WORK = servicesWork
        else:
            self.WORK = [max(1.0, float(self._cr_of(s))) for s in self.S]

        # deadline per app (opsional) – dipakai hanya untuk ordering
        self.DL = getattr(self.ec, "appsDeadlines", {})

        # daftar user-requests: (app_id:int, user_idx:int, gateway_id:int)
        self.A = self._build_requests()

        # precompute shortest path latency & paths
        self.L, self.PATH = self._precompute_latencies_and_paths()

        # bobot skor (bisa override via cnf.wgh_weights)
        w_default = {"lat": 0.4, "res": 0.3, "risk": 0.3}
        self.WEIGHTS = dict(w_default)
        custom = getattr(self.cnf, "wgh_weights", None)
        if isinstance(custom, dict):
            for k in ("lat", "res", "risk"):
                if k in custom:
                    try:
                        self.WEIGHTS[k] = float(custom[k])
                    except Exception:
                        pass

        # top-K kandidat device per (s,gw)
        self.K = int(getattr(self.cnf, "candidate_k", 5))
        # jika ingin membatasi ke komunitas, aktifkan flag ini dan sediakan self.communities_levels
        self.use_communities = bool(getattr(self.cnf, "wgh_use_communities", True))
        if self.use_communities:
            self.communities_levels = self._compute_communities()
        else:
            self.communities_levels = None

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
    # Build requests dari ec.appsRequests (robust)
    # -------------------------------------------------------
    def _build_requests(self):
        """
        Return list (app_id:int, user_idx:int, gateway_id:int).
        Mendukung:
          - dict: {app_key: [gw...]} atau {app_key: {"gateways":[...]}}
          - list of dict: [{"app": app_key, "gateways":[...]}]
          - list of list/tuple: [[gw...], [gw...], ...]  (index list = app_id)
          - list sederhana: [gw1, gw2, ...] (diasumsikan app_id = 0)
        Fallback: 1 request per app di semua gateway FG/FOG/Gateway (atau semua node).
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

        # de-dup (app, gw) → ambil satu user_idx
        dedup = {}
        for (app_id, user_idx, gw) in A:
            dedup[(int(app_id), int(gw))] = (int(app_id), 0, int(gw))
        A = list(dedup.values())

        if getattr(self.cnf, "verbose_log", False):
            print(f"[WCN] appsRequests parsed → {len(A)} requests; sample={A[:min(5,len(A))]}")
        return A

    # -------------------------------------------------------
    # Precompute latency & path
    # -------------------------------------------------------
    def _precompute_latencies_and_paths(self):
        L = {}
        PATH = {}
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
    # Communities (opsional)
    # -------------------------------------------------------
    def _compute_communities(self):
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
                for _ in range(3):
                    parts = next(gen, None)
                    if not parts:
                        break
                    levels.append([set(p) for p in parts])
            except Exception:
                pass
        if not levels:
            levels = [[set(self.I)]]
        if getattr(self.cnf, "verbose_log", False):
            sizes = [[len(c) for c in lvl] for lvl in levels]
            print(f"[WCN] communities levels: {sizes}")
        return levels

    # -------------------------------------------------------
    # Candidates per (s, gw)
    # -------------------------------------------------------
    def _candidates(self, s, gw):
        """
        Kembalikan set kandidat device untuk (service s, gateway gw).
        - remCap filter dilakukan saat scoring (cek ulang),
        - top-K by latency diterapkan di akhir.
        - jika use_communities: prioritaskan komunitas yang memuat gw pada level terdalam.
        """
        cand = set(self.I)
        if self.use_communities and self.communities_levels:
            # ambil level terdalam yang memuat gw
            for lvl in reversed(self.communities_levels):
                found = [c for c in lvl if gw in c]
                if found:
                    cand = set(found[0])  # komunitas yang memuat gw
                    break
        # sort by latency dan ambil top-K
        sorted_nodes = sorted(cand, key=lambda i: self.L.get((gw, i), 1e9))
        if self.K > 0:
            sorted_nodes = sorted_nodes[:self.K] + ([self.cloud] if (self.cloud is not None and self.cloud not in sorted_nodes) else [])
        return set(sorted_nodes)

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
            cap = self._cap_of(i)
            cap = cap if cap > 0.0 else 1.0
            nodeResUse[i] = min(1.0, nodeResUse[i] / cap)
        return nodeResUse, nodeNumServ

    # -------------------------------------------------------
    # Output helpers
    # -------------------------------------------------------
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
        path = os.path.join(outdir, "allocDefinitionWCN.json")
        with open(path, "w") as f:
            json.dump({"initialAllocation": alloc}, f)
        return path

    # -------------------------------------------------------
    # SOLVE
    # -------------------------------------------------------
    def solve(self):
        verbose = bool(getattr(self.cnf, "verbose_log", False))
        if verbose:
            print(f"[WCN] Weights = {self.WEIGHTS} | K = {self.K} | use_communities={self.use_communities}")

        n_serv = len(self.S)
        n_dev = len(self.I)
        S2D = [[0 for _ in range(n_dev)] for _ in range(n_serv)]
        remCap = {i: self._cap_of(i) for i in self.I}

        # layanan per app
        services_by_app = defaultdict(list)
        for s in self.S:
            services_by_app[self._app_of(s)].append(s)

        # urut aplikasi menurut deadline (jika ada), else by app_id
        apps_deadlines = getattr(self.ec, "appsDeadlines", {})
        def _dl_of(app_id):
            try:
                return float(apps_deadlines.get(app_id, 1e9))
            except Exception:
                return 1e9
        apps_sorted = sorted(services_by_app.keys(), key=lambda a: _dl_of(a))

        # requests per app
        req_by_app = defaultdict(list)
        for a in self.A:
            req_by_app[int(a[0])].append(a)

        node2col = {i: idx for idx, i in enumerate(self.I)}
        eps = 1e-12

        for app_id in apps_sorted:
            app_services = services_by_app[app_id]
            # urutkan service by demand besar dulu (packing lebih stabil)
            app_services = sorted(app_services, key=lambda s: self._cr_of(s), reverse=True)

            for (_, _, gw) in req_by_app.get(app_id, []):
                for s in app_services:
                    # skip jika s sudah ditempatkan (oleh request sebelumnya)
                    if any(S2D[s][k] for k in range(n_dev)):
                        continue

                    cr_s = self._cr_of(s)
                    # KANDIDAT
                    C = [i for i in self._candidates(s, gw)]
                    if not C and self.cloud is not None:
                        C = [self.cloud]

                    # KOMPONEN untuk kandidat feasible
                    comps = []
                    for i in C:
                        cap_i = remCap.get(i, 0.0)
                        # cloud dianggap selalu bisa (tidak kurangi remCap)
                        feasible = (i == self.cloud) or (cap_i >= cr_s and cr_s > 0.0)
                        if not feasible:
                            continue
                        lat = float(self.L.get((gw, i), 1e9))
                        load = cr_s / max(eps, cap_i) if i != self.cloud else 0.0
                        dev_risk = 1.0 - self._avail_of(i)
                        link_risk = 0.0
                        if self.REL:
                            for (u, v) in self.PATH.get((gw, i), []):
                                rel = self.REL.get((u, v), self.REL.get((v, u), 1.0))
                                link_risk += (1.0 - float(rel))
                        risk = dev_risk + link_risk
                        comps.append((i, lat, load, risk))

                    # jika tidak ada kandidat feasible non-cloud, paksa cloud
                    if not comps and self.cloud is not None:
                        j = node2col.get(self.cloud)
                        if j is not None:
                            S2D[s][j] = 1
                        continue
                    elif not comps:
                        # tidak ada cloud: cari device dengan kapasitas minimum yang cukup (darurat)
                        feas = [(i, remCap.get(i, 0.0)) for i in self.I if remCap.get(i, 0.0) >= cr_s]
                        if feas:
                            i_best = min(feas, key=lambda t: t[1])[0]
                            S2D[s][node2col[i_best]] = 1
                            remCap[i_best] -= cr_s
                        continue

                    # NORMALISASI min–max pada kandidat
                    lats  = [t[1] for t in comps]
                    loads = [t[2] for t in comps]
                    risks = [t[3] for t in comps]
                    lmin, lmax = min(lats),  max(lats)
                    omin, omax = min(loads), max(loads)
                    rmin, rmax = min(risks), max(risks)

                    def norm(val, vmin, vmax):
                        return 0.0 if abs(vmax - vmin) < eps else (val - vmin) / (vmax - vmin)

                    # HITUNG SCORE & pilih minimum
                    best = None
                    for (i, lat, load, risk) in comps:
                        score = (
                            self.WEIGHTS["lat"]  * norm(lat,  lmin, lmax) +
                            self.WEIGHTS["res"]  * norm(load, omin, omax) +
                            self.WEIGHTS["risk"] * norm(risk, rmin, rmax)
                        )
                        if (best is None) or (score < best[0]):
                            best = (score, i)
                    best_i = best[1]

                    # tempatkan
                    j = node2col.get(best_i)
                    if j is None:
                        continue
                    S2D[s][j] = 1
                    if best_i != self.cloud:
                        remCap[best_i] -= cr_s

        # statistik
        nodeResUse, nodeNumServ = self.calculateNodeUsage(S2D)
        if verbose:
            fog_count = 0
            if self.cloud in self.I:
                cloud_idx = self.I.index(self.cloud)
                fog_count = sum(sum(row) for row in S2D) - sum(S2D[s][cloud_idx] for s in self.S)
            else:
                fog_count = sum(sum(row) for row in S2D)
            cloud_services = len(self.S)
            print(f"[WCN] Number of services in fog (WCN): {fog_count}")
            print(f"[WCN] Number of services in cloud (WCN): {cloud_services}")
            print(f"[WCN] Finished WCN in {time.time()-self._t0:.3f}s")

        # tulis JSON
        alloc = self._buildAllocationList(S2D)
        out_json = self._writeAllocationJson(alloc)
        if verbose:
            print(f"[WCN] allocation json: {out_json}")

        return S2D
