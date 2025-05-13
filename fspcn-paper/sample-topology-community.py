import os
import time
import random
from pathlib import Path

import networkx as nx
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

from yafs.core import Sim
from yafs.topology import Topology
# from yafs.path_routing import DeviceSpeedAwareRouting

# Seed untuk reproducibility
SEED = 42
random.seed(SEED)
np.random.seed(SEED)

# --- Parameter Konfigurasi Topologi Berdasarkan Table 3 ---
# Node
NUM_FOG_NODES = 100
MIN_FOG_RAM_MB = 10
MAX_FOG_RAM_MB = 25
MIN_FOG_IPT_INSTR_MS = 100
MAX_FOG_IPT_INSTR_MS = 1000
MIN_FOG_TB_TERABYTE = 0.2
MAX_FOG_TB_TERABYTE = 100

# Link
MIN_LINK_BW_BPS = 6 * 10**6  # 6 Mbps
MAX_LINK_BW_BPS = 6 * 10**7  # 60 Mbps
MIN_LINK_PD_MS = 3
MAX_LINK_PD_MS = 5

# Gateways
PERCENT_CFG_NODES = 0.05 # 5%
PERCENT_FG_NODES = 0.25  # 25%

# --- Parameter Komunitas dari Table 2 ---
NUM_COMMUNITIES = 10

# Parameter Lain (Tidak dari Table 3 untuk fog environment, bisa disesuaikan)
NUM_CLOUD_NODES = 3
BARABASI_M = 2 # Untuk Barabasi-Albert graph

# Atribut default untuk Cloud Nodes (sumber daya besar)
DEFAULT_CLOUD_RAM_MB = 200000 # Jauh lebih besar dari fog
DEFAULT_CLOUD_IPT_INSTR_MS = 100000
DEFAULT_CLOUD_STO_TB = 200

# Atribut untuk link CFG ke Cloud (biasanya lebih baik dari link fog-fog)
CFG_CLOUD_LINK_BW_BPS = MAX_LINK_BW_BPS * 2 # Misal 2x BW maks fog link
CFG_CLOUD_LINK_PD_MS = MIN_LINK_PD_MS # Misal delay minimum

