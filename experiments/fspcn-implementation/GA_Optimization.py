import time
import json
import networkx as nx
from experiment_configuration import ExperimentConfiguration
from GA_community import GACommunity  

class GAOptimization:
    def __init__(self, expconf, cnf, num_communities=3):
        self.expconf = expconf
        self.cnf = cnf
        self.G = expconf.G
        self.num_communities = num_communities
        self.fog_nodes = [n for n, d in self.G.nodes(data=True) if d.get('level', 'fog') == 'fog']

    def run_ga_community_detection(self):
        # --- Step 1: GA cari komunitas tiap node ---
        ga = GACommunity(
            self.G,
            num_communities=self.num_communities,
            generations=50,  # atau sesuai kebutuhan
            population_size=30,
            mutation_rate=0.1,
            omega_1=1.0, omega_2=1.0, omega_3=1.0,
            w_RAM=1.0, w_TB=1.0, w_IPT=1.0
        )
        best_chromosome, _ = ga.run()
        # best_chromosome: list of community assignment, index = node index
        # Map node ke komunitas
        node_list = list(self.fog_nodes)
        comm_map = {}
        for idx, comm_id in enumerate(best_chromosome):
            comm_map.setdefault(comm_id, []).append(node_list[idx])
        communities = list(comm_map.values())
        return communities

    def community_ranking(self, communities):
        # Kombinasi resource: RAM, IPT, STO (bobot bisa kamu atur)
        def total_resource(comm):
            ram = sum(self.G.nodes[n].get('RAM', 0) for n in comm)
            ipt = sum(self.G.nodes[n].get('IPT', 0) for n in comm)
            sto = sum(self.G.nodes[n].get('STO', 0) for n in comm)
            # Contoh bobot: RAM 0.4, IPT 0.4, STO 0.2
            return 0.4 * ram + 0.4 * ipt + 0.2 * sto
        ranked = sorted(communities, key=total_resource, reverse=True)
        return ranked

    def solve(self, verbose=True):
        t = time.time()
        print("=== GA Optimization (FSPCN) ===")

        # 1. GA cari komunitas tiap node
        communities = self.run_ga_community_detection()
        print(f"GA found {len(communities)} communities.")

        # 2. Community ranking (kombinasi resource)
        ranked_communities = self.community_ranking(communities)
        if verbose:
            for i, comm in enumerate(ranked_communities):
                print(f"Community {i+1}: nodes={comm}")

        # 3. Application placement
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

        for idServ in range(num_services):
            placed = False
            # Prioritaskan komunitas ranking atas
            for comm in ranked_communities:
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

        # 5. Simpan ke appAllocation.json
        output_path = self.cnf.data_folder + "/fspcn-implementation/dataGA/allocDefinitionGAcls.json"
        with open(output_path, "w") as file:
            file.write(json.dumps(allAlloc, indent=2))

        print("Allocation saved to", output_path)
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