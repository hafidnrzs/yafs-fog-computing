import networkx as nx

def select_routes(graph, placement, service_pairs, routing="shortest"):
    """
    Menentukan rute komunikasi antar service/module berdasarkan hasil placement.
    :param graph: NetworkX graph (topology komunitas yang sudah ada placement)
    :param placement: dict mapping service_name -> node_name (hasil GA placement)
    :param service_pairs: list of tuple (service_src, service_dst)
    :param routing: "shortest" (default) atau "latency"
    :return: dict mapping (service_src, service_dst) -> [node1, node2, ...] (jalur node)
    """
    routes = {}
    for src, dst in service_pairs:
        src_node = placement[src]
        dst_node = placement[dst]
        if routing == "shortest":
            try:
                path = nx.shortest_path(graph, source=src_node, target=dst_node)
            except nx.NetworkXNoPath:
                path = []
        elif routing == "latency":
            try:
                path = nx.shortest_path(graph, source=src_node, target=dst_node, weight="PR")
            except nx.NetworkXNoPath:
                path = []
        else:
            raise ValueError("Unknown routing type")
        routes[(src, dst)] = path
    return routes

# Contoh penggunaan:
if __name__ == "__main__":
    # Misal graph, placement, dan services sudah ada dari main.py
    import networkx as nx

    # Dummy graph dan placement untuk contoh
    G = nx.Graph()
    G.add_edges_from([("A", "B"), ("B", "C"), ("C", "D")])
    placement = {"Service_1": "A", "Service_2": "D"}
    service_pairs = [("Service_1", "Service_2")]

    routes = select_routes(G, placement, service_pairs)
    print(routes)