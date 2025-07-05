import random
import networkx as nx
from collections import defaultdict
from config import config


class Placement:
    """
    Mengimplementasikan Fase 2 dari FSPCN: Community Ranking dan Application Placement.
    """

    def __init__(self, network, communities, applications, users):
        self.network = network
        self.communities = communities
        self.applications = applications
        self.users = users.get("sources", [])

        self.placement_matrix = defaultdict(list)
        self.community_of_node = {
            node_id: comm_id
            for comm_id, nodes in self.communities.items()
            for node_id in nodes
        }

        self.available_resources = {
            node: data.get("RAM", 0) for node, data in self.network.nodes(data=True)
        }

    def _rank_communities(self):
        print("Memulai Community Ranking...")
        ranked_neighbors = defaultdict(list)
        community_ids = list(self.communities.keys())
        for i in range(len(community_ids)):
            for j in range(i + 1, len(community_ids)):
                comm_id1, comm_id2 = community_ids[i], community_ids[j]
                nodes1, nodes2 = self.communities[comm_id1], self.communities[comm_id2]
                boundary_edges_count = len(
                    list(nx.edge_boundary(self.network, nodes1, nodes2))
                )
                neighbor_distance = 1 / (boundary_edges_count + 1e-6)
                ranked_neighbors[comm_id1].append(
                    {"rank": neighbor_distance, "id": comm_id2}
                )
                ranked_neighbors[comm_id2].append(
                    {"rank": neighbor_distance, "id": comm_id1}
                )
        for comm_id in ranked_neighbors:
            ranked_neighbors[comm_id].sort(key=lambda x: x["rank"])
        print("Community Ranking selesai.")
        return ranked_neighbors

    def _try_place_app_in_community(self, app, community_nodes):
        temp_placement = defaultdict(list)
        temp_community_resources = {
            node_id: self.available_resources.get(node_id, 0)
            for node_id in community_nodes
        }
        for service in app["module"]:
            service_placed = False
            required_ram = service.get("RAM", 1)
            sorted_nodes = sorted(
                community_nodes,
                key=lambda n: temp_community_resources.get(n, 0),
                reverse=True,
            )
            for node_id in sorted_nodes:
                if temp_community_resources.get(node_id, 0) >= required_ram:
                    temp_placement[service["name"]].append(node_id)
                    temp_community_resources[node_id] -= required_ram
                    service_placed = True
                    break
            if not service_placed:
                return None
        return temp_placement

    def run(self):
        ranked_neighbors = self._rank_communities()
        print("Memulai Application Placement...")
        sorted_apps = sorted(self.applications, key=lambda x: x["deadline"])
        app_requests = defaultdict(list)
        for user in self.users:
            app_requests[user["app"]].append(user)

        for app in sorted_apps:
            if any(s["name"] in self.placement_matrix for s in app["module"]):
                continue
            req = app_requests.get(app["name"], [None])[0]
            if not req:
                continue

            home_community_id = self.community_of_node.get(req["id_resource"])
            if home_community_id is None:
                continue

            placement_result = self._try_place_app_in_community(
                app, self.communities[home_community_id]
            )
            if not placement_result:
                for neighbor in ranked_neighbors.get(home_community_id, []):
                    if neighbor["rank"] <= config.RANK_THRESHOLD:
                        placement_result = self._try_place_app_in_community(
                            app, self.communities[neighbor["id"]]
                        )
                        if placement_result:
                            break

            if placement_result:
                for service_name, node_ids in placement_result.items():
                    self.placement_matrix[service_name].extend(node_ids)
                    service_ram = next(
                        s["RAM"] for s in app["module"] if s["name"] == service_name
                    )
                    for node_id in node_ids:
                        self.available_resources[node_id] -= service_ram

        print("Application Placement selesai.")
        return dict(self.placement_matrix)
