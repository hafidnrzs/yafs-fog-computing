import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.animation import FuncAnimation
from pathlib import Path
from Simulation.config import *
from Simulation.Topology.topology import *
from Simulation.Topology.topologyGA import *
import random

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

def visualize_topology_ga_with_communities(graph_to_draw, title="Topology GA with Communities", save_path=None):
    """
    Memvisualisasikan topologi GA dengan warna komunitas pada node fog.
    :param graph_to_draw: Objek graf NetworkX yang akan divisualisasikan.
    :param title: Judul untuk plot.
    :param save_path: Path untuk menyimpan gambar hasil visualisasi.
    """
    if graph_to_draw.number_of_nodes() == 0:
        print("Graph is empty, skipping drawing.")
        return

    print(f"\nAttempting to draw: {title}...")
    plt.figure(figsize=(18, 12))  # Ukuran figure bisa disesuaikan
    pos = {}
    node_colors = []
    node_sizes = []
    node_labels = {}

    # Definisikan level Y untuk setiap lapisan
    y_cloud = 4.0
    y_cfg = 3.5
    y_fog_main_upper = 3  # Batas atas untuk fog nodes biasa
    y_fog_main_lower = 0.5  # Batas bawah untuk fog nodes biasa
    y_fg = 0.0

    # Kelompokkan node berdasarkan tipe/level
    cloud_nodes = [n for n, d in graph_to_draw.nodes(data=True) if d.get('level') == 'cloud']
    cfg_nodes = [n for n, d in graph_to_draw.nodes(data=True) if d.get('type') == 'CFG']
    fg_nodes = [n for n, d in graph_to_draw.nodes(data=True) if d.get('type') == 'FG']
    main_fog_nodes = [n for n, d in graph_to_draw.nodes(data=True)
                      if d.get('level') == 'fog' and n not in cfg_nodes and n not in fg_nodes]

    def distribute_nodes_x(nodes, y_level, x_spacing=1.0, x_center_offset=0.0):
        positions = {}
        if not nodes:
            return positions
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
            k_val = 0.8 / ((len(subgraph_main_fog))**0.4) if len(subgraph_main_fog) > 1 else 0.8
            pos_main_fog_raw = nx.spring_layout(subgraph_main_fog, seed=42, k=k_val, iterations=60)

            min_x = min(p[0] for p in pos_main_fog_raw.values()) if pos_main_fog_raw else 0
            max_x = max(p[0] for p in pos_main_fog_raw.values()) if pos_main_fog_raw else 0
            min_y = min(p[1] for p in pos_main_fog_raw.values()) if pos_main_fog_raw else 0
            max_y = max(p[1] for p in pos_main_fog_raw.values()) if pos_main_fog_raw else 0

            span_x = max_x - min_x if max_x > min_x else 1.0
            span_y = max_y - min_y if max_y > min_y else 1.0

            desired_x_width_fog = max((len(cfg_nodes) - 1) * 1.2, (len(fg_nodes) - 1) * 1.0, (len(main_fog_nodes) - 1) * 0.4, 5.0)

            for node, (x, y) in pos_main_fog_raw.items():
                norm_x = ((x - min_x) / span_x - 0.5) * desired_x_width_fog if span_x > 0 else 0
                norm_y = y_fog_main_lower + ((y - min_y) / span_y) * (y_fog_main_upper - y_fog_main_lower) if span_y > 0 else (y_fog_main_lower + y_fog_main_upper) / 2
                pos[node] = (norm_x, norm_y)
        else:
            for node in main_fog_nodes:
                pos[node] = (0, (y_fog_main_lower + y_fog_main_upper) / 2)

    for node in graph_to_draw.nodes():
        if node not in pos:
            pos[node] = (random.uniform(-3, 3), random.uniform(0.5, 3.5))

        node_data = graph_to_draw.nodes[node]
        node_labels[node] = node

        if node_data.get('level') == 'cloud':
            node_colors.append('deepskyblue')
            node_sizes.append(1200)
        elif node_data.get('type') == 'CFG':
            node_colors.append('red')
            node_sizes.append(700)
        elif node_data.get('type') == 'FG':
            node_colors.append('limegreen')
            node_sizes.append(600)
        elif node_data.get('level') == 'fog':
            # Warna berdasarkan komunitas
            community_id = node_data.get('community_id', 'Undefined')
            community_colors = plt.cm.get_cmap('tab10', 10)  # Maksimal 10 komunitas
            if community_id != 'Undefined':
                community_index = int(community_id.replace('CV', '')) - 1
                node_colors.append(community_colors(community_index))
            else:
                node_colors.append('silver')  # Default untuk fog tanpa komunitas
            node_sizes.append(400)
        else:
            node_colors.append('gray')
            node_sizes.append(300)

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
    
    # Menambahkan legend untuk komunitas
    unique_communities = set(node_data.get('community_id', 'Undefined') for node_data in graph_to_draw.nodes.values())
    legend_labels = {f"Community {i+1}": plt.cm.get_cmap('tab10', 10)(i) for i in range(len(unique_communities))}
    legend_handles = [plt.Line2D([0], [0], marker='o', color='w', label=label, markerfacecolor=color, markersize=10) for label, color in legend_labels.items()]
    plt.legend(handles=legend_handles, loc='upper left', bbox_to_anchor=(1, 1), title="Communities", fontsize=8)
    plt.box(False)
    plt.tight_layout(pad=1.0)
    if save_path:
        plt.savefig(save_path, format='png', dpi=300, bbox_inches='tight')
        print(f"Saved plot to {save_path}")
    else:
        print("No save path provided, displaying plot instead.")
