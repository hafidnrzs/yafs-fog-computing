"""Functions for visualizing the topology."""
import matplotlib.pyplot as plt
import networkx as nx
from pathlib import Path
from config import *

def visualize_layered_topology(graph_to_draw, num_communities_param, title="Layered Topology with Communities", save_path=None):
    if graph_to_draw.number_of_nodes() == 0:
        print("Graph is empty, skipping drawing.")
        return

    print(f"\nAttempting to draw: {title}...")
    plt.figure(figsize=(22, 16))
    pos = {}
    node_colors_list = []
    node_sizes = []
    node_labels = {node: node for node in graph_to_draw.nodes()}

    y_cloud = 4.0
    y_cfg = 3.5
    y_fog_main_upper = 3.0
    y_fog_main_lower = 0.5
    y_fg = 0.0

    if num_communities_param <= 0:
        community_color_map = None
    elif num_communities_param <= 10:
        community_color_map = plt.cm.get_cmap('tab10', num_communities_param)
    elif num_communities_param <= 20:
        community_color_map = plt.cm.get_cmap('tab20', num_communities_param)
    else:
        community_color_map = plt.cm.get_cmap('nipy_spectral', num_communities_param)

    cloud_nodes = [n for n, d in graph_to_draw.nodes(data=True) if d.get('level') == 'cloud']
    cfg_nodes = [n for n, d in graph_to_draw.nodes(data=True) if d.get('type') == 'CFG']
    fg_nodes = [n for n, d in graph_to_draw.nodes(data=True) if d.get('type') == 'FG']
    main_fog_nodes = [n for n, d in graph_to_draw.nodes(data=True)
                      if d.get('level') == 'fog' and n not in cfg_nodes and n not in fg_nodes]

    # Calculate estimated width
    estimated_main_fog_width = calculate_estimated_width(graph_to_draw, main_fog_nodes)

    # Position nodes
    pos.update(distribute_nodes_x(cloud_nodes, y_cloud, x_spacing_factor=2.0, 
                                overall_width_hint=max(estimated_main_fog_width * 0.8, 3.0)))
    pos.update(distribute_nodes_x(cfg_nodes, y_cfg, x_spacing_factor=1.2, 
                                overall_width_hint=max(estimated_main_fog_width * 0.9, 2.0)))
    pos.update(distribute_nodes_x(fg_nodes, y_fg, x_spacing_factor=1.0, 
                                overall_width_hint=max(estimated_main_fog_width * 0.9, 2.0)))

    # Position main fog nodes
    pos.update(position_main_fog_nodes(graph_to_draw, main_fog_nodes, y_fog_main_upper, 
                                     y_fog_main_lower, estimated_main_fog_width))

    # Color and size nodes
    node_colors_list, node_sizes = get_node_visual_attributes(graph_to_draw, pos, 
                                                            community_color_map, num_communities_param)

    # Draw the graph
    draw_graph(graph_to_draw, pos, node_colors_list, node_sizes, node_labels)

    # Add layer indicators and legend
    add_layer_indicators(y_cloud, y_cfg, y_fog_main_upper, y_fog_main_lower, y_fg)
    add_legend(community_color_map, num_communities_param)

    # Save or show the plot
    finalize_plot(save_path)

def calculate_estimated_width(graph, main_fog_nodes):
    estimated_main_fog_width = 0
    if main_fog_nodes:
        temp_subgraph_main_fog = graph.subgraph(main_fog_nodes)
        if temp_subgraph_main_fog.number_of_nodes() > 0:
            try:
                temp_pos_main_fog = nx.spring_layout(temp_subgraph_main_fog, seed=SEED, k=0.5)
                if temp_pos_main_fog:
                    all_x = [p[0] for p in temp_pos_main_fog.values()]
                    estimated_main_fog_width = (max(all_x) - min(all_x)) if all_x else 0
            except Exception as e:
                print(f"Warning: Could not estimate main fog width: {e}")
                estimated_main_fog_width = len(main_fog_nodes) * 0.3
    return estimated_main_fog_width

def distribute_nodes_x(nodes, y_level, x_spacing_factor=1.0, overall_width_hint=None):
    positions = {}
    if not nodes:
        return positions

    num_nodes = len(nodes)
    if num_nodes == 1:
        positions[nodes[0]] = (0, y_level)
        return positions

    if overall_width_hint and overall_width_hint > 0:
        x_spacing = overall_width_hint / (num_nodes - 1) if num_nodes > 1 else 0
    else:
        x_spacing = x_spacing_factor

    total_width = (num_nodes - 1) * x_spacing
    start_x = -total_width / 2

    for i, node in enumerate(nodes):
        positions[node] = (start_x + i * x_spacing, y_level)
    return positions

def position_main_fog_nodes(graph, main_fog_nodes, y_upper, y_lower, desired_x_width):
    positions = {}
    if not main_fog_nodes:
        return positions

    subgraph_main_fog = graph.subgraph(main_fog_nodes)
    if subgraph_main_fog.number_of_nodes() > 0:
        k_val = 0.8 / ((len(subgraph_main_fog))**0.35) if len(subgraph_main_fog) > 1 else 0.8
        pos_main_fog_raw = nx.spring_layout(subgraph_main_fog, seed=SEED, k=k_val, iterations=80)

        all_raw_x = [p[0] for p in pos_main_fog_raw.values()]
        all_raw_y = [p[1] for p in pos_main_fog_raw.values()]
        min_x_raw, max_x_raw = (min(all_raw_x), max(all_raw_x)) if all_raw_x else (0, 0)
        min_y_raw, max_y_raw = (min(all_raw_y), max(all_raw_y)) if all_raw_y else (0, 0)
        span_x_raw = max_x_raw - min_x_raw if max_x_raw > min_x_raw else 1.0
        span_y_raw = max_y_raw - min_y_raw if max_y_raw > min_y_raw else 1.0

        desired_x_width = max(desired_x_width, (len(main_fog_nodes)-1)*0.3, 5.0)

        for node, (x_raw, y_raw) in pos_main_fog_raw.items():
            norm_x = ((x_raw - min_x_raw) / span_x_raw - 0.5) * desired_x_width if span_x_raw > 0 else 0
            norm_y = y_lower + ((y_raw - min_y_raw) / span_y_raw) * (y_upper - y_lower) if span_y_raw > 0 else (y_lower+y_upper)/2
            positions[node] = (norm_x, norm_y)
    elif main_fog_nodes:
        positions[main_fog_nodes[0]] = (0, (y_lower + y_upper)/2)

    return positions

