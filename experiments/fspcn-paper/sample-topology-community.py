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

# --- Folder untuk menyimpan hasil ---
RESULTS_FOLDER = "results"
Path(RESULTS_FOLDER).mkdir(parents=True, exist_ok=True)


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
    print(f"DEBUG: Jumlah node dengan level 'fog': {len(current_fog_node_names)}") # VERIFIKASI 1

    # Buat subgraph HANYA dari fog nodes untuk kalkulasi sentralitas
    fog_only_subgraph = final_graph_nx.subgraph(current_fog_node_names).copy()
    print(f"DEBUG: Jumlah node di fog_only_subgraph: {fog_only_subgraph.number_of_nodes()}") # VERIFIKASI 2
    print(f"DEBUG: Jumlah edge di fog_only_subgraph: {fog_only_subgraph.number_of_edges()}") # VERIFIKASI 3

    if fog_only_subgraph.number_of_nodes() > 0 and fog_only_subgraph.number_of_edges() > 0:
        print("DEBUG: Menghitung betweenness centrality...")
        betweenness = nx.betweenness_centrality(fog_only_subgraph, normalized=True, endpoints=False)
        sorted_fog_nodes_by_centrality = sorted(betweenness.items(), key=lambda item: item[1], reverse=True)
    elif fog_only_subgraph.number_of_nodes() > 0:
        print("DEBUG: Warning: Fog graph has no edges. Selecting CFG nodes randomly.")
        temp_fog_node_names = list(current_fog_node_names)
        random.shuffle(temp_fog_node_names)
        sorted_fog_nodes_by_centrality = [(name, 0) for name in temp_fog_node_names]
    else:
        print("DEBUG: Warning: No fog nodes to select CFG from.")
        sorted_fog_nodes_by_centrality = []
    
    print(f"DEBUG: Jumlah node dalam sorted_fog_nodes_by_centrality: {len(sorted_fog_nodes_by_centrality)}") # VERIFIKASI 4

    num_cfg_nodes_target = max(1, int(NUM_FOG_NODES * PERCENT_CFG_NODES)) if NUM_FOG_NODES > 0 else 0
    print(f"DEBUG: Target jumlah CFG nodes: {num_cfg_nodes_target}") # VERIFIKASI 5
    
    # Pastikan tidak mengambil lebih banyak dari yang tersedia
    actual_num_cfg_to_select = min(num_cfg_nodes_target, len(sorted_fog_nodes_by_centrality))
    cfg_node_names = [name for name, _ in sorted_fog_nodes_by_centrality[:actual_num_cfg_to_select]]
    print(f"DEBUG: Jumlah CFG nodes yang akan di-assign: {len(cfg_node_names)}") # VERIFIKASI 6
    # print(f"DEBUG: Nama CFG nodes: {cfg_node_names[:5]}") # Tampilkan beberapa nama

    for cfg_name in cfg_node_names:
        node_attrs_type[cfg_name] = "CFG" # Ini menimpa 'fog_node'
        # ... (sisa kode CFG) ...

    # 7. Tentukan FG (Fog Gateway) nodes
    remaining_fog_nodes_for_fg = [
        (name, centrality) for name, centrality in sorted_fog_nodes_by_centrality
        if name not in cfg_node_names # Penting: gunakan list cfg_node_names yang sudah final
    ]
    print(f"DEBUG: Jumlah node tersisa untuk FG: {len(remaining_fog_nodes_for_fg)}") # VERIFIKASI 7

    sorted_remaining_fog_nodes_by_centrality_asc = sorted(remaining_fog_nodes_for_fg, key=lambda item: item[1])

    num_fg_nodes_target = max(1, int(NUM_FOG_NODES * PERCENT_FG_NODES)) if NUM_FOG_NODES > 0 else 0
    print(f"DEBUG: Target jumlah FG nodes: {num_fg_nodes_target}") # VERIFIKASI 8

    # Pastikan tidak mengambil lebih banyak dari yang tersedia di sisa node
    actual_num_fg_to_select = min(num_fg_nodes_target, len(sorted_remaining_fog_nodes_by_centrality_asc))
    fg_node_names_candidates = [name for name, _ in sorted_remaining_fog_nodes_by_centrality_asc[:actual_num_fg_to_select]]
    print(f"DEBUG: Jumlah FG nodes yang akan di-assign: {len(fg_node_names_candidates)}") # VERIFIKASI 9
    # print(f"DEBUG: Nama FG nodes: {fg_node_names_candidates[:5]}") # Tampilkan beberapa nama

    for fg_name in fg_node_names_candidates:
        if node_attrs_type.get(fg_name) != "CFG": # Pengaman, seharusnya tidak perlu jika logika benar
            node_attrs_type[fg_name] = "FG" # Ini menimpa 'fog_node'


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

