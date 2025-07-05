import networkx as nx
import random
from config import config


def generate_network():
    """
    Membuat topologi jaringan berdasarkan model Barabasi-Albert.
    """
    random.seed(config.RANDOM_SEED)
    G = nx.barabasi_albert_graph(n=config.NUM_FOG_NODES, m=3, seed=config.RANDOM_SEED)

    for node_id in G.nodes():
        G.nodes[node_id]["id"] = node_id
        G.nodes[node_id]["RAM"] = random.randint(*config.NODE_RAM_RANGE)
        G.nodes[node_id]["IPT"] = random.randint(*config.NODE_IPT_RANGE)
        G.nodes[node_id]["TB"] = random.uniform(*config.NODE_STORAGE_RANGE)
        G.nodes[node_id]["type"] = "FOG_NODE"

    for u, v in G.edges():
        G.edges[u, v]["PR"] = random.randint(*config.LINK_PROPAGATION_RANGE)
        G.edges[u, v]["BW"] = random.randint(*config.LINK_BANDWIDTH_RANGE)

    centrality = nx.betweenness_centrality(G)
    sorted_nodes = sorted(centrality.items(), key=lambda item: item[1])

    num_fg = int(config.NUM_FOG_NODES * config.GATEWAY_NODES_PERCENTAGE)
    num_cfg = int(config.NUM_FOG_NODES * config.CLOUD_GATEWAY_NODES_PERCENTAGE)

    fg_nodes = [node_id for node_id, _ in sorted_nodes[:num_fg]]
    for node_id in fg_nodes:
        G.nodes[node_id]["type"] = "FOG_GATEWAY"

    cfg_nodes = [node_id for node_id, _ in sorted_nodes[-num_cfg:]]
    for node_id in cfg_nodes:
        G.nodes[node_id]["type"] = "CLOUD_FOG_GATEWAY"

    cloud_id = config.CLOUD_NODE_ID
    G.add_node(cloud_id, id=cloud_id, RAM=9e12, IPT=9e12, TB=9e12, type="CLOUD")

    for node_id in cfg_nodes:
        G.add_edge(node_id, cloud_id, PR=1, BW=1e9)

    return G