def generate_mock_chromosome(num_nodes, num_communities):
    """
    Menghasilkan kromosom mock yang memetakan node ke ID komunitas.
    ID Komunitas akan berupa integer dari 1 hingga num_communities.
    """
    print(f"Generating mock chromosome for {num_nodes} nodes into {num_communities} communities...")
    chromosome = [0] * num_nodes
    if num_communities == 0: # Hindari ZeroDivisionError
        print("Warning: NUM_COMMUNITIES is 0. All nodes will be in community 0 (undefined).")
        return chromosome

    nodes_per_community_ideal = num_nodes // num_communities

    for i in range(num_nodes):
        # ID Komunitas dari 1 hingga num_communities
        community_id_int = (i // nodes_per_community_ideal) + 1
        # Pastikan tidak melebihi num_communities (penting jika num_nodes tidak habis dibagi num_communities)
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
        # Kromosom diindeks dari 0, node_name "f_0" sesuai dengan chromosome[0]
        if i < len(mock_chromosome): # Pastikan index tidak keluar batas
            community_id_int = mock_chromosome[i]
            node_attrs_community[node_name] = f"CV{community_id_int}" # Simpan sebagai string "CV1", "CV2", dst.
        else:
            # Fallback jika ada ketidaksesuaian (seharusnya tidak terjadi dengan logika saat ini)
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
    # Hanya pertimbangkan fog nodes untuk seleksi CFG
    current_fog_node_names = [name for name, data in final_graph_nx.nodes(data=True) if data.get('level') == 'fog']
    
    # Buat subgraph HANYA dari fog nodes untuk kalkulasi sentralitas
    # Ini penting agar sentralitas hanya berdasarkan konektivitas antar fog.
    fog_only_subgraph = final_graph_nx.subgraph(current_fog_node_names).copy()

    if fog_only_subgraph.number_of_nodes() > 0 and fog_only_subgraph.number_of_edges() > 0:
        # Gunakan k_shortest_paths=None untuk versi NetworkX > 2.4 jika tidak ingin menghitung semua path
        # Untuk betweenness centrality, tidak ada parameter k_shortest_paths
        betweenness = nx.betweenness_centrality(fog_only_subgraph, normalized=True, endpoints=False)
        sorted_fog_nodes_by_centrality = sorted(betweenness.items(), key=lambda item: item[1], reverse=True)
    elif fog_only_subgraph.number_of_nodes() > 0:
        print("Warning: Fog graph has no edges. Selecting CFG nodes randomly from available fog nodes.")
        # Jika tidak ada edge, semua node memiliki sentralitas 0. Pilih secara acak.
        temp_fog_node_names = list(current_fog_node_names)
        random.shuffle(temp_fog_node_names)
        sorted_fog_nodes_by_centrality = [(name, 0) for name in temp_fog_node_names]
    else:
        print("Warning: No fog nodes to select CFG from.")
        sorted_fog_nodes_by_centrality = []


    num_cfg_nodes = max(1, int(NUM_FOG_NODES * PERCENT_CFG_NODES)) if NUM_FOG_NODES > 0 else 0
    cfg_node_names = [name for name, _ in sorted_fog_nodes_by_centrality[:num_cfg_nodes]]

    for cfg_name in cfg_node_names:
        node_attrs_type[cfg_name] = "CFG"
        if cloud_node_names:
            cloud_to_connect = random.choice(cloud_node_names)
            final_graph_nx.add_edge(cfg_name, cloud_to_connect)
            edge_attrs_bw[(cfg_name, cloud_to_connect)] = CFG_CLOUD_LINK_BW_BPS
            edge_attrs_pr[(cfg_name, cloud_to_connect)] = CFG_CLOUD_LINK_PD_MS
            # Pastikan link dua arah jika YAFS mengasumsikannya atau routing membutuhkannya
            edge_attrs_bw[(cloud_to_connect, cfg_name)] = CFG_CLOUD_LINK_BW_BPS
            edge_attrs_pr[(cloud_to_connect, cfg_name)] = CFG_CLOUD_LINK_PD_MS


    # 7. Tentukan FG (Fog Gateway) nodes
    # FG dipilih dari node yang BUKAN CFG, berdasarkan sentralitas TERENDAH
    remaining_fog_nodes_for_fg = [
        (name, centrality) for name, centrality in sorted_fog_nodes_by_centrality
        if name not in cfg_node_names
    ]
    # Urutkan sisa node berdasarkan sentralitas menaik (ascending)
    sorted_remaining_fog_nodes_by_centrality_asc = sorted(remaining_fog_nodes_for_fg, key=lambda item: item[1])

    num_fg_nodes = max(1, int(NUM_FOG_NODES * PERCENT_FG_NODES)) if NUM_FOG_NODES > 0 else 0
    fg_node_names_candidates = [name for name, _ in sorted_remaining_fog_nodes_by_centrality_asc[:num_fg_nodes]]

    for fg_name in fg_node_names_candidates:
        # Pastikan kita tidak menimpa CFG jika ada overlap (seharusnya tidak dengan logika di atas)
        if node_attrs_type.get(fg_name) != "CFG":
            node_attrs_type[fg_name] = "FG" # Timpa tipe default 'fog_node'


    # 8. Tugaskan graf NetworkX yang sudah lengkap ke YAFS topology
    yafs_topology_instance.G = final_graph_nx

    # 9. Set semua atribut node pada yafs_topology_instance.G
    nx.set_node_attributes(yafs_topology_instance.G, values=node_attrs_ram, name="RAM")
    nx.set_node_attributes(yafs_topology_instance.G, values=node_attrs_ipt, name="IPT")
    nx.set_node_attributes(yafs_topology_instance.G, values=node_attrs_sto, name="STO")
    nx.set_node_attributes(yafs_topology_instance.G, values=node_attrs_level, name="level")
    nx.set_node_attributes(yafs_topology_instance.G, values=node_attrs_type, name="type")
    nx.set_node_attributes(yafs_topology_instance.G, values=node_attrs_community, name="community_id") # SET ATRIBUT KOMUNITAS

    # 10. Set semua atribut edge pada yafs_topology_instance.G
    # Perlu memastikan edge dua arah memiliki atribut jika diperlukan oleh YAFS
    # Untuk Barabasi-Albert, edge tidak terarah, jadi (u,v) dan (v,u) adalah sama.
    # Namun, YAFS mungkin memperlakukannya sebagai terarah untuk BW/PR, jadi kita set keduanya.
    final_edge_attrs_bw = {}
    final_edge_attrs_pr = {}
    for (u,v), bw_val in edge_attrs_bw.items():
        final_edge_attrs_bw[(u,v)] = bw_val
        final_edge_attrs_bw[(v,u)] = bw_val # Asumsikan simetris untuk link fog-fog dan cfg-cloud
    for (u,v), pr_val in edge_attrs_pr.items():
        final_edge_attrs_pr[(u,v)] = pr_val
        final_edge_attrs_pr[(v,u)] = pr_val

    nx.set_edge_attributes(yafs_topology_instance.G, values=final_edge_attrs_bw, name="BW")
    nx.set_edge_attributes(yafs_topology_instance.G, values=final_edge_attrs_pr, name="PR")


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

    # Verifikasi atribut komunitas untuk beberapa node
    print("\nCommunity Assignment Verification (first 5 fog nodes):")
    for i in range(min(5, NUM_FOG_NODES)):
        node_name = f"f_{i}"
        if node_name in yafs_topology_instance.G:
            print(f"  Node {node_name}: Attributes {yafs_topology_instance.G.nodes[node_name]}")
        else:
            # Ini seharusnya tidak terjadi jika NUM_FOG_NODES > 0
            print(f"  Node {node_name} not found for verification.")


    return yafs_topology_instance

# def main(stop_time, folder_results):
    #
    # TOPOLOGY 
    #

    #
    # APPLICATION or SERVICES
    #

    #
    # SERVICE PLACEMENT
    #
    # selector = DeviceSpeedAwareRouting()

    #
    # SIMULATION ENGINE
    #
    # s = Sim(t, default_results_path=folder_result+"sim_trace")

    # Deploy services
    # s.deploy_app(app, placement, selector)

def visualize_layered_topology(graph_to_draw, title="Layered Topology", save_path=None):
    """
    Memvisualisasikan graf NetworkX dengan layout berlapis.
    :param graph_to_draw: Objek graf NetworkX yang akan divisualisasikan.
    :param title: Judul untuk plot.
    :param save_path: Path untuk menyimpan gambar hasil visualisasi.
    """
    if graph_to_draw.number_of_nodes() == 0:
        print("Graph is empty, skipping drawing.")
        return

    print(f"\nAttempting to draw: {title}...")
    plt.figure(figsize=(18, 12)) # Ukuran figure bisa disesuaikan
    pos = {}
    node_colors = []
    node_sizes = []
    node_labels = {}

    # Definisikan level Y untuk setiap lapisan
    y_cloud = 4.0
    y_cfg = 3.5
    y_fog_main_upper = 3 # Batas atas untuk fog nodes biasa (sedikit dinaikkan)
    y_fog_main_lower = 0.5 # Batas bawah untuk fog nodes biasa (sedikit diturunkan)
    y_fg = 0.0

    # Kelompokkan node berdasarkan tipe/level
    cloud_nodes = [n for n, d in graph_to_draw.nodes(data=True) if d.get('level') == 'cloud']
    cfg_nodes = [n for n, d in graph_to_draw.nodes(data=True) if d.get('type') == 'CFG']
    fg_nodes = [n for n, d in graph_to_draw.nodes(data=True) if d.get('type') == 'FG']
    main_fog_nodes = [n for n, d in graph_to_draw.nodes(data=True)
                      if d.get('level') == 'fog' and n not in cfg_nodes and n not in fg_nodes]

    def distribute_nodes_x(nodes, y_level, x_spacing=1.0, x_center_offset=0.0):
        positions = {}
        if not nodes: return positions
        # Hitung total lebar yang dibutuhkan dan geser agar terpusat
        total_width = (len(nodes) - 1) * x_spacing
        start_x = x_center_offset - total_width / 2
        for i, node in enumerate(nodes):
            positions[node] = (start_x + i * x_spacing, y_level)
        return positions

    pos.update(distribute_nodes_x(cloud_nodes, y_cloud, x_spacing=2.0))
    pos.update(distribute_nodes_x(cfg_nodes, y_cfg, x_spacing=1.2))
    pos.update(distribute_nodes_x(fg_nodes, y_fg, x_spacing=1.0))

    if main_fog_nodes:
        subgraph_main_fog = graph_to_draw.subgraph(main_fog_nodes)
        if subgraph_main_fog.number_of_nodes() > 0:
            # Coba k yang lebih besar untuk penyebaran lebih luas, atau lebih kecil untuk lebih rapat
            k_val = 0.8 / ((len(subgraph_main_fog))**0.4) if len(subgraph_main_fog) > 1 else 0.8
            pos_main_fog_raw = nx.spring_layout(subgraph_main_fog, seed=42, k=k_val, iterations=60)
            
            min_x = min(p[0] for p in pos_main_fog_raw.values()) if pos_main_fog_raw else 0
            max_x = max(p[0] for p in pos_main_fog_raw.values()) if pos_main_fog_raw else 0
            min_y = min(p[1] for p in pos_main_fog_raw.values()) if pos_main_fog_raw else 0
            max_y = max(p[1] for p in pos_main_fog_raw.values()) if pos_main_fog_raw else 0

            span_x = max_x - min_x if max_x > min_x else 1.0
            span_y = max_y - min_y if max_y > min_y else 1.0
            
            # Lebar X yang diinginkan untuk lapisan fog utama, coba buat lebih lebar
            desired_x_width_fog = max((len(cfg_nodes)-1)*1.2, (len(fg_nodes)-1)*1.0, (len(main_fog_nodes)-1)*0.4, 5.0)


            for node, (x, y) in pos_main_fog_raw.items():
                norm_x = ((x - min_x) / span_x - 0.5) * desired_x_width_fog if span_x > 0 else 0
                norm_y = y_fog_main_lower + ((y - min_y) / span_y) * (y_fog_main_upper - y_fog_main_lower) if span_y > 0 else (y_fog_main_lower+y_fog_main_upper)/2
                pos[node] = (norm_x, norm_y)
        else: # Jika hanya satu main_fog_node
            for node in main_fog_nodes:
                pos[node] = (0, (y_fog_main_lower + y_fog_main_upper)/2)

    for node in graph_to_draw.nodes():
        if node not in pos: # Jaring pengaman jika ada node terlewat
            pos[node] = (random.uniform(-3, 3), random.uniform(0.5, 3.5))
        
        node_data = graph_to_draw.nodes[node]
        node_labels[node] = node # Hanya nama node
        
        node_type = node_data.get('type')
        if node_type == 'cloud_server': node_colors.append('deepskyblue'); node_sizes.append(1200)
        elif node_type == 'CFG': node_colors.append('red'); node_sizes.append(700)
        elif node_type == 'FG': node_colors.append('limegreen'); node_sizes.append(600)
        else: node_colors.append('silver'); node_sizes.append(400) # Warna lebih terang untuk fog

    nx.draw_networkx_nodes(graph_to_draw, pos, node_color=node_colors, node_size=node_sizes, alpha=0.9)
    nx.draw_networkx_edges(graph_to_draw, pos, alpha=0.4, edge_color="dimgray", width=0.8)
    nx.draw_networkx_labels(graph_to_draw, pos, labels=node_labels, font_size=6, font_weight='bold')

    plt.title(title, fontsize=18)
    plt.xticks([])
    plt.yticks([])
    # Menambahkan garis pemisah antar layer (opsional)
    plt.axhline(y=(y_cloud + y_cfg) / 2, color='gray', linestyle='--', linewidth=0.7)
    plt.axhline(y=(y_cfg + y_fog_main_upper) / 2, color='gray', linestyle='--', linewidth=0.7)
    plt.axhline(y=(y_fg + y_fog_main_lower) / 2, color='gray', linestyle='--', linewidth=0.7)
    
    # Menambahkan label layer (opsional)
    plt.text(plt.xlim()[0] - 0.5, y_cloud, 'Cloud Layer', ha='right', va='center', fontsize=10, color='gray')
    plt.text(plt.xlim()[0] - 0.5, (y_cfg + y_fog_main_upper)/2 , 'Upper Fog (CFG)', ha='right', va='center', fontsize=10, color='gray')
    plt.text(plt.xlim()[0] - 0.5, (y_fog_main_lower + y_fog_main_upper)/2, 'Fog Layer', ha='right', va='center', fontsize=10, color='gray')
    plt.text(plt.xlim()[0] - 0.5, y_fg, 'Edge Fog (FG)', ha='right', va='center', fontsize=10, color='gray')

    plt.box(False) # Menghilangkan box di sekitar plot
    plt.tight_layout(pad=1.0) # Tambahkan padding
    plt.savefig(folder_results+"topology_visualization.png") # Simpan sebagai file PNG
    print(f"Plot saved to {save_path}/topology_visualization.png")


if __name__ == "__main__":
    folder_results = Path("./results/")
    folder_results.mkdir(parents=True, exist_ok=True)
    folder_results = str(folder_results) + "/"

    # Pastikan SEED di-set di awal untuk random di dalam fungsi juga
    random.seed(SEED)
    np.random.seed(SEED)

    start_time = time.time()
    topology = create_topology()

    # Anda sekarang bisa mengakses atribut komunitas dari graf:
    # Misalnya, untuk node "f_0":
    if "f_0" in topology.G:
        print(f"\nNode f_0 community: {topology.G.nodes['f_0'].get('community_id')}")
        print(f"Node fog_0 type: {topology.G.nodes['f_0'].get('type')}")

    if NUM_FOG_NODES > 10 and "f_10" in topology.G:
        print(f"Node f_10 community: {topology.G.nodes['f_10'].get('community_id')}")

    # Mengambil semua node dalam komunitas tertentu
    target_community_str = "CV1"
    nodes_in_cv1 = [
        node for node, data in topology.G.nodes(data=True)
        if data.get('level') == 'fog' and data.get('community_id') == target_community_str
    ]
    print(f"\nNodes in {target_community_str}: {nodes_in_cv1}")
    if nodes_in_cv1:
         print(f"First node in CV1 ({nodes_in_cv1[0]}) attributes: {topology.G.nodes[nodes_in_cv1[0]]}")

    # Simpan topology ke file GEXF untuk visualisasi
    # nx.write_gexf(topology.G, folder_results + f"graph_barabasi_albert_{BARABASI_M}.gexf")

    # Visualisasikan topologi yang sudah dibuat
    # visualize_layered_topology(topology.G, title="Topology Visualization", save_path=folder_results)

    print(f"\n--- {time.time() - start_time} ---")
    print("Simulation Done!")
    
    # Visualisasi sederhana (opsional, bisa memakan waktu untuk graf besar)
    plt.figure(figsize=(12, 12))
    pos = nx.spring_layout(topology.G, seed=SEED)
    node_colors = []
    for node in topology.G.nodes():
        node_data = topology.G.nodes[node]
        if node_data.get('type') == 'CFG':
            node_colors.append('red')
        elif node_data.get('type') == 'FG':
            node_colors.append('orange')
        elif node_data.get('level') == 'cloud':
            node_colors.append('skyblue')
        elif node_data.get('level') == 'fog':
            # Warnai fog node berdasarkan komunitasnya jika ada
            community_id_str = node_data.get('community_id')
            if community_id_str:
                try:
                    community_num = int(community_id_str.replace("CV", ""))
                    # Simple color map based on community number
                    # This will repeat colors if NUM_COMMUNITIES > number of distinct colors
                    color_map = plt.cm.get_cmap('tab10', NUM_COMMUNITIES)
                    node_colors.append(color_map(community_num -1))
                except ValueError:
                    node_colors.append('lightgray') # Default for unparsed community
            else:
                node_colors.append('lightgreen') # Regular fog node
        else:
            node_colors.append('gray')

    nx.draw(topology.G, pos, with_labels=True, node_color=node_colors, node_size=500, font_size=8)
    plt.title("Generated Topology with Node Types and Communities")
    # plt.show()
    plt.savefig(folder_results+"topology_community_visualization.png")
    print(f"Plot saved to {folder_results}/topology_community_visualization.png")