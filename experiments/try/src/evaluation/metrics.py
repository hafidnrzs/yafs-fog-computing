import networkx as nx
import pandas as pd
from collections import defaultdict
import itertools


def _calculate_path_delay(path: list, graph: nx.Graph, packet_size: float) -> float:
    total_delay = 0
    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        link_data = graph.get_edge_data(u, v)
        if link_data:
            bw_ms = link_data.get("BW", 1) / 1000.0
            pr_ms = link_data.get("PR", 0)
            transmission_delay = packet_size / bw_ms if bw_ms > 0 else float("inf")
            link_delay = pr_ms + transmission_delay
            total_delay += link_delay
    return total_delay


def calculate_adra(
    start_node: int, end_node: int, graph: nx.Graph, packet_size: float
) -> float:
    try:
        path = nx.shortest_path(graph, source=start_node, target=end_node)
        return _calculate_path_delay(path, graph, packet_size)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return float("inf")


def calculate_adsa(
    target_app: dict,
    placement_matrix: dict,
    network_graph: nx.Graph,
    packet_size: float,
) -> float:
    service_list = [module["name"] for module in target_app.get("module", [])]
    all_device_locations = set()
    for service_name in service_list:
        locations = placement_matrix.get(service_name, [])
        all_device_locations.update(locations)
    if len(all_device_locations) < 2:
        return 0.0
    services_delay_list = []
    for dev1, dev2 in itertools.combinations(list(all_device_locations), 2):
        delay = calculate_adra(dev1, dev2, network_graph, packet_size)
        if delay != float("inf"):
            services_delay_list.append(delay)
    if not services_delay_list:
        return 0.0
    return sum(services_delay_list) / len(services_delay_list)


def calculate_placement_metrics(placement_matrix, config):
    total_placements = sum(len(nodes) for nodes in placement_matrix.values())
    if total_placements == 0:
        return {"cloud_placement_rate": 0.0}
    placements_in_cloud = sum(
        1
        for nodes in placement_matrix.values()
        for node_id in nodes
        if node_id == config.CLOUD_NODE_ID
    )
    return {"cloud_placement_rate": placements_in_cloud / total_placements}


def calculate_availability_metric(placement_matrix, network, applications, users):
    if not users:
        return 0.0
    app_service_map = {
        app["name"]: [m["name"] for m in app["module"]] for app in applications
    }
    available_requests = 0
    for user_req in users:
        app_id = user_req["app"]
        requester_gateway = user_req["id_resource"]
        services_for_app = app_service_map.get(app_id, [])
        if not services_for_app:
            continue
        all_paths_exist = all(
            service in placement_matrix
            and any(
                nx.has_path(network, requester_gateway, node_id)
                for node_id in placement_matrix[service]
            )
            for service in services_for_app
        )
        if all_paths_exist:
            available_requests += 1
    return available_requests / len(users) if users else 0.0


def calculate_delay_metrics(placement_matrix, network, applications, users, config):
    delay_results = []
    app_map = {app["name"]: app for app in applications}
    packet_size = (config.PACKET_SIZE_RANGE[0] + config.PACKET_SIZE_RANGE[1]) / 2
    for app_id, app_data in app_map.items():
        adsa = calculate_adsa(app_data, placement_matrix, network, packet_size)
        user_for_app = next((u for u in users if u["app"] == app_id), None)
        adra = 0.0
        if user_for_app:
            requester_node = user_for_app["id_resource"]
            entry_module_name = next(
                (
                    t.get("module")
                    for t in app_data.get("transmission", [])
                    if t.get("message_in") == f"M.USER.APP.{app_id}"
                ),
                None,
            )
            if entry_module_name and entry_module_name in placement_matrix:
                entry_nodes = placement_matrix[entry_module_name]
                min_adra = min(
                    (
                        calculate_adra(requester_node, node, network, packet_size)
                        for node in entry_nodes
                    ),
                    default=float("inf"),
                )
                adra = min_adra
        total_delay = adsa + adra if adra != float("inf") else float("inf")
        delay_results.append(
            {"app_id": app_id, "adra": adra, "adsa": adsa, "total_delay": total_delay}
        )
    return delay_results


def print_evaluation_summary(results):
    print("\n" + "=" * 50 + "\n--- HASIL EVALUASI EKSPERIMEN FSPCN ---\n" + "=" * 50)
    cloud_rate = results.get("placement_metrics", {}).get("cloud_placement_rate", 0)
    print(f"\n[Metrik Penempatan]\n  - Tingkat Penempatan di Cloud: {cloud_rate:.2%}")
    availability = results.get("availability", 0)
    print(
        f"\n[Metrik Ketersediaan]\n  - Rata-rata Ketersediaan Aplikasi: {availability:.2%}"
    )
    delay_df = pd.DataFrame(results.get("delay_metrics", []))
    if not delay_df.empty:
        delay_df.replace(float("inf"), pd.NA, inplace=True)
        avg_total_delay = delay_df["total_delay"].mean()
        print(
            f"\n[Metrik Delay]\n  - Rata-rata Total Delay (ADRA + ADSA): {avg_total_delay:.2f} ms"
        )
        print(
            "\nDetail Delay per Aplikasi:\n"
            + delay_df.to_string(index=False, float_format="%.2f")
        )
    print(
        "\n"
        + "=" * 50
        + "\nCatatan: Metrik 'Meet Deadline' dan 'Resource Usage' memerlukan simulasi dinamis (YAFS) untuk dihitung.\n"
        + "=" * 50
    )