plt.show()

def animate_service_placement(graph, services, placement, save_path="results/png/service_placement.gif"):
    """
    Animasi proses penempatan service pada topology, disimpan sebagai GIF.
    :param graph: NetworkX graph (sudah ada node, edge, dan atribut komunitas).
    :param services: List of dict service (hasil application.to_dict_list()).
    :param placement: Dict mapping service_name -> node_name (hasil GA placement).
    :param save_path: Path file gif hasil animasi.
    """
    print("Creating service placement animation...")

    # --- Layout dan layer sama seperti visualisasi komunitas ---
    y_cloud = 4.0
    y_cfg = 3.5
    y_fog_main_upper = 3
    y_fog_main_lower = 0.5
    y_fg = 0.0

    cloud_nodes = [n for n, d in graph.nodes(data=True) if d.get('level') == 'cloud']
    cfg_nodes = [n for n, d in graph.nodes(data=True) if d.get('type') == 'CFG']
    fg_nodes = [n for n, d in graph.nodes(data=True) if d.get('type') == 'FG']
    main_fog_nodes = [n for n, d in graph.nodes(data=True)
                      if d.get('level') == 'fog' and n not in cfg_nodes and n not in fg_nodes]

    def distribute_nodes_x(nodes, y_level, x_spacing=1.0, x_center_offset=0.0):
        positions = {}
        if not nodes: return positions
        total_width = (len(nodes) - 1) * x_spacing
        start_x = x_center_offset - total_width / 2
        for i, node in enumerate(nodes):
            positions[node] = (start_x + i * x_spacing, y_level)
        return positions

    pos = {}
    pos.update(distribute_nodes_x(cloud_nodes, y_cloud, x_spacing=2.0))
    pos.update(distribute_nodes_x(cfg_nodes, y_cfg, x_spacing=1.2))
    pos.update(distribute_nodes_x(fg_nodes, y_fg, x_spacing=1.0))

    if main_fog_nodes:
        subgraph_main_fog = graph.subgraph(main_fog_nodes)
        if subgraph_main_fog.number_of_nodes() > 0:
            k_val = 0.8 / ((len(subgraph_main_fog))**0.4) if len(subgraph_main_fog) > 1 else 0.8
            pos_main_fog_raw = nx.spring_layout(subgraph_main_fog, seed=42, k=k_val, iterations=60)
            min_x = min(p[0] for p in pos_main_fog_raw.values()) if pos_main_fog_raw else 0
            max_x = max(p[0] for p in pos_main_fog_raw.values()) if pos_main_fog_raw else 0
            min_y = min(p[1] for p in pos_main_fog_raw.values()) if pos_main_fog_raw else 0
            max_y = max(p[1] for p in pos_main_fog_raw.values()) if pos_main_fog_raw else 0
            span_x = max_x - min_x if max_x > min_x else 1.0
            span_y = max_y - min_y if max_y > min_y else 1.0
            desired_x_width_fog = max((len(cfg_nodes)-1)*1.2, (len(fg_nodes)-1)*1.0, (len(main_fog_nodes)-1)*0.4, 5.0)
            for node, (x, y) in pos_main_fog_raw.items():
                norm_x = ((x - min_x) / span_x - 0.5) * desired_x_width_fog if span_x > 0 else 0
                norm_y = y_fog_main_lower + ((y - min_y) / span_y) * (y_fog_main_upper - y_fog_main_lower) if span_y > 0 else (y_fog_main_lower+y_fog_main_upper)/2
                pos[node] = (norm_x, norm_y)
        else:
            for node in main_fog_nodes:
                pos[node] = (0, (y_fog_main_lower + y_fog_main_upper)/2)

    # --- Siapkan data untuk animasi ---
    fig, ax = plt.subplots(figsize=(18, 12))
    node_base_colors = []
    for node in graph.nodes():
        node_data = graph.nodes[node]
        if node_data.get('level') == 'cloud':
            node_base_colors.append('deepskyblue')
        elif node_data.get('type') == 'CFG':
            node_base_colors.append('red')
        elif node_data.get('type') == 'FG':
            node_base_colors.append('limegreen')
        elif node_data.get('level') == 'fog':
            community_id = node_data.get('community_id', 'Undefined')
            community_colors = plt.cm.get_cmap('tab10', 10)
            if community_id != 'Undefined':
                community_index = int(community_id.replace('CV', '')) - 1
                node_base_colors.append(community_colors(community_index))
            else:
                node_base_colors.append('silver')
        else:
            node_base_colors.append('gray')

    # Untuk setiap frame, simpan node mana saja yang sudah ditempati service
    service_order = [svc['name'] for svc in services]
    placement_order = [placement[svc_name] for svc_name in service_order]

    # Untuk label, simpan service yang sudah ditempatkan di setiap node
    node_services = {node: [] for node in graph.nodes()}

    def update(frame):
        ax.clear()
        # Tambahkan service ke node sesuai urutan
        svc_name = service_order[frame]
        node = placement_order[frame]
        node_services[node].append(svc_name)

        # Update warna node: gold jika sudah ada service, base color jika belum
        node_colors = []
        for idx, n in enumerate(graph.nodes()):
            if node_services[n]:
                node_colors.append('gold')
            else:
                node_colors.append(node_base_colors[idx])

        # Update label: tampilkan nama node + service yang sudah ditempatkan
        node_labels = {}
        for n in graph.nodes():
            label = n
            if node_services[n]:
                label += "\n" + ", ".join(node_services[n])
            node_labels[n] = label

        nx.draw_networkx_nodes(graph, pos, node_color=node_colors, node_size=700, alpha=0.95, ax=ax)
        nx.draw_networkx_edges(graph, pos, alpha=0.4, edge_color="dimgray", width=0.8, ax=ax)
        nx.draw_networkx_labels(graph, pos, labels=node_labels, font_size=7, font_weight='bold', ax=ax)

        ax.set_title(f"Service Placement Step {frame+1}: {svc_name} → {node}", fontsize=18)
        ax.set_xticks([])
        ax.set_yticks([])

        # Layer lines & labels (opsional)
        ax.axhline(y=(y_cloud + y_cfg) / 2, color='gray', linestyle='--', linewidth=0.7)
        ax.axhline(y=(y_cfg + y_fog_main_upper) / 2, color='gray', linestyle='--', linewidth=0.7)
        ax.axhline(y=(y_fg + y_fog_main_lower) / 2, color='gray', linestyle='--', linewidth=0.7)
        ax.text(ax.get_xlim()[0] - 0.5, y_cloud, 'Cloud Layer', ha='right', va='center', fontsize=10, color='gray')
        ax.text(ax.get_xlim()[0] - 0.5, (y_cfg + y_fog_main_upper)/2 , 'Upper Fog (CFG)', ha='right', va='center', fontsize=10, color='gray')
        ax.text(ax.get_xlim()[0] - 0.5, (y_fog_main_lower + y_fog_main_upper)/2, 'Fog Layer', ha='right', va='center', fontsize=10, color='gray')
        ax.text(ax.get_xlim()[0] - 0.5, y_fg, 'Edge Fog (FG)', ha='right', va='center', fontsize=10, color='gray')
        ax.set_frame_on(False)

    anim = FuncAnimation(fig, update, frames=len(services), repeat=False)
    Path(save_path).parent.mkdir(parents=True, exist_ok=True)
    anim.save(save_path, writer="pillow", fps=1)
    print(f"Service placement animation saved to {save_path}")

