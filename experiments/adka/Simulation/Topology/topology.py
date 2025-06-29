import os
import time
import random
from pathlib import Path
import csv

import networkx as nx
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

from yafs.core import Sim
from yafs.topology import Topology
from yafs.path_routing import DeviceSpeedAwareRouting
from Simulation.config import *

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




def export_topology_to_csv(graph, folder_path="results", node_filename="nodes.csv", edge_filename="edges.csv"):
    """
    Mengekspor topologi ke file CSV.
    :param graph: Graf NetworkX yang akan diekspor.
    :param folder_path: Folder tempat file CSV akan disimpan.
    :param node_filename: Nama file CSV untuk node.
    :param edge_filename: Nama file CSV untuk edge.
    """
    folder = Path(folder_path)
    folder.mkdir(parents=True, exist_ok=True)

    # Ekspor node
    node_file_path = folder / node_filename
    with open(node_file_path, mode="w", newline="", encoding="utf-8") as node_file:
        fieldnames = ["node", "RAM", "IPT", "STO", "level", "type"]
        writer = csv.DictWriter(node_file, fieldnames=fieldnames)
        writer.writeheader()

        for node, data in graph.nodes(data=True):
            writer.writerow({
                "node": node,
                "RAM": data.get("RAM", ""),
                "IPT": data.get("IPT", ""),
                "STO": data.get("STO", ""),
                "level": data.get("level", ""),
                "type": data.get("type", "")
            })

    print(f"Node data exported to {node_file_path}")

    # Ekspor edge
    edge_file_path = folder / edge_filename
    with open(edge_file_path, mode="w", newline="", encoding="utf-8") as edge_file:
        fieldnames = ["source", "target", "BW", "PR"]
        writer = csv.DictWriter(edge_file, fieldnames=fieldnames)
        writer.writeheader()

        for u, v, data in graph.edges(data=True):
            writer.writerow({
                "source": u,
                "target": v,
                "BW": data.get("BW", ""),
                "PR": data.get("PR", "")
            })

    print(f"Edge data exported to {edge_file_path}")