def get_node_visual_attributes(graph, pos, community_color_map, num_communities_param):
    node_colors_list = []
    node_sizes = []
    default_fog_color = 'gainsboro'

    for node in graph.nodes():
        if node not in pos:
            pos[node] = (random.uniform(-3, 3), random.uniform(0.5, 3.5))
        
        node_data = graph.nodes[node]
        node_type = node_data.get('type')
        node_level = node_data.get('level')
        current_color = 'gray'
        current_size = 400

        if node_type == 'cloud_server':
            current_color = 'deepskyblue'
            current_size = 1200
        elif node_type == 'CFG':
            current_color = 'red'
            current_size = 800
        elif node_type == 'FG':
            current_color = 'limegreen'
            current_size = 700
        elif node_level == 'fog':
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

    return node_colors_list, node_sizes

def draw_graph(graph, pos, node_colors, node_sizes, node_labels):
    nx.draw_networkx_nodes(graph, pos, node_color=node_colors, node_size=node_sizes, alpha=0.9)
    nx.draw_networkx_edges(graph, pos, alpha=0.3, edge_color="dimgray", width=0.7)
    nx.draw_networkx_labels(graph, pos, labels=node_labels, font_size=6, font_weight='normal')

def add_layer_indicators(y_cloud, y_cfg, y_fog_main_upper, y_fog_main_lower, y_fg):
    current_xlim = plt.xlim()
    label_x_pos = current_xlim[0] - (current_xlim[1] - current_xlim[0]) * 0.03

    # Add horizontal lines and labels for each layer
    plt.axhline(y=(y_cloud + y_cfg) / 2 + 0.05, color='gray', linestyle=':', linewidth=0.9, xmin=0.05, xmax=0.95)
    plt.text(label_x_pos, y_cloud, 'Cloud Layer', ha='right', va='center', fontsize=12, color='dimgray', fontweight='bold')
    
    plt.axhline(y=(y_cfg + y_fog_main_upper) / 2 + 0.05, color='gray', linestyle=':', linewidth=0.9, xmin=0.05, xmax=0.95)
    plt.text(label_x_pos, y_cfg, 'CFG Layer', ha='right', va='center', fontsize=12, color='dimgray', fontweight='bold')
    
    plt.text(label_x_pos, (y_fog_main_lower + y_fog_main_upper)/2, 'Fog Node Layer', 
             ha='right', va='center', fontsize=12, color='dimgray', fontweight='bold')
    
    plt.axhline(y=(y_fg + y_fog_main_lower) / 2 - 0.05, color='gray', linestyle=':', linewidth=0.9, xmin=0.05, xmax=0.95)
    plt.text(label_x_pos, y_fg, 'FG Layer', ha='right', va='center', fontsize=12, color='dimgray', fontweight='bold')

def add_legend(community_color_map, num_communities_param):
    default_fog_color = 'gainsboro'
    legend_elements = [
        plt.Line2D([0], [0], marker='o', color='w', label='Cloud Server', 
                   markersize=10, markerfacecolor='deepskyblue'),
        plt.Line2D([0], [0], marker='o', color='w', label='CFG Node', 
                   markersize=10, markerfacecolor='red'),
        plt.Line2D([0], [0], marker='o', color='w', label='FG Node', 
                   markersize=10, markerfacecolor='limegreen'),
    ]

    if community_color_map and num_communities_param > 0:
        for i in range(num_communities_param):
            community_num_for_legend = i + 1
            color = community_color_map(i % num_communities_param)
            legend_elements.append(
                plt.Line2D([0], [0], marker='o', color='w', 
                          label=f'Community CV{community_num_for_legend}',
                          markersize=10, markerfacecolor=color)
            )
    else:
        legend_elements.append(
            plt.Line2D([0], [0], marker='o', color='w', label='Fog Node', 
                      markersize=10, markerfacecolor=default_fog_color)
        )

    ncol_legend = 1
    if num_communities_param > 5: ncol_legend = 2
    if num_communities_param > 12: ncol_legend = 3

    plt.legend(handles=legend_elements, loc='center left', bbox_to_anchor=(1.01, 0.5),
              fontsize=9, title="Legend", title_fontsize='11', ncol=ncol_legend)

def finalize_plot(save_path):
    plt.title(plt.gca().get_title(), fontsize=20, fontweight='bold')
    plt.xticks([])
    plt.yticks([])
    plt.box(False)

    ncol_legend = len(plt.gca().get_legend().get_texts()) > 5
    plt.tight_layout(rect=[0.05, 0.05, 0.82 if ncol_legend else 0.85, 0.95])

    if save_path:
        plt.savefig(save_path, dpi=200, bbox_inches='tight')
        print(f"Plot saved to {save_path}")
    else:
        plt.show()
    plt.close()
