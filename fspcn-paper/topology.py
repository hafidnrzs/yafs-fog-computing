"""Functions for mock chromosome generation and topology creation."""
import random
import networkx as nx
from yafs.topology import Topology
from config import *

def generate_mock_chromosome(num_nodes, num_communities):
    """
    Menghasilkan kromosom mock yang memetakan node ke ID komunitas.
    ID Komunitas akan berupa integer dari 1 hingga num_communities.
    """
    print(f"Generating mock chromosome for {num_nodes} nodes into {num_communities} communities...")
    chromosome = [0] * num_nodes
    if num_communities == 0:  # Hindari ZeroDivisionError
        print("Warning: NUM_COMMUNITIES is 0. All nodes will be in community 0 (undefined).")
        return chromosome

    nodes_per_community_ideal = num_nodes // num_communities

    for i in range(num_nodes):
        # ID Komunitas dari 1 hingga num_communities
        community_id_int = (i // nodes_per_community_ideal) + 1
        # Pastikan tidak melebihi num_communities
        if community_id_int > num_communities:
            community_id_int = num_communities
        chromosome[i] = community_id_int
    print("Mock chromosome generated.")
    return chromosome

def create_topology():
    """
    Membuat topologi YAFS berdasarkan parameter dari paper, termasuk integrasi komunitas.
    """
    print("Creating topology...")

    # 1. Inisialisasi objek Topology YAFS
    yafs_topology_instance = Topology()

    # 2. Buat graf NetworkX untuk fog nodes
    if NUM_FOG_NODES <= BARABASI_M:
        print(f"Warning: NUM_FOG_NODES ({NUM_FOG_NODES}) should be > BARABASI_M ({BARABASI_M}). Using a complete graph for fog nodes.")
        fog_graph_nx = nx.complete_graph(NUM_FOG_NODES)
    else:
        fog_graph_nx = nx.barabasi_albert_graph(n=NUM_FOG_NODES, m=BARABASI_M, seed=SEED)

    # Ganti nama node di fog_graph_nx agar menjadi string "f_i"
    node_mapping = {i: f"f_{i}" for i in range(NUM_FOG_NODES)}
    final_graph_nx = nx.relabel_nodes(fog_graph_nx, node_mapping, copy=True)

    # --- INTEGRASI KOMUNITAS: Hasilkan Kromosom Mock ---
    mock_chromosome = generate_mock_chromosome(NUM_FOG_NODES, NUM_COMMUNITIES)

    # 3. Siapkan atribut untuk fog nodes
    node_attrs_ram = {}
    node_attrs_ipt = {}
    node_attrs_sto = {}
    node_attrs_level = {}
    node_attrs_type = {}
    node_attrs_community = {}

    fog_node_names = [f"f_{i}" for i in range(NUM_FOG_NODES)]
    for i, node_name in enumerate(fog_node_names):
        node_attrs_ram[node_name] = random.randint(MIN_FOG_RAM_MB, MAX_FOG_RAM_MB)
        node_attrs_ipt[node_name] = random.randint(MIN_FOG_IPT_INSTR_MS, MAX_FOG_IPT_INSTR_MS)
        node_attrs_sto[node_name] = round(random.uniform(MIN_FOG_TB_TERABYTE, MAX_FOG_TB_TERABYTE), 2)
        node_attrs_level[node_name] = "fog"
        node_attrs_type[node_name] = "fog_node"

        # Tetapkan ID komunitas dari kromosom mock
        if i < len(mock_chromosome):  # Pastikan index tidak keluar batas
            community_id_int = mock_chromosome[i]
            node_attrs_community[node_name] = f"CV{community_id_int}"  # Simpan sebagai string "CV1", "CV2", dst.
        else:
            node_attrs_community[node_name] = "CV_Undefined"

    # 4. Siapkan atribut untuk fog edges (link antar fog node)
    edge_attrs_bw = {}
    edge_attrs_pr = {}

    for u, v in final_graph_nx.edges():
        edge_attrs_bw[(u, v)] = random.randint(MIN_LINK_BW_BPS, MAX_LINK_BW_BPS)
        edge_attrs_pr[(u, v)] = random.randint(MIN_LINK_PD_MS, MAX_LINK_PD_MS)

    # 5. Tambahkan cloud nodes ke final_graph_nx
    cloud_node_names = []
    for i in range(NUM_CLOUD_NODES):
        cloud_name = f"cloud_{i}"
        cloud_node_names.append(cloud_name)
        final_graph_nx.add_node(cloud_name)

        # Atur atribut untuk cloud node
        node_attrs_ram[cloud_name] = DEFAULT_CLOUD_RAM_MB
        node_attrs_ipt[cloud_name] = DEFAULT_CLOUD_IPT_INSTR_MS
        node_attrs_sto[cloud_name] = DEFAULT_CLOUD_STO_TB
        node_attrs_level[cloud_name] = "cloud"
        node_attrs_type[cloud_name] = "cloud_server"
        # Cloud node tidak termasuk dalam komunitas fog
        node_attrs_community[cloud_name] = None

    # 6. Tentukan CFG (Cloud-Fog Gateway) nodes
    current_fog_node_names = [name for name, data in final_graph_nx.nodes(data=True)
                            if data.get('level') == 'fog']

    fog_only_subgraph = final_graph_nx.subgraph(current_fog_node_names).copy()
    
    if fog_only_subgraph.number_of_nodes() > 0 and fog_only_subgraph.number_of_edges() > 0:
        betweenness = nx.betweenness_centrality(fog_only_subgraph, normalized=True, endpoints=False)
        sorted_fog_nodes_by_centrality = sorted(betweenness.items(), key=lambda item: item[1], reverse=True)
    elif fog_only_subgraph.number_of_nodes() > 0:
        temp_fog_node_names = list(current_fog_node_names)
        random.shuffle(temp_fog_node_names)
        sorted_fog_nodes_by_centrality = [(name, 0) for name in temp_fog_node_names]
    else:
        sorted_fog_nodes_by_centrality = []

    num_cfg_nodes_target = max(1, int(NUM_FOG_NODES * PERCENT_CFG_NODES)) if NUM_FOG_NODES > 0 else 0
    actual_num_cfg_to_select = min(num_cfg_nodes_target, len(sorted_fog_nodes_by_centrality))
    cfg_node_names = [name for name, _ in sorted_fog_nodes_by_centrality[:actual_num_cfg_to_select]]

    for cfg_name in cfg_node_names:
        node_attrs_type[cfg_name] = "CFG"

    # 7. Tentukan FG (Fog Gateway) nodes
    remaining_fog_nodes_for_fg = [
        (name, centrality) for name, centrality in sorted_fog_nodes_by_centrality
        if name not in cfg_node_names
    ]

    sorted_remaining_fog_nodes_by_centrality_asc = sorted(remaining_fog_nodes_for_fg, key=lambda item: item[1])

    num_fg_nodes_target = max(1, int(NUM_FOG_NODES * PERCENT_FG_NODES)) if NUM_FOG_NODES > 0 else 0
    actual_num_fg_to_select = min(num_fg_nodes_target, len(sorted_remaining_fog_nodes_by_centrality_asc))
    fg_node_names_candidates = [name for name, _ in sorted_remaining_fog_nodes_by_centrality_asc[:actual_num_fg_to_select]]

    for fg_name in fg_node_names_candidates:
        if node_attrs_type.get(fg_name) != "CFG":
            node_attrs_type[fg_name] = "FG"

    # 8. Tugaskan graf NetworkX yang sudah lengkap ke YAFS topology
    yafs_topology_instance.G = final_graph_nx

    # 9. Set semua atribut node pada yafs_topology_instance.G
    nx.set_node_attributes(yafs_topology_instance.G, values=node_attrs_ram, name="RAM")
    nx.set_node_attributes(yafs_topology_instance.G, values=node_attrs_ipt, name="IPT")
    nx.set_node_attributes(yafs_topology_instance.G, values=node_attrs_sto, name="STO")
    nx.set_node_attributes(yafs_topology_instance.G, values=node_attrs_level, name="level")
    nx.set_node_attributes(yafs_topology_instance.G, values=node_attrs_type, name="type")
    nx.set_node_attributes(yafs_topology_instance.G, values=node_attrs_community, name="community_id")

    # 10. Set semua atribut edge pada yafs_topology_instance.G
    final_edge_attrs_bw = {}
    final_edge_attrs_pr = {}
    for (u, v), bw_val in edge_attrs_bw.items():
        final_edge_attrs_bw[(u, v)] = bw_val
        final_edge_attrs_bw[(v, u)] = bw_val
    for (u, v), pr_val in edge_attrs_pr.items():
        final_edge_attrs_pr[(u, v)] = pr_val
        final_edge_attrs_pr[(v, u)] = pr_val

    nx.set_edge_attributes(yafs_topology_instance.G, values=final_edge_attrs_bw, name="BW")
    nx.set_edge_attributes(yafs_topology_instance.G, values=final_edge_attrs_pr, name="PR")

    print_topology_summary(yafs_topology_instance)

    return yafs_topology_instance

def print_topology_summary(yafs_topology_instance):
    """Print a summary of the topology."""
    print(f"\nTopology Summary (YAFS example aligned, based on Table 3):")
    print(f"Total Fog Nodes: {len([n for n,d in yafs_topology_instance.G.nodes(data=True) if d.get('level')=='fog'])}")
    print(f"Total Cloud Nodes: {len([n for n,d in yafs_topology_instance.G.nodes(data=True) if d.get('level')=='cloud'])}")
    cfg_nodes_count = len([n for n,d in yafs_topology_instance.G.nodes(data=True) if d.get('type')=='CFG'])
    print(f"CFG Nodes: {cfg_nodes_count}")
    fg_nodes_count = len([n for n,d in yafs_topology_instance.G.nodes(data=True) if d.get('type')=='FG'])
    print(f"FG Nodes: {fg_nodes_count}")
    regular_fog_nodes_count = NUM_FOG_NODES - cfg_nodes_count - fg_nodes_count
    print(f"Regular Fog Nodes (type='fog_node'): {regular_fog_nodes_count}")
    print(f"Total Edges in YAFS topology: {yafs_topology_instance.G.number_of_edges()}")

    print("\nCommunity Assignment Verification (first 5 fog nodes):")
    for i in range(min(5, NUM_FOG_NODES)):
        node_name = f"f_{i}"
        if node_name in yafs_topology_instance.G:
            print(f"  Node {node_name}: Attributes {yafs_topology_instance.G.nodes[node_name]}")
        else:
            print(f"  Node {node_name} not found for verification.")