def animate_routes_on_topology(graph, routes, title="Service Routing Animation", save_path="results/png/service_routing.gif"):
    """
    Animasi jalur komunikasi (routes) antar service/module di topology.
    :param graph: NetworkX graph (topology komunitas yang sudah ada placement)
    :param routes: dict mapping (service_src, service_dst) -> [node1, node2, ...] (hasil select_routes)
    :param title: Judul plot
    :param save_path: Path file hasil animasi (GIF)
    """
    if graph.number_of_nodes() == 0:
        print("Graph is empty, skipping drawing.")
        return

    fig, ax = plt.subplots(figsize=(18, 12))

    # --- Layout dan layer sama seperti visualisasi lain ---
    y_cloud = 4.0
    y_cfg = 3.5
    y_fog_main_upper = 3
    y_fog_main_lower = 0.5
    y_fg = 0.0

    cloud_nodes = [n for n, d in graph.nodes(data=True) if d.get('level') == 'cloud']
    cfg_nodes = [n for n, d in graph.nodes(data=True) if d.get('type') == 'CFG']
    fg_nodes = [n for n, d in graph.nodes(data=True) if d.get('type') == 'FG']
    main_fog_nodes = [n for n, d in graph.nodes(data=True)
                      if d.get('level') == 'fog' and n not in cfg_nodes and n not in fg_nodes]

    def distribute_nodes_x(nodes, y_level, x_spacing=1.0, x_center_offset=0.0):
        positions = {}
        if not nodes: return positions
        total_width = (len(nodes) - 1) * x_spacing
        start_x = x_center_offset - total_width / 2
        for i, node in enumerate(nodes):
            positions[node] = (start_x + i * x_spacing, y_level)
        return positions

    pos = {}
    pos.update(distribute_nodes_x(cloud_nodes, y_cloud, x_spacing=2.0))
    pos.update(distribute_nodes_x(cfg_nodes, y_cfg, x_spacing=1.2))
    pos.update(distribute_nodes_x(fg_nodes, y_fg, x_spacing=1.0))

    if main_fog_nodes:
        subgraph_main_fog = graph.subgraph(main_fog_nodes)
        if subgraph_main_fog.number_of_nodes() > 0:
            k_val = 0.8 / ((len(subgraph_main_fog))**0.4) if len(subgraph_main_fog) > 1 else 0.8
            pos_main_fog_raw = nx.spring_layout(subgraph_main_fog, seed=42, k=k_val, iterations=60)
            min_x = min(p[0] for p in pos_main_fog_raw.values()) if pos_main_fog_raw else 0
            max_x = max(p[0] for p in pos_main_fog_raw.values()) if pos_main_fog_raw else 0
            min_y = min(p[1] for p in pos_main_fog_raw.values()) if pos_main_fog_raw else 0
            max_y = max(p[1] for p in pos_main_fog_raw.values()) if pos_main_fog_raw else 0
            span_x = max_x - min_x if max_x > min_x else 1.0
            span_y = max_y - min_y if max_y > min_y else 1.0
            desired_x_width_fog = max((len(cfg_nodes)-1)*1.2, (len(fg_nodes)-1)*1.0, (len(main_fog_nodes)-1)*0.4, 5.0)
            for node, (x, y) in pos_main_fog_raw.items():
                norm_x = ((x - min_x) / span_x - 0.5) * desired_x_width_fog if span_x > 0 else 0
                norm_y = y_fog_main_lower + ((y - min_y) / span_y) * (y_fog_main_upper - y_fog_main_lower) if span_y > 0 else (y_fog_main_lower+y_fog_main_upper)/2
                pos[node] = (norm_x, norm_y)
        else:
            for node in main_fog_nodes:
                pos[node] = (0, (y_fog_main_lower + y_fog_main_upper)/2)

    node_colors = []
    node_sizes = []
    node_labels = {}
    for node in graph.nodes():
        node_data = graph.nodes[node]
        node_labels[node] = node
        node_type = node_data.get('type')
        if node_type == 'cloud_server': node_colors.append('deepskyblue'); node_sizes.append(1200)
        elif node_type == 'CFG': node_colors.append('red'); node_sizes.append(700)
        elif node_type == 'FG': node_colors.append('limegreen'); node_sizes.append(600)
        else: node_colors.append('silver'); node_sizes.append(400)

    route_keys = list(routes.keys())
    route_colors = ['blue', 'green', 'orange', 'purple', 'magenta', 'brown', 'black']

    def update(frame):
        ax.clear()
        # Draw base graph
        nx.draw_networkx_nodes(graph, pos, node_color=node_colors, node_size=node_sizes, alpha=0.9, ax=ax)
        nx.draw_networkx_edges(graph, pos, alpha=0.4, edge_color="dimgray", width=0.8, ax=ax)
        nx.draw_networkx_labels(graph, pos, labels=node_labels, font_size=7, font_weight='bold', ax=ax)

        # Draw routes up to current frame
        for idx in range(frame+1):
            if idx >= len(route_keys): continue
            (src, dst) = route_keys[idx]
            path = routes[(src, dst)]
            if not path or len(path) < 2: continue
            color = route_colors[idx % len(route_colors)]
            edge_list = list(zip(path[:-1], path[1:]))
            nx.draw_networkx_edges(graph, pos, edgelist=edge_list, width=4, edge_color=color, alpha=0.8, ax=ax)
            nx.draw_networkx_nodes(graph, pos, nodelist=path, node_color=color, node_size=900, alpha=0.3, ax=ax)
            mid_idx = len(path)//2
            ax.text(pos[path[mid_idx]][0], pos[path[mid_idx]][1]+0.2, f"{src}→{dst}", color=color, fontsize=11, fontweight='bold')

        ax.set_title(f"{title} (Step {frame+1}/{len(route_keys)})", fontsize=18)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.axhline(y=(y_cloud + y_cfg) / 2, color='gray', linestyle='--', linewidth=0.7)
        ax.axhline(y=(y_cfg + y_fog_main_upper) / 2, color='gray', linestyle='--', linewidth=0.7)
        ax.axhline(y=(y_fg + y_fog_main_lower) / 2, color='gray', linestyle='--', linewidth=0.7)
        ax.text(ax.get_xlim()[0] - 0.5, y_cloud, 'Cloud Layer', ha='right', va='center', fontsize=10, color='gray')
        ax.text(ax.get_xlim()[0] - 0.5, (y_cfg + y_fog_main_upper)/2 , 'Upper Fog (CFG)', ha='right', va='center', fontsize=10, color='gray')
        ax.text(ax.get_xlim()[0] - 0.5, (y_fog_main_lower + y_fog_main_upper)/2, 'Fog Layer', ha='right', va='center', fontsize=10, color='gray')
        ax.text(ax.get_xlim()[0] - 0.5, y_fg, 'Edge Fog (FG)', ha='right', va='center', fontsize=10, color='gray')
        ax.set_frame_on(False)

    anim = FuncAnimation(fig, update, frames=len(route_keys), repeat=False)
    Path(save_path).parent.mkdir(parents=True, exist_ok=True)
    anim.save(save_path, writer="pillow", fps=1)
    print(f"Service routing animation saved to {save_path}")
    