def visualize_layered_topology(graph_to_draw, num_communities_param, title="Layered Topology with Communities", save_path=None):
    if graph_to_draw.number_of_nodes() == 0:
        print("Graph is empty, skipping drawing.")
        return

    print(f"\nAttempting to draw: {title}...")
    plt.figure(figsize=(22, 16)) # Ukuran figure lebih besar untuk mengakomodasi legenda
    pos = {}
    node_colors_list = []
    node_sizes = []
    node_labels = {node: node for node in graph_to_draw.nodes()} # Label default adalah nama node

    y_cloud = 4.0
    y_cfg = 3.5
    y_fog_main_upper = 3.0
    y_fog_main_lower = 0.5
    y_fg = 0.0

    if num_communities_param <= 0: # Penanganan jika tidak ada komunitas
        community_color_map = None
    elif num_communities_param <= 10:
        community_color_map = plt.cm.get_cmap('tab10', num_communities_param)
    elif num_communities_param <= 20:
        community_color_map = plt.cm.get_cmap('tab20', num_communities_param)
    else:
        community_color_map = plt.cm.get_cmap('nipy_spectral', num_communities_param) # nipy_spectral punya banyak variasi

    cloud_nodes = [n for n, d in graph_to_draw.nodes(data=True) if d.get('level') == 'cloud']
    # PENTING: CFG dan FG adalah node dengan 'type' spesifik, BUKAN hanya level.
    # Mereka juga memiliki level 'fog'.
    cfg_nodes = [n for n, d in graph_to_draw.nodes(data=True) if d.get('type') == 'CFG']
    fg_nodes = [n for n, d in graph_to_draw.nodes(data=True) if d.get('type') == 'FG']
    # Main fog nodes adalah yang level='fog' TAPI BUKAN CFG atau FG
    main_fog_nodes = [n for n, d in graph_to_draw.nodes(data=True)
                      if d.get('level') == 'fog' and n not in cfg_nodes and n not in fg_nodes]

    # Hitung lebar X yang dibutuhkan oleh lapisan fog utama untuk membantu penempatan CFG/FG
    # Ini adalah estimasi kasar, spring_layout yang akan menentukan sebaran sebenarnya
    estimated_main_fog_width = 0
    if main_fog_nodes:
        # Dummy spring layout untuk estimasi lebar
        temp_subgraph_main_fog = graph_to_draw.subgraph(main_fog_nodes)
        if temp_subgraph_main_fog.number_of_nodes() > 0:
            try:
                temp_pos_main_fog = nx.spring_layout(temp_subgraph_main_fog, seed=SEED, k=0.5) # k lebih kecil untuk lebih rapat
                if temp_pos_main_fog:
                    all_x = [p[0] for p in temp_pos_main_fog.values()]
                    estimated_main_fog_width = (max(all_x) - min(all_x)) if all_x else 0
            except Exception as e:
                print(f"Warning: Could not estimate main fog width: {e}")
                estimated_main_fog_width = len(main_fog_nodes) * 0.3 # Fallback kasar

    # Fungsi untuk mendistribusikan node pada sumbu X
    def distribute_nodes_x(nodes, y_level, x_spacing_factor=1.0, overall_width_hint=None):
        positions = {}
        if not nodes: return positions
        
        num_nodes = len(nodes)
        if num_nodes == 1: # Jika hanya satu node, letakkan di tengah (0)
            positions[nodes[0]] = (0, y_level)
            return positions

        # Gunakan hint lebar jika ada, atau default spacing
        if overall_width_hint and overall_width_hint > 0:
            # Distribusikan node dalam rentang overall_width_hint
            # x_spacing dihitung agar pas dalam overall_width_hint
            x_spacing = overall_width_hint / (num_nodes -1) if num_nodes > 1 else 0
        else:
            x_spacing = x_spacing_factor # Default jika tidak ada hint

        total_width = (num_nodes - 1) * x_spacing
        start_x = -total_width / 2 # Pusatkan di 0
        
        for i, node in enumerate(nodes):
            positions[node] = (start_x + i * x_spacing, y_level)
        return positions

    # Penempatan Cloud, CFG, FG
    pos.update(distribute_nodes_x(cloud_nodes, y_cloud, x_spacing_factor=2.0, overall_width_hint=max(estimated_main_fog_width * 0.8, 3.0)))
    pos.update(distribute_nodes_x(cfg_nodes, y_cfg, x_spacing_factor=1.2, overall_width_hint=max(estimated_main_fog_width * 0.9, 2.0)))
    pos.update(distribute_nodes_x(fg_nodes, y_fg, x_spacing_factor=1.0, overall_width_hint=max(estimated_main_fog_width * 0.9, 2.0)))


    # Penempatan Main Fog Nodes
    if main_fog_nodes:
        subgraph_main_fog = graph_to_draw.subgraph(main_fog_nodes)
        if subgraph_main_fog.number_of_nodes() > 0:
            # k_val disesuaikan agar tidak terlalu menyebar atau terlalu rapat
            k_val = 0.8 / ((len(subgraph_main_fog))**0.35) if len(subgraph_main_fog) > 1 else 0.8
            pos_main_fog_raw = nx.spring_layout(subgraph_main_fog, seed=SEED, k=k_val, iterations=80)
            
            # Normalisasi dan skala posisi X dan Y untuk main fog nodes
            all_raw_x = [p[0] for p in pos_main_fog_raw.values()]
            all_raw_y = [p[1] for p in pos_main_fog_raw.values()]
            min_x_raw, max_x_raw = (min(all_raw_x), max(all_raw_x)) if all_raw_x else (0,0)
            min_y_raw, max_y_raw = (min(all_raw_y), max(all_raw_y)) if all_raw_y else (0,0)
            span_x_raw = max_x_raw - min_x_raw if max_x_raw > min_x_raw else 1.0
            span_y_raw = max_y_raw - min_y_raw if max_y_raw > min_y_raw else 1.0
            
            # Lebar X yang diinginkan untuk main fog, coba buat sedikit lebih lebar dari CFG/FG
            # Ini agar fog layer terlihat sebagai 'badan' utama
            desired_x_width_fog = max(estimated_main_fog_width, (len(main_fog_nodes)-1)*0.3, 5.0)

            for node, (x_raw, y_raw) in pos_main_fog_raw.items():
                norm_x = ((x_raw - min_x_raw) / span_x_raw - 0.5) * desired_x_width_fog if span_x_raw > 0 else 0
                norm_y = y_fog_main_lower + ((y_raw - min_y_raw) / span_y_raw) * (y_fog_main_upper - y_fog_main_lower) if span_y_raw > 0 else (y_fog_main_lower+y_fog_main_upper)/2
                pos[node] = (norm_x, norm_y)
        elif main_fog_nodes: # Jika hanya satu main_fog_node
             pos[main_fog_nodes[0]] = (0, (y_fog_main_lower + y_fog_main_upper)/2)


    # Pewarnaan dan Ukuran Node
    default_fog_color = 'gainsboro' # Warna yang lebih netral untuk fog tanpa komunitas
    for node in graph_to_draw.nodes():
        if node not in pos: # Jaring pengaman
            pos[node] = (random.uniform(-3, 3), random.uniform(0.5, 3.5))
        
        node_data = graph_to_draw.nodes[node]
        node_type = node_data.get('type') # Ini yang paling penting untuk CFG/FG
        node_level = node_data.get('level')
        current_color = 'gray'
        current_size = 400

        if node_type == 'cloud_server': # Atau node_level == 'cloud'
            current_color = 'deepskyblue'
            current_size = 1200
        elif node_type == 'CFG': # CFG Nodes
            current_color = 'red'
            current_size = 800
        elif node_type == 'FG': # FG Nodes
            current_color = 'limegreen'
            current_size = 700
        elif node_level == 'fog': # Ini adalah main_fog_nodes (type='fog_node')
            community_id_str = node_data.get('community_id')
            if community_color_map and community_id_str and community_id_str != "CV_Undefined":
                try:
                    community_num = int(community_id_str.replace("CV", ""))
                    current_color = community_color_map((community_num - 1) % num_communities_param)
                except ValueError:
                    current_color = default_fog_color
            else:
                current_color = default_fog_color
            current_size = 500
        
        node_colors_list.append(current_color)
        node_sizes.append(current_size)

    nx.draw_networkx_nodes(graph_to_draw, pos, node_color=node_colors_list, node_size=node_sizes, alpha=0.9)
    nx.draw_networkx_edges(graph_to_draw, pos, alpha=0.3, edge_color="dimgray", width=0.7)
    nx.draw_networkx_labels(graph_to_draw, pos, labels=node_labels, font_size=6, font_weight='normal')

    plt.title(title, fontsize=20, fontweight='bold')
    plt.xticks([]); plt.yticks([])
    
    current_xlim = plt.xlim()
    current_ylim = plt.ylim()
    label_x_pos = current_xlim[0] - (current_xlim[1] - current_xlim[0]) * 0.03

    plt.axhline(y=(y_cloud + y_cfg) / 2 + 0.05, color='gray', linestyle=':', linewidth=0.9, xmin=0.05, xmax=0.95)
    plt.text(label_x_pos, y_cloud, 'Cloud Layer', ha='right', va='center', fontsize=12, color='dimgray', fontweight='bold')
    plt.axhline(y=(y_cfg + y_fog_main_upper) / 2 + 0.05, color='gray', linestyle=':', linewidth=0.9, xmin=0.05, xmax=0.95)
    plt.text(label_x_pos, y_cfg, 'CFG Layer', ha='right', va='center', fontsize=12, color='dimgray', fontweight='bold')
    plt.text(label_x_pos, (y_fog_main_lower + y_fog_main_upper)/2, 'Fog Node Layer', ha='right', va='center', fontsize=12, color='dimgray', fontweight='bold')
    plt.axhline(y=(y_fg + y_fog_main_lower) / 2 - 0.05, color='gray', linestyle=':', linewidth=0.9, xmin=0.05, xmax=0.95)
    plt.text(label_x_pos, y_fg, 'FG Layer', ha='right', va='center', fontsize=12, color='dimgray', fontweight='bold')

    # Legenda Kustom (Menampilkan semua komunitas)
    legend_elements = [
        plt.Line2D([0], [0], marker='o', color='w', label='Cloud Server', markersize=10, markerfacecolor='deepskyblue'),
        plt.Line2D([0], [0], marker='o', color='w', label='CFG Node', markersize=10, markerfacecolor='red'),
        plt.Line2D([0], [0], marker='o', color='w', label='FG Node', markersize=10, markerfacecolor='limegreen'),
    ]
    if community_color_map and num_communities_param > 0:
        for i in range(num_communities_param): # Loop untuk semua komunitas
            community_num_for_legend = i + 1
            color = community_color_map(i % num_communities_param)
            legend_elements.append(
                plt.Line2D([0], [0], marker='o', color='w', label=f'Community CV{community_num_for_legend}',
                           markersize=10, markerfacecolor=color)
            )
    else: # Jika tidak ada komunitas atau map tidak terdefinisi
        legend_elements.append(
             plt.Line2D([0], [0], marker='o', color='w', label='Fog Node', markersize=10, markerfacecolor=default_fog_color)
        )


    # Atur posisi legenda agar tidak tumpang tindih dengan plot
    # Mungkin perlu beberapa kolom jika legenda sangat panjang
    ncol_legend = 1
    if num_communities_param > 5: ncol_legend = 2 # Coba 2 kolom jika komunitas > 5
    if num_communities_param > 12: ncol_legend = 3 # Coba 3 kolom jika komunitas > 12

    plt.legend(handles=legend_elements, loc='center left', bbox_to_anchor=(1.01, 0.5),
               fontsize=9, title="Legend", title_fontsize='11', ncol=ncol_legend)

    plt.box(False)
    # rect [left, bottom, right, top]
    plt.tight_layout(rect=[0.05, 0.05, 0.82 if ncol_legend > 1 else 0.85, 0.95]) # Sesuaikan right berdasarkan ncol_legend
    
    if save_path:
        plt.savefig(save_path, dpi=200, bbox_inches='tight') # bbox_inches='tight' untuk memastikan legenda masuk
        print(f"Plot saved to {save_path}")
    else:
        plt.show()
    plt.close()

