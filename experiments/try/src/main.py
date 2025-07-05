import json
import os
import random
import networkx as nx

from yafs.core import Sim
from yafs.application import Application, Message
from yafs.topology import Topology
from yafs.placement import JSONPlacement
from yafs.population import Population
from yafs.selection import Selection
from yafs.distribution import exponential_distribution

from config import config

RESULTS_PATH = "results"
DATA_PATH = "data"


class CustomTopology(Topology):
    def __init__(self, name="CustomTopology"):
        super().__init__()
        self.name = name
        if self.G is None:
            self.G = nx.Graph()

    def load_from_node_link_data(self, json_data):
        if "nodes" not in json_data or "links" not in json_data:
            raise ValueError(
                "Format JSON tidak valid. Harus mengandung kunci 'nodes' dan 'links'."
            )
        self.G = nx.node_link_graph(json_data)
        for n in self.G.nodes():
            self.nodeAttributes[n] = self.G.nodes[n]
        print(
            f"Topologi berhasil dimuat dengan {self.G.number_of_nodes()} node dan {self.G.number_of_edges()} link."
        )


class JSONPopulation(Population):
    def __init__(self, name, json, iteration=0, **kwargs):
        super(JSONPopulation, self).__init__(name=name, **kwargs)
        self.data = json
        self.it = iteration

    def initial_allocation(self, sim, app_name):
        for item in self.data["sources"]:
            if item["app"] == app_name:
                idtopo = item["id_resource"]
                lambd = item["lambda"]
                app = sim.apps[app_name]
                msg = app.get_message(item["message"])
                dDistribution = exponential_distribution(
                    name="Exp", lambd=lambd, seed=self.it
                )
                sim.deploy_source(
                    app_name, id_node=idtopo, msg=msg, distribution=dDistribution
                )


class DeviceSpeedAwareRouting(Selection):
    def __init__(self):
        self.cache = {}
        self.MAX_CACHE_SIZE = 10000
        super(DeviceSpeedAwareRouting, self).__init__()

    def get_path(
        self, sim, app_name, message, topology_src, alloc_module, traffic, from_des
    ):
        node_src = topology_src
        DES_dst = alloc_module[app_name][message.dst]
        if len(self.cache) > self.MAX_CACHE_SIZE:
            items_to_delete = random.sample(
                list(self.cache.keys()), len(self.cache) // 2
            )
            for item in items_to_delete:
                del self.cache[item]
        cache_key = (node_src, tuple(DES_dst))
        if cache_key not in self.cache:
            self.cache[cache_key] = self.compute_DSAR(
                node_src, sim.alloc_DES, sim, DES_dst, message
            )
        path, des = self.cache[cache_key]
        return [path] if des is not None else [], [des] if des is not None else []

    def compute_DSAR(self, node_src, alloc_DES, sim, DES_dst, message):
        try:
            bestSpeed, minPath, bestDES = float("inf"), [], None
            for dev in DES_dst:
                node_dst = alloc_DES[dev]
                path = list(
                    nx.shortest_path(sim.topology.G, source=node_src, target=node_dst)
                )
                speed = 0
                for i in range(len(path) - 1):
                    link = (path[i], path[i + 1])
                    bw_ms = sim.topology.G.edges[link][Topology.LINK_BW] / 1000.0
                    speed += sim.topology.G.edges[link][Topology.LINK_PR] + (
                        message.bytes * 8 / bw_ms if bw_ms > 0 else float("inf")
                    )
                att_node = sim.topology.get_nodes_att()[path[-1]]
                speed += message.inst / float(att_node["IPT"])
                if speed < bestSpeed:
                    bestSpeed, minPath, bestDES = speed, path, dev
            return minPath, bestDES
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return [], None


def create_applications_from_json(app_definitions):
    applications = {}
    for app_def in app_definitions:
        a = Application(name=app_def["name"])
        modules = [{"None": {"Type": Application.TYPE_SOURCE}}]
        for module in app_def["module"]:
            modules.append(
                {
                    module["name"]: {
                        "RAM": module["RAM"],
                        "Type": Application.TYPE_MODULE,
                    }
                }
            )
        a.set_modules(modules)
        messages = {}
        for msg_def in app_def["message"]:
            messages[msg_def["name"]] = Message(
                msg_def["name"],
                msg_def["s"],
                msg_def["d"],
                instructions=msg_def.get("instructions", 0),
                bytes=msg_def.get("bytes", 0),
            )
            if msg_def["s"] == "None":
                a.add_source_messages(messages[msg_def["name"]])
        for transmission in app_def["transmission"]:
            msg_in = messages[transmission["message_in"]]
            if "message_out" in transmission:
                a.add_service_module(
                    transmission["module"],
                    msg_in,
                    messages[transmission["message_out"]],
                    lambda: 1.0,
                )
            else:
                a.add_service_module(transmission["module"], msg_in)
        applications[app_def["name"]] = a
    return applications


def main():
    print("--- Memulai Simulasi Dinamis YAFS ---")
    print("1. Memuat file definisi...")
    try:
        network_json = json.load(
            open(os.path.join(DATA_PATH, "networkDefinition.json"))
        )
        app_json = json.load(open(os.path.join(DATA_PATH, "appDefinition.json")))
        users_json = json.load(open(os.path.join(DATA_PATH, "usersDefinition.json")))
        placement_json = json.load(
            open(os.path.join(RESULTS_PATH, "placement_result_20apps.json"))
        )
    except FileNotFoundError as e:
        print(
            f"Error: Pastikan semua file definisi ada. File yang hilang: {e.filename}"
        )
        return
    print("2. Membangun topologi...")
    topology = CustomTopology()
    topology.load_from_node_link_data(network_json)
    print("3. Membuat definisi aplikasi YAFS...")
    applications = create_applications_from_json(app_json)
    print("4. Menerapkan hasil penempatan FSPCN...")
    placement = JSONPlacement(name="FSPCN_Placement", json=placement_json)
    print("5. Menggunakan selector DeviceSpeedAwareRouting...")
    selector = DeviceSpeedAwareRouting()
    stop_time = 100000
    results_folder = os.path.join(RESULTS_PATH, f"sim_trace_{stop_time}ms")
    s = Sim(topology, default_results_path=results_folder)
    print("6. Mendeploy aplikasi ke simulator...")
    for app_name, app_obj in applications.items():
        app_users = [u for u in users_json["sources"] if u["app"] == app_name]
        if not app_users:
            continue
        pop_app = JSONPopulation(
            name=f"Pop_{app_name}", json={"sources": app_users}, iteration=0
        )
        s.deploy_app2(
            app=app_obj, placement=placement, population=pop_app, selector=selector
        )
    print(f"\n7. Menjalankan simulasi hingga waktu {stop_time}...")
    s.run(stop_time, show_progress_monitor=True)
    print(
        "\n--- Simulasi Selesai ---\n"
        + f"Hasil simulasi (trace CSV) disimpan di folder: {results_folder}"
    )


if __name__ == "__main__":
    for path in [DATA_PATH, RESULTS_PATH]:
        if not os.path.exists(path):
            os.makedirs(path)
    random.seed(config.RANDOM_SEED)
    main()
