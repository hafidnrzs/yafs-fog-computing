import os
import time
import random
import csv
from pathlib import Path

import networkx as nx
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

from yafs.core import Sim
from yafs.topology import Topology
from Simulation.ComunityGA.comunityGA import genetic_algorithm  # Impor algoritma genetika

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
PERCENT_CFG_NODES = 0.05  # 5%
PERCENT_FG_NODES = 0.25  # 25%

# --- Parameter Komunitas dari Table 2 ---
NUM_COMMUNITIES = 10

# Parameter Lain (Tidak dari Table 3 untuk fog environment, bisa disesuaikan)
NUM_CLOUD_NODES = 3
BARABASI_M = 2  # Untuk Barabasi-Albert graph

# Atribut default untuk Cloud Nodes (sumber daya besar)
DEFAULT_CLOUD_RAM_MB = 200000  # Jauh lebih besar dari fog
DEFAULT_CLOUD_IPT_INSTR_MS = 100000
DEFAULT_CLOUD_STO_TB = 200

# --- Folder untuk menyimpan hasil ---
RESULTS_FOLDER = "results"
Path(RESULTS_FOLDER).mkdir(parents=True, exist_ok=True)

# --- Fungsi untuk membuat topologi ---
def create_topology_community(graph, chromosome):
    """
    Memperbarui graf dengan atribut komunitas berdasarkan kromosom.
    :param graph: Graf NetworkX yang akan diperbarui.
    :param chromosome: Kromosom hasil dari Community GA.
    :return: Graf yang diperbarui dengan atribut komunitas.
    """
    print("Updating topology with community assignments...")
    node_attrs_community = {}

    # Tetapkan atribut komunitas berdasarkan kromosom
    for i, node_name in enumerate(graph.nodes):
        if i < len(chromosome):  # Pastikan index tidak keluar batas
            community_id_int = chromosome[i]
            node_attrs_community[node_name] = f"CV{community_id_int}"  # Simpan sebagai string "CV1", "CV2", dst.
        else:
            node_attrs_community[node_name] = "CV_Undefined"  # Fallback jika ada ketidaksesuaian

    # Terapkan atribut komunitas ke graf
    nx.set_node_attributes(graph, values=node_attrs_community, name="community_id")

    print(f"Updated topology with {len(set(chromosome))} communities.")
    return graph

def export_topology_ga_to_csv(graph, folder_path="results/csv", node_filename="nodes.csv", edge_filename="edges.csv"):
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
        fieldnames = ["node", "RAM", "IPT", "STO", "level", "type", "community_id"]
        writer = csv.DictWriter(node_file, fieldnames=fieldnames)
        writer.writeheader()

        for node, data in graph.nodes(data=True):
            
            writer.writerow({
                "node": node,
                "RAM": data.get("RAM", ""),
                "IPT": data.get("IPT", ""),
                "STO": data.get("STO", ""),
                "level": data.get("level", ""),
                "type": data.get("type", ""),
                "community_id": data.get("community_id", "")
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