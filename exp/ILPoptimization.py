# ============================================================
# ILPoptimization.py
# Baseline ILP Placement (robust + style seragam)
# ============================================================

from __future__ import annotations
import os
import json
import time
from collections import defaultdict

import networkx as nx
import pulp as pl


class ILP:
    """
    Baseline Integer Linear Programming (single objective):
      - Decision vars: x[s, i, a] ∈ {0,1}  (service s, device i, user-request a)
      - Objective    : minimize total latency gateway(a) -> device(i)
      - Constraints  : assignment == 1 per (s, a); kapasitas RAM per device
    Output:
      - Matriks biner [num_services x num_devices]
      - allocDefinitionILP.json (format identik dengan algoritma lain)
      - Fallback: satu entri Cloud per service
    """

    # -------------------------------------------------------
    # INIT
    # -------------------------------------------------------
    def __init__(self, ec, cnf):
        self.ec = ec
        self.cnf = cnf

        # himpunan dasar
        self.S = list(range(self.ec.numberOfServices))          # service ids [0..num_services-1]
        self.I = list(self.ec.G.nodes())                        # device ids (fog + cloud), bisa non-urut
        self.cloud = getattr(self.ec, "cloudId", None)

        # peta service <-> app & nama service (bisa dict atau list)
        self.s2app = getattr(self.ec, "mapService2App", {})
        self.sname = getattr(self.ec, "mapServiceId2ServiceName", {})

        # resource skalar (RAM) dan kapasitas node (bisa dict atau list)
        self.CR = getattr(self.ec, "servicesResources", [])
        self.AR = getattr(self.ec, "nodeResources", {})

        # daftar user-requests: (app_id:int, user_idx:int, gateway_id:int)
        self.A = self._build_requests()

        # precompute shortest path latency gateway -> device
        self.L = self._precompute_latencies()

        self._t0 = time.time()

    # -------------------------------------------------------
    # Helper umum: akses aman dict/list
    # -------------------------------------------------------
    def _app_of(self, s: int) -> int:
        """
        Kembalikan app_id untuk service s.
        Mendukung self.s2app berupa dict {s: app_id} atau list/tuple [app_id_by_index].
        """
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
        """
        Kembalikan nama service untuk indeks s.
        Mendukung self.sname berupa dict {s: "name"} atau list/tuple ["name", ...].
        """
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
        """
        Resource demand (RAM) untuk service s. Mendukung dict/list.
        """
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
        """
        Kapasitas RAM untuk device i. Mendukung dict keyed by device_id atau list sejajar index.
        Catatan: jika self.AR adalah list, diasumsikan indeksnya sejajar dengan nilai device id (umumnya 0..N-1).
        """
        m = self.AR
        try:
            if isinstance(m, dict):
                return float(m.get(i, 0.0))
            elif isinstance(m, (list, tuple)):
                # jika i integer dan dalam range, ambil langsung
                if isinstance(i, int) and 0 <= i < len(m):
                    return float(m[i])
        except Exception:
            pass
        return 0.0

    # -------------------------------------------------------
    # Normalisasi app_id (bila app_key adalah object/graph)
    # -------------------------------------------------------
    def _normalize_app_id(self, app_key) -> int:
        """
        Pastikan app_id menjadi int:
        - Jika sudah int/str numerik -> cast ke int.
        - Jika object (mis. DiGraph/Application), cari index-nya di self.ec.apps.
        - Jika gagal, fallback 0.
        """
        # 1) coba konversi langsung
        try:
            return int(app_key)
        except Exception:
            pass

        # 2) cari posisinya di ec.apps
        apps = getattr(self.ec, "apps", None)
        if isinstance(apps, (list, tuple)) and apps:
            for idx, app_obj in enumerate(apps):
                # identitas objek sama
                if app_obj is app_key:
                    return idx
                # equality
                try:
                    if app_obj == app_key:
                        return idx
                except Exception:
                    pass
                # jika punya atribut 'name'
                try:
                    if hasattr(app_obj, "name") and hasattr(app_key, "name"):
                        if app_obj.name == app_key.name:
                            return idx
                except Exception:
                    pass

        # 3) fallback terakhir
        return 0

    # -------------------------------------------------------
    # Build requests dari ec.appsRequests (robust)
    # -------------------------------------------------------
    def _build_requests(self):
        """
        Kembalikan list tuple (app_id:int, user_idx:int, gateway_id:int) dari ec.appsRequests.

        Mendukung format:
        1) dict: {app_key: [gw1, gw2, ...]} atau {app_key: {"gateways":[...] } }
        2) list of dict: [{"app": app_key, "gateways":[...]}]
        3) list of list/tuple: [[gw...], [gw...], ...]  (index list = app_id)
        4) list sederhana: [gw1, gw2, ...]  (diasumsikan app_id = 0)

        Jika kosong/tidak dikenal → fallback:
        1 request per app di semua node bertipe FG/FOG/Gateway (atau semua node jika tak ada tipe tersebut).
        """
        A = []
        appsRequests = getattr(self.ec, "appsRequests", None)

        def _as_gateway_id(g):
            # normalisasikan kandidat gateway menjadi int id node
            # dukung: int/str numerik, dict {"id":...}, list/tuple [id,...], tuple (node_id, data_dict)
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
                gid = _as_gateway_id(g)
                A.append((int(app_id), int(idx), int(gid)))

        # ---- Parse utama ----
        if isinstance(appsRequests, dict) and appsRequests:
            # {app_key: [gw...]} atau {app_key: {"gateways":[...]}}
            for app_key, reqs in appsRequests.items():
                if isinstance(reqs, dict) and "gateways" in reqs:
                    _append(app_key, reqs["gateways"])
                else:
                    _append(app_key, reqs)

        elif isinstance(appsRequests, list) and appsRequests:
            # list of dict: [{"app": app_key, "gateways":[...]}]
            if all(isinstance(x, dict) for x in appsRequests) and all(("gateways" in x) for x in appsRequests):
                for item in appsRequests:
                    app_key = item.get("app", 0)
                    _append(app_key, item["gateways"])

            # list of list/tuple: [[gw...], [gw...], ...] (index list = app_id)
            elif all(isinstance(x, (list, tuple)) for x in appsRequests):
                for app_idx, gateways in enumerate(appsRequests):
                    _append(app_idx, gateways)

            # list sederhana: [gw1, gw2, ...]  → app_id = 0
            else:
                _append(0, appsRequests)

        # ---- Fallback bila A kosong ----
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

        # Debug ringan
        if getattr(self.cnf, "verbose_log", False):
            sample = A[:min(5, len(A))]
            print(f"[ILP] appsRequests parsed → {len(A)} requests; sample={sample}")
        return A

    # -------------------------------------------------------
    # Precompute latency gateway->device
    # -------------------------------------------------------
    def _precompute_latencies(self):
        """Latency L[(g, i)] = shortest-path length (weight='weight') dari gateway g ke device i."""
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
        path = os.path.join(outdir, "allocDefinitionILP.json")
        with open(path, "w") as f:
            json.dump({"initialAllocation": alloc}, f)
        return path

    # -------------------------------------------------------
    # Solve
    # -------------------------------------------------------
    def solve(self):
        verbose = bool(getattr(self.cnf, "verbose_log", False))
        if verbose:
            print("[ILP] Building model...")

        # mapping request relevan per service
        req_by_service = defaultdict(list)
        for s in self.S:
            app_id = self._app_of(s)
            for a in self.A:
                if int(a[0]) == app_id:
                    req_by_service[s].append(a)

        # model ILP
        model = pl.LpProblem("ILP_Service_Placement", pl.LpMinimize)

        # variabel keputusan: x[s, i, a]
        x = {}
        for s in self.S:
            for i in self.I:
                for a in req_by_service[s]:
                    var_name = f"x_s{s}_i{i}_a{a[0]}_{a[1]}_{a[2]}"
                    x[(s, i, a)] = pl.LpVariable(var_name, lowBound=0, upBound=1, cat=pl.LpBinary)

        # objektif: minimalkan total latency gateway(a)->device(i)
        if verbose:
            print("[ILP] Objective: minimize total user->device latency")
        obj_terms = []
        for s in self.S:
            for i in self.I:
                for a in req_by_service[s]:
                    gw = a[2]
                    cost = self.L.get((gw, i), 0.0)
                    if cost != 0.0:
                        obj_terms.append(x[(s, i, a)] * float(cost))
        model += pl.lpSum(obj_terms) if obj_terms else 0.0

        # kendala: assignment == 1 per (s, a)
        if verbose:
            print("[ILP] Constraints: assignment == 1 per (service, request), capacity per device")
        for s in self.S:
            for a in req_by_service[s]:
                model += pl.lpSum([x[(s, i, a)] for i in self.I]) == 1, f"assign_once_s{s}_a{a}"

        # kendala: kapasitas RAM per device
        for i in self.I:
            model += pl.lpSum([x[(s, i, a)] * self._cr_of(s)
                               for s in self.S for a in req_by_service[s]]) <= self._cap_of(i), f"cap_i{i}"

        # solve
        if verbose:
            print("[ILP] Solving...")
        status = model.solve(pl.PULP_CBC_CMD(msg=verbose))

        # bangun matriks hasil S2D (service x device)
        n_serv = len(self.S)
        n_dev = len(self.I)
        S2D = [[0 for _ in range(n_dev)] for _ in range(n_serv)]

        # set 1 jika ada minimal satu x[s,i,a] = 1 untuk request relevan
        for s in self.S:
            for j, i in enumerate(self.I):
                assigned = False
                for a in req_by_service[s]:
                    var = x[(s, i, a)]
                    if var.varValue is not None and var.varValue > 0.5:
                        assigned = True
                        break
                if assigned:
                    S2D[s][j] = 1

        # statistik
        nodeResUse, nodeNumServ = self.calculateNodeUsage(S2D)
        if verbose:
            fog_count = 0
            if self.cloud in self.I:
                cloud_idx = self.I.index(self.cloud)
                fog_count = sum(sum(row) for row in S2D) - sum(S2D[s][cloud_idx] for s in self.S)
            else:
                fog_count = sum(sum(row) for row in S2D)
            cloud_services = len(self.S)  # fallback cloud per service
            print(f"[ILP] Number of services in fog (ILP): {fog_count}")
            print(f"[ILP] Number of services in cloud (ILP): {cloud_services}")
            print(f"[ILP] Finished ILP in {time.time()-self._t0:.3f}s | status={pl.LpStatus[status]}")

        # tulis JSON
        alloc = self._buildAllocationList(S2D)
        out_json = self._writeAllocationJson(alloc)
        if verbose:
            print(f"[ILP] allocation json: {out_json}")

        return S2D
