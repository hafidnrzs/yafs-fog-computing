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
from yafs.path_routing import DeviceSpeedAwareRouting

# Seed untuk reproducibility
SEED = 42

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

# Parameter Lain (Tidak dari Table 3 untuk fog environment, bisa disesuaikan)
NUM_CLOUD_NODES = 3
BARABASI_M = 2

# Atribut default untuk Cloud Nodes (sumber daya besar)
DEFAULT_CLOUD_RAM_MB = 200000 # Jauh lebih besar dari fog
DEFAULT_CLOUD_IPT_INSTR_MS = 100000
DEFAULT_CLOUD_STO_TB = 200

# Atribut untuk link CFG ke Cloud (biasanya lebih baik dari link fog-fog)
CFG_CLOUD_LINK_BW_BPS = MAX_LINK_BW_BPS * 2 # Misal 2x BW maks fog link
CFG_CLOUD_LINK_PD_MS = MIN_LINK_PD_MS # Misal delay minimum

def create_topology():
    """
    Membuat topologi YAFS berdasarkan parameter dari paper.
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

    # Ganti nama node di fog_graph_nx agar menjadi string "fog_i" agar konsisten dengan penamaan node
    node_mapping = {i: f"fog_{i}" for i in range(NUM_FOG_NODES)}
    final_graph_nx = nx.relabel_nodes(fog_graph_nx, node_mapping, copy=True)

    # 3. Siapkan atribut untuk fog nodes
    node_attrs_ram = {}
    node_attrs_ipt = {}
    node_attrs_sto = {}
    node_attrs_level = {}
    node_attrs_type = {}

    fog_node_names = [f"fog_{i}" for i in range(NUM_FOG_NODES)]
    for node_name in fog_node_names:
        node_attrs_ram[node_name] = random.randint(MIN_FOG_RAM_MB, MAX_FOG_RAM_MB)
        node_attrs_ipt[node_name] = random.randint(MIN_FOG_IPT_INSTR_MS, MAX_FOG_IPT_INSTR_MS)
        node_attrs_sto[node_name] = random.uniform(MIN_FOG_TB_TERABYTE, MAX_FOG_TB_TERABYTE)
        node_attrs_level[node_name] = "fog"
        node_attrs_type[node_name] = "fog_node"

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
    
    # 6. Tentukan CFG (Cloud-Fog Gateway) nodes
    fog_subgraph = final_graph_nx.subgraph(fog_node_names).copy()

    if fog_subgraph.number_of_edges() > 0:
        betweenness = nx.betweenness_centrality(fog_subgraph, normalized=True, endpoints=False)
        sorted_fog_nodes_by_centrality = sorted(betweenness.items(), key=lambda item: item[1], reverse=True)
    else:
        print("Warning: Fog graph has no edges. Selecting CFG nodes randomly.")
        temp_fog_node_names = list(fog_node_names)
        random.shuffle(temp_fog_node_names)
        sorted_fog_nodes_by_centrality = [(name, 0) for name in temp_fog_node_names]
    
    num_cfg_nodes = max(1, int(NUM_FOG_NODES * PERCENT_CFG_NODES))
    cfg_node_names = [name for name, _ in sorted_fog_nodes_by_centrality[:num_cfg_nodes]]

    for cfg_name in cfg_node_names:
        node_attrs_type[cfg_name] = "CFG"
        if cloud_node_names:
             # Hubungkan CFG ke cloud secara acak
            cloud_to_connect = random.choice(cloud_node_names)
            final_graph_nx.add_edge(cfg_name, cloud_to_connect)

            # Atur atribut untuk edge CFG ke cloud
            edge_attrs_bw[(cfg_name, cloud_to_connect)] = CFG_CLOUD_LINK_BW_BPS
            edge_attrs_pr[(cfg_name, cloud_to_connect)] = CFG_CLOUD_LINK_PD_MS

    # 7. Tentukan FG (Fog Gateway) nodes
    remaining_fog_nodes_for_fg = [
        (name, centrality) for name, centrality in sorted_fog_nodes_by_centrality
        if name not in cfg_node_names
    ]
    sorted_remaining_fog_nodes_by_centrality_asc = sorted(remaining_fog_nodes_for_fg, key=lambda item: item[1])
    num_fg_nodes = max(1, int(NUM_FOG_NODES * PERCENT_FG_NODES))
    fg_node_names_candidates = [name for name, _ in sorted_remaining_fog_nodes_by_centrality_asc[:num_fg_nodes]]

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

    # 10. Set semua atribut edge pada yafs_topology_instance.G
    nx.set_edge_attributes(yafs_topology_instance.G, values=edge_attrs_bw, name="BW")
    nx.set_edge_attributes(yafs_topology_instance.G, values=edge_attrs_pr, name="PR")


    print(f"\nTopology Summary (YAFS example aligned, based on Table 3):")
    # Akses melalui yafs_topology_instance.G
    print(f"Total Fog Nodes: {len([n for n,d in yafs_topology_instance.G.nodes(data=True) if d.get('level')=='fog'])}")
    print(f"Total Cloud Nodes: {len([n for n,d in yafs_topology_instance.G.nodes(data=True) if d.get('level')=='cloud'])}")
    print(f"CFG Nodes: {len([n for n,d in yafs_topology_instance.G.nodes(data=True) if d.get('type')=='CFG'])}")
    print(f"FG Nodes: {len([n for n,d in yafs_topology_instance.G.nodes(data=True) if d.get('type')=='FG'])}")
    print(f"Total Edges in YAFS topology: {len(yafs_topology_instance.G.edges())}")

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

    start_time = time.time()
    t = create_topology()
    print(f"\n--- {time.time() - start_time} ---")
    print("Simulation Done!")

    # Simpan topology ke file GEXF untuk visualisasi
    nx.write_gexf(t.G,folder_results + f"graph_barabasi_albert_{BARABASI_M}.gexf")

    # Visualisasikan topologi yang sudah dibuat
    visualize_layered_topology(t.G, title="Topology Visualization", save_path=folder_results)