def export_graph_data(graph_nx, base_filename="topology_export", export_folder="."):
    """
    Mengekspor data graf NetworkX ke format GEXF dan CSV.

    :param graph_nx: Objek graf NetworkX yang akan diekspor.
    :param base_filename: Nama dasar untuk file output (tanpa ekstensi).
    :param export_folder: Folder tempat menyimpan file output.
    """
    Path(export_folder).mkdir(parents=True, exist_ok=True)
    print(f"\nExporting graph data to folder: {Path(export_folder).resolve()}")

    # --- 1. Ekspor ke GEXF ---
    # GEXF sangat baik untuk menyimpan atribut node dan edge, cocok untuk Gephi.
    # NetworkX secara otomatis akan mencoba menyertakan semua atribut node dan edge.
    # Pastikan atribut memiliki tipe data yang didukung GEXF (string, integer, float, boolean).
    # Jika ada list atau dictionary sebagai atribut, mungkin perlu diproses dulu atau akan diabaikan.

    gexf_path = Path(export_folder) / f"{base_filename}.gexf"
    try:
        # NetworkX mungkin mengeluarkan warning jika ada tipe data atribut yang tidak ideal untuk GEXF,
        # tapi biasanya tetap berhasil mengekspor yang kompatibel.
        # Untuk GEXF versi 1.2 (default), NetworkX menangani konversi tipe dasar.
        nx.write_gexf(graph_nx, gexf_path, version="1.2draft")
        print(f"  Graf berhasil diekspor ke: {gexf_path}")
    except Exception as e:
        print(f"  Error saat mengekspor ke GEXF: {e}")
        print("    Pastikan semua atribut node/edge memiliki tipe data sederhana (string, int, float, bool).")
        print("    Atribut list/dict mungkin perlu di-flatten atau di-stringifikasi.")


    # --- 2. Ekspor ke CSV (Node List dan Edge List) ---
    # CSV lebih tabular, jadi kita akan membuat dua file: satu untuk node dan satu untuk edge.

    # A. Node List CSV
    nodes_data = []
    for node, attrs in graph_nx.nodes(data=True):
        node_info = {'node_id': node}
        node_info.update(attrs) # Tambahkan semua atribut node
        nodes_data.append(node_info)
    
    nodes_df = pd.DataFrame(nodes_data)
    # Reorder kolom agar 'node_id' di depan, jika ada kolom lain bisa diatur urutannya
    if 'node_id' in nodes_df.columns:
        cols = ['node_id'] + [col for col in nodes_df.columns if col != 'node_id']
        nodes_df = nodes_df[cols]

    nodes_csv_path = Path(export_folder) / f"{base_filename}_nodes.csv"
    try:
        nodes_df.to_csv(nodes_csv_path, index=False)
        print(f"  Node list berhasil diekspor ke: {nodes_csv_path}")
    except Exception as e:
        print(f"  Error saat mengekspor node list ke CSV: {e}")

    # B. Edge List CSV
    edges_data = []
    for u, v, attrs in graph_nx.edges(data=True):
        edge_info = {'source': u, 'target': v}
        edge_info.update(attrs) # Tambahkan semua atribut edge
        edges_data.append(edge_info)

    edges_df = pd.DataFrame(edges_data)
    # Reorder kolom agar 'source' dan 'target' di depan
    if 'source' in edges_df.columns and 'target' in edges_df.columns:
        cols = ['source', 'target'] + [col for col in edges_df.columns if col not in ['source', 'target']]
        edges_df = edges_df[cols]
    
    edges_csv_path = Path(export_folder) / f"{base_filename}_edges.csv"
    try:
        edges_df.to_csv(edges_csv_path, index=False)
        print(f"  Edge list berhasil diekspor ke: {edges_csv_path}")
    except Exception as e:
        print(f"  Error saat mengekspor edge list ke CSV: {e}")

# --- Contoh Penggunaan ---
if __name__ == "__main__":
    random.seed(SEED)
    np.random.seed(SEED)

    MAIN_OUTPUT_FOLDER = "topology_outputs"
    Path(MAIN_OUTPUT_FOLDER).mkdir(parents=True, exist_ok=True)

    topology_instance = create_topology()
    graph = topology_instance.G

    export_subfolder = Path(MAIN_OUTPUT_FOLDER) / "graph_exports"
    base_export_filename = f"fspcn_topo_N{NUM_FOG_NODES}_C{NUM_COMMUNITIES}"

    # Panggil fungsi ekspor
    export_graph_data(graph, 
                      base_filename=base_export_filename, 
                      export_folder=export_subfolder)

    output_image_path = Path(RESULTS_FOLDER) / f"topology_fspcn_layers_N{NUM_FOG_NODES}_C{NUM_COMMUNITIES}.png"
    visualize_layered_topology(graph,
                               num_communities_param=NUM_COMMUNITIES,
                               title=f"Layered FSPCN Topology ({NUM_FOG_NODES} Fog Nodes, {NUM_COMMUNITIES} Communities)",
                               save_path=output_image_path)
    
    print(f"\nVisualisasi selesai. Cek file di: {output_image_path.resolve()}")