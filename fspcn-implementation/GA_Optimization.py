import time
import json
import networkx as nx
from experiment_configuration import ExperimentConfiguration

class GAOptimization:
    def __init__(self, expconf, cnf, num_communities=3):
        self.expconf = expconf
        self.cnf = cnf
        self.G = expconf.G
        self.num_communities = num_communities
        self.fog_nodes = [n for n, d in self.G.nodes(data=True) if d.get('level', 'fog') == 'fog']

    def run_ga_community_detection(self):
        # Simple random assignment as placeholder for actual GA
        # Replace this with your actual GA logic if sudah ada
        import random
        communities = [[] for _ in range(self.num_communities)]
        for idx, node in enumerate(self.fog_nodes):
            communities[idx % self.num_communities].append(node)
        return communities

    def solve(self, verbose=True):
        t = time.time()
        print("=== GA Optimization ===")

        # 1. Jalankan GA untuk deteksi komunitas
        communities = self.run_ga_community_detection()
        print(f"GA found {len(communities)} communities.")

        # 2. Siapkan struktur penempatan
        num_services = self.expconf.number_of_services
        num_devices = len(self.G.nodes)
        service2DevicePlacementMatrixGA = [
            [0 for _ in range(num_devices)]
            for _ in range(num_services)
        ]
        nodeBussyResourcesGA = {i: 0.0 for i in self.G.nodes}

        servicesInCloud = 0
        servicesInFog = 0
        allAlloc = {}
        myAllocationList = []

        # 3. Placement service ke device berdasarkan komunitas hasil GA
        for idServ in range(num_services):
            placed = False
            for comm in communities:
                for devId in comm:
                    if nodeBussyResourcesGA[devId] + self.expconf.service_resources[idServ] <= self.expconf.node_resources[devId]:
                        service2DevicePlacementMatrixGA[idServ][devId] = 1
                        nodeBussyResourcesGA[devId] += self.expconf.service_resources[idServ]
                        myAllocation = {
                            "app": self.expconf.map_service_to_apps[idServ],
                            "module_name": self.expconf.map_service_id_to_service_name[idServ],
                            "id_resource": devId
                        }
                        myAllocationList.append(myAllocation)
                        servicesInFog += 1
                        placed = True
                        break
                if placed:
                    break
            if not placed:
                myAllocation = {
                    "app": self.expconf.map_service_to_apps[idServ],
                    "module_name": self.expconf.map_service_id_to_service_name[idServ],
                    "id_resource": self.expconf.cloud_id
                }
                myAllocationList.append(myAllocation)
                servicesInCloud += 1

        # 4. Statistik penggunaan node
        nodeResUseGA, nodeNumServGA = self.calculateNodeUsage(service2DevicePlacementMatrixGA)

        print("Number of services in cloud (GA):", servicesInCloud)
        print("Number of services in fog (GA):", servicesInFog)

        allAlloc["initialAllocation"] = myAllocationList

        # 5. Simpan ke file JSON
        with open(self.cnf.data_folder + "/data/allocDefinitionGA.json", "w") as file:
            file.write(json.dumps(allAlloc, indent=2))

        print(str(time.time() - t) + " seconds for GA-based optimization")

        return service2DevicePlacementMatrixGA

    def calculateNodeUsage(self, service2DevicePlacementMatrix):
        nodeResUse = [0.0 for _ in self.G.nodes]
        nodeNumServ = [0 for _ in self.G.nodes]

        for idServ in range(len(service2DevicePlacementMatrix)):
            for idDev in range(len(service2DevicePlacementMatrix[idServ])):
                if service2DevicePlacementMatrix[idServ][idDev] == 1:
                    nodeNumServ[idDev] += 1
                    nodeResUse[idDev] += self.expconf.service_resources[idServ]

        for idDev in range(len(nodeResUse)):
            if self.expconf.node_resources[idDev] > 0:
                nodeResUse[idDev] = nodeResUse[idDev] / self.expconf.node_resources[idDev]
            else:
                nodeResUse[idDev] = 0.0

        nodeResUse = sorted(nodeResUse)
        nodeNumServ = sorted(nodeNumServ)
        return nodeResUse, nodeNumServ

if __name__ == "__main__":
    # 1. Load experiment configuration (no dummy, no halu)
    class Config:
        def __init__(self):
            self.data_folder = "."
            self.verbose_log = True
            self.graphic_terminal = False

    config = Config()
    expconf = ExperimentConfiguration(config)
    expconf.load_configuration("iotjournal")  # atau preset lain sesuai kebutuhanmu
    expconf.network_generation()
    expconf.app_generation()

    # 2. Jalankan GAOptimization
    gaopt = GAOptimization(expconf, config, num_communities=3)
    ga_matrix = gaopt.solve(verbose=True)
    print("GA Placement Matrix:")
    for row in ga_matrix:
        print(row)