def animate_request_flow(graph, event_log, save_path="results/png/request_flow.gif"):
    """
    Animasi request flow: request bergerak node per node di sepanjang path, info rate & delay tampil di node aktif.
    """
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation
    from pathlib import Path

    if not isinstance(event_log, list):
        try:
            event_log = list(event_log)
        except Exception:
            print("event_log harus berupa list of dict!")
            return
    if not event_log:
        print("No events to animate.")
        return

    # Layout & pos (copy dari animasi lain)
    y_cloud = 4.0
    y_cfg = 3.5
    y_fog_main_upper = 3
    y_fog_main_lower = 0.5
    y_fg = 0.0

    cloud_nodes = [n for n, d in graph.nodes(data=True) if d.get('level') == 'cloud']
    cfg_nodes = [n for n, d in graph.nodes(data=True) if d.get('type') == 'CFG']
    fg_nodes = [n for n, d in graph.nodes(data=True) if d.get('type') == 'FG']
    main_fog_nodes = [n for n, d in graph.nodes(data=True)
                      if d.get('level') == 'fog' and n not in cfg_nodes and n not in fg_nodes]

    def distribute_nodes_x(nodes, y_level, x_spacing=1.0, x_center_offset=0.0):
        positions = {}
        if not nodes: return positions
        total_width = (len(nodes) - 1) * x_spacing
        start_x = x_center_offset - total_width / 2
        for i, node in enumerate(nodes):
            positions[node] = (start_x + i * x_spacing, y_level)
        return positions

    pos = {}
    pos.update(distribute_nodes_x(cloud_nodes, y_cloud, x_spacing=2.0))
    pos.update(distribute_nodes_x(cfg_nodes, y_cfg, x_spacing=1.2))
    pos.update(distribute_nodes_x(fg_nodes, y_fg, x_spacing=1.0))

    if main_fog_nodes:
        subgraph_main_fog = graph.subgraph(main_fog_nodes)
        if subgraph_main_fog.number_of_nodes() > 0:
            k_val = 0.8 / ((len(subgraph_main_fog))**0.4) if len(subgraph_main_fog) > 1 else 0.8
            pos_main_fog_raw = nx.spring_layout(subgraph_main_fog, seed=42, k=k_val, iterations=60)
            min_x = min(p[0] for p in pos_main_fog_raw.values()) if pos_main_fog_raw else 0
            max_x = max(p[0] for p in pos_main_fog_raw.values()) if pos_main_fog_raw else 0
            min_y = min(p[1] for p in pos_main_fog_raw.values()) if pos_main_fog_raw else 0
            max_y = max(p[1] for p in pos_main_fog_raw.values()) if pos_main_fog_raw else 0
            span_x = max_x - min_x if max_x > min_x else 1.0
            span_y = max_y - min_y if max_y > min_y else 1.0
            desired_x_width_fog = max((len(cfg_nodes)-1)*1.2, (len(fg_nodes)-1)*1.0, (len(main_fog_nodes)-1)*0.4, 5.0)
            for node, (x, y) in pos_main_fog_raw.items():
                norm_x = ((x - min_x) / span_x - 0.5) * desired_x_width_fog if span_x > 0 else 0
                norm_y = y_fog_main_lower + ((y - min_y) / span_y) * (y_fog_main_upper - y_fog_main_lower) if span_y > 0 else (y_fog_main_lower+y_fog_main_upper)/2
                pos[node] = (norm_x, norm_y)
        else:
            for node in main_fog_nodes:
                pos[node] = (0, (y_fog_main_lower + y_fog_main_upper)/2)

    node_colors = []
    node_sizes = []
    node_labels = {}
    for node in graph.nodes():
        node_data = graph.nodes[node]
        node_labels[node] = node
        node_type = node_data.get('type')
        if node_type == 'cloud_server': node_colors.append('deepskyblue'); node_sizes.append(1200)
        elif node_type == 'CFG': node_colors.append('red'); node_sizes.append(700)
        elif node_type == 'FG': node_colors.append('limegreen'); node_sizes.append(600)
        else: node_colors.append('silver'); node_sizes.append(400)

    # --- Build frame list: (event_idx, step_idx) for each step along each path ---
    frame_steps = []
    for event_idx, event in enumerate(event_log):
        path = event.get('path', [])
        if path and len(path) > 1:
            for step in range(1, len(path)):
                frame_steps.append((event_idx, step))
        else:
            frame_steps.append((event_idx, 1))

    fig, ax = plt.subplots(figsize=(18, 12))

    def update(frame):
        ax.clear()
        event_idx, step = frame_steps[frame]
        event = event_log[event_idx]
        path = event.get('path', [])
        src = event.get('source', '-')
        dst = event.get('target_service', '-')
        delay = event.get('total_delay', event.get('delay', '-'))
        rate = event.get('rate', '-')

        # Draw base graph
        nx.draw_networkx_nodes(graph, pos, node_color=node_colors, node_size=node_sizes, alpha=0.9, ax=ax)
        nx.draw_networkx_edges(graph, pos, alpha=0.4, edge_color="dimgray", width=0.8, ax=ax)
        nx.draw_networkx_labels(graph, pos, labels=node_labels, font_size=7, font_weight='bold', ax=ax)

        # Efek mengalir: highlight edge/node yang sudah dilewati dan yang sedang aktif
        if path and len(path) > 1:
            # Sudah dilewati (gold)
            if step > 1:
                nx.draw_networkx_edges(graph, pos, edgelist=list(zip(path[:step-1], path[1:step])), width=4, edge_color='gold', alpha=0.5, ax=ax)
                nx.draw_networkx_nodes(graph, pos, nodelist=path[:step], node_color='gold', node_size=900, alpha=0.3, ax=ax)
            # Edge/node aktif (oranye)
            highlight_edge = [(path[step-1], path[step])]
            highlight_node = [path[step]]
            nx.draw_networkx_edges(graph, pos, edgelist=highlight_edge, width=6, edge_color='orange', alpha=0.9, ax=ax)
            nx.draw_networkx_nodes(graph, pos, nodelist=highlight_node, node_color='orange', node_size=1100, alpha=0.7, ax=ax)

        # Judul dan info di bawah plot
        ax.set_title(f"Request Flow Animation (Event {event_idx+1}, Step {step}/{len(path)-1 if path else 1})", fontsize=18)
        info_text = f"{src}→{dst}   |   Rate: {rate} req/s   |   Delay: {delay}"
        fig = ax.get_figure()
        fig.subplots_adjust(bottom=0.18)
        ax.text(0.5, -0.13, info_text, color='orange', fontsize=13, fontweight='bold',
                ha='center', va='center', transform=ax.transAxes, bbox=dict(facecolor='white', alpha=0.7, edgecolor='orange'))

        # Layer lines & labels (opsional, agar konsisten)
        ax.axhline(y=(y_cloud + y_cfg) / 2, color='gray', linestyle='--', linewidth=0.7)
        ax.axhline(y=(y_cfg + y_fog_main_upper) / 2, color='gray', linestyle='--', linewidth=0.7)
        ax.axhline(y=(y_fg + y_fog_main_lower) / 2, color='gray', linestyle='--', linewidth=0.7)
        ax.text(ax.get_xlim()[0] - 0.5, y_cloud, 'Cloud Layer', ha='right', va='center', fontsize=10, color='gray')
        ax.text(ax.get_xlim()[0] - 0.5, (y_cfg + y_fog_main_upper)/2 , 'Upper Fog (CFG)', ha='right', va='center', fontsize=10, color='gray')
        ax.text(ax.get_xlim()[0] - 0.5, (y_fog_main_lower + y_fog_main_upper)/2, 'Fog Layer', ha='right', va='center', fontsize=10, color='gray')
        ax.text(ax.get_xlim()[0] - 0.5, y_fg, 'Edge Fog (FG)', ha='right', va='center', fontsize=10, color='gray')
        ax.set_frame_on(False)

    anim = FuncAnimation(fig, update, frames=len(frame_steps), repeat=False)
    Path(save_path).parent.mkdir(parents=True, exist_ok=True)
    anim.save(save_path, writer="pillow", fps=1)
    print(f"Request flow animation saved to {save_path}")
   