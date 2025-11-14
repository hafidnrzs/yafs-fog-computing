
# -*- coding: utf-8 -*-
"""
MOLPoptimization.py
Multi-Objective Linear Programming (MOLP) for Service Placement in Fog (YAFS)
Objectives (weighted-sum):
  - Latency (proxy): shortest-path distance from service ingress to device.
  - Utilization: normalized CPU/RAM load per device.
  - Availability: penalize assignments to devices with low availability (unavailability).
Notes:
  * Minimal, drop-in file. Does not change other project files.
  * Logging mirrors ILP style.
  * Output JSON: allocDefinitionMOLP.json (compatible with main.py loader).
"""

import time
import json
import networkx as nx
import pulp
from collections import defaultdict

class MOLP:
    def __init__(self, ec, cnf):
        self.ec = ec
        self.cnf = cnf

        # weights (override via cnf if needed)
        self.w_latency       = getattr(self.cnf, "w_latency", 1.0)
        self.w_utilization   = getattr(self.cnf, "w_utilization", 0.3)
        self.w_availability  = getattr(self.cnf, "w_availability", 0.2)  # for UN-availability term

        # extra penalty for placing on cloud (optional)
        self.cloud_penalty   = getattr(self.cnf, "cloud_penalty", 1.0)

    # ---------- helpers ----------
    def _shortest_latency(self, src, dst):
        try:
            return nx.shortest_path_length(self.ec.G, source=src, target=dst, weight="weight")
        except Exception:
            return 1e6  # large penalty if unreachable

    def _get_result_folder(self):
        result_folder = (
            getattr(self.ec, 'resultFolder', None)
            or getattr(self.cnf, 'resultFolder', None)
            or getattr(self.ec, 'resultsPath', None)
            or getattr(self.ec, 'pathExperimento', None)
            or '.'
        )
        import os
        try:
            os.makedirs(result_folder, exist_ok=True)
        except Exception:
            pass
        return result_folder

    def solve(self):
        print("Computing betweenness centrality...")
        _ = nx.betweenness_centrality(self.ec.G, weight="weight")

        print("Starting MOLP optimization....")
        t0 = time.time()

        # sets
        services = list(range(int(self.ec.numberOfServices)))
        devices  = list(self.ec.G.nodes)

        # ---- discover cloud nodes robustly ----
        cloud_ids = []
        try:
            cfg_cloud = int(self.ec.cloudId)
        except Exception:
            cfg_cloud = None
        if cfg_cloud is not None and cfg_cloud in devices:
            cloud_ids = [cfg_cloud]
        else:
            if hasattr(self.ec, "devices"):
                try:
                    if isinstance(self.ec.devices, dict):
                        for did, nd in self.ec.devices.items():
                            if nd.get("type") == "C" and did in devices:
                                cloud_ids.append(did)
                    else:
                        for nd in self.ec.devices:
                            did = nd.get("id")
                            if nd.get("type") == "C" and did in devices:
                                cloud_ids.append(did)
                except Exception:
                    pass
        if not cloud_ids:
            print("[MOLP] Warning: No cloud node found in graph devices; cloud penalty term disabled.")
        else:
            print(f"[MOLP] Cloud nodes detected in graph: {cloud_ids}")

        # decision variables
        x = pulp.LpVariable.dicts("x", (services, devices), cat=pulp.LpBinary)

        # model
        prob = pulp.LpProblem("ServicePlacementMOLP", pulp.LpMinimize)

        # ---------- constraints ----------
        # assign each service exactly once
        for s in services:
            prob += pulp.lpSum([x[s][i] for i in devices]) == 1, f"assign_once_s{s}"

        # capacities (RAM & CPU where available)
        ram_cap = {}
        ipt_cap = {}
        availability = {}

        availability_map = {}
        if hasattr(self.ec, "availability"):
            try:
                availability_map.update(self.ec.availability)
            except Exception:
                pass

        for i in devices:
            nd = None
            if hasattr(self.ec, "devices"):
                if isinstance(self.ec.devices, dict):
                    nd = self.ec.devices.get(i, {})
                else:
                    for d in self.ec.devices:
                        if d.get("id") == i:
                            nd = d
                            break
            ram_cap[i] = int(nd.get("RAM", 10**9)) if nd else 10**9
            ipt_cap[i] = float(nd.get("IPT", 0.0)) if nd else 0.0
            availability[i] = float(availability_map.get(i, nd.get("availability", 1.0) if nd else 1.0))

        # service demands (RAM and CPU)
        service_ram = defaultdict(lambda: 1)
        if hasattr(self.ec, "serviceRAM"):
            try:
                service_ram.update(self.ec.serviceRAM)
            except Exception:
                pass

        service_cpu = defaultdict(lambda: 1.0)  # abstract CPU demand per service
        # fallback options: serviceCPU map or normalize serviceINSTR
        if hasattr(self.ec, "serviceCPU"):
            try:
                service_cpu.update(self.ec.serviceCPU)
            except Exception:
                pass
        elif hasattr(self.ec, "serviceINSTR"):
            try:
                K = 1e6  # scaling to keep values reasonable
                for s in services:
                    instr = float(self.ec.serviceINSTR.get(s, 1.0))
                    service_cpu[s] = max(1.0, instr / K)
            except Exception:
                pass

        # RAM capacity constraints
        for i in devices:
            prob += pulp.lpSum([service_ram[s] * x[s][i] for s in services]) <= ram_cap[i], f"ram_cap_i{i}"

        # optional CPU capacity (only if IPT > 0 for device)
        for i in devices:
            if ipt_cap[i] > 0:
                prob += pulp.lpSum([service_cpu[s] * x[s][i] for s in services]) <= ipt_cap[i], f"cpu_cap_i{i}"

        # ---------- objectives (weighted-sum) ----------
        # 1) Latency: dist(ingress_s, i)
        service_ingress = defaultdict(lambda: None)
        if hasattr(self.ec, "serviceIngress"):
            try:
                service_ingress.update(self.ec.serviceIngress)
            except Exception:
                pass

        dist_coeff = defaultdict(dict)
        for s in services:
            src = service_ingress[s]
            for i in devices:
                dist_coeff[s][i] = 0.0 if src is None else float(self._shortest_latency(src, i))
        obj_latency = pulp.lpSum([dist_coeff[s][i] * x[s][i] for s in services for i in devices])

        # 2) Utilization: sum_i (load_cpu/ipt + load_ram/ram)
        eps = 1e-9
        inv_ipt = {i: (1.0 / (ipt_cap[i] + eps)) for i in devices}
        inv_ram = {i: (1.0 / (ram_cap[i] + eps)) for i in devices}
        obj_util_cpu = pulp.lpSum([(service_cpu[s] * inv_ipt[i]) * x[s][i] for s in services for i in devices])
        obj_util_ram = pulp.lpSum([(service_ram[s] * inv_ram[i]) * x[s][i] for s in services for i in devices])
        obj_utilization = obj_util_cpu + obj_util_ram

        # 3) Availability: penalize unavailability * cpu load
        unavail = {i: max(0.0, 1.0 - float(availability[i])) for i in devices}
        obj_unavailability = pulp.lpSum([(unavail[i] * service_cpu[s]) * x[s][i] for s in services for i in devices])

        # Optional cloud usage penalty (if you still want it)
        obj_cloud = 0 if not cloud_ids else pulp.lpSum([x[s][i] for s in services for i in cloud_ids]) * self.cloud_penalty

        prob += (
            self.w_latency      * obj_latency +
            self.w_utilization  * obj_utilization +
            self.w_availability * obj_unavailability +
            obj_cloud
        )

        # ---------- solve ----------
        print(f"Solving global MOLP: {len(services)} services, {len(devices)} devices")
        t_solve = time.time()
        prob.solve(pulp.PULP_CBC_CMD(msg=False))
        print(f"Global MOLP solved in {time.time() - t_solve:.2f} seconds")

        # ---------- extract solution ----------
        alloc = []
        servicesInCloud = 0
        servicesInFog   = 0

        for s in services:
            chosen = None
            for i in devices:
                val = pulp.value(x[s][i])
                if val is not None and val > 0.5:
                    chosen = i
                    break
            if chosen is None:
                # fallback: choose a cloud node if exists, else first device
                chosen = (cloud_ids[0] if cloud_ids else devices[0])

            appId = int(self.ec.mapService2App[s]) if hasattr(self.ec, "mapService2App") else 0
            # IMPORTANT: keep module_name compatible with ILP loader (e.g., "appId_serviceId")
            if hasattr(self.ec, "serviceNames") and s in getattr(self.ec, "serviceNames"):
                modName = str(self.ec.serviceNames[s])
            else:
                modName = f"{appId}_{s}"

            alloc.append({"app": str(appId), "module_name": modName, "id_resource": int(chosen)})

            if cloud_ids and chosen in cloud_ids:
                servicesInCloud += 1
            else:
                servicesInFog += 1

        allocation = {"initialAllocation": alloc}

        # ---------- write json ----------
        result_folder = self._get_result_folder()
        out_path = result_folder + "/allocDefinitionMOLP.json"
        with open(out_path, "w") as f:
            json.dump(allocation, f)

        # ---------- summary log ----------
        print("Number of services in cloud (MOLP) (servicesInCloud): " + str(servicesInCloud))
        print("Number of services in fog (MOLP) (servicesInFog): " + str(servicesInFog))
        print(str(time.time() - t0) + " time for MOLP optimization")

        return allocation
