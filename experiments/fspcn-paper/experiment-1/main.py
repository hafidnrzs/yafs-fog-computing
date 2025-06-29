import time
import random
import logging.config

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import networkx as nx
from pathlib import Path

from yafs.topology import Topology

# Seed untuk reproducibility
SEED = 42

# Parameter
BARABASI_M = 2
NUM_COMMUNITIES = 10

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


def main(stop_time, iter, folder_results):
    #
    # TOPOLOGY
    #
    t = Topology()

    ba_params = [NUM_FOG_NODES, BARABASI_M]
    try:
        t.create_random_topology(nx.barabasi_albert_graph, ba_params)
    except Exception as e:
        print(f"Failed to create topology: {e}")

    if t.G:
        print(f"Number of nodes in generated graph: {t.G.number_of_nodes()}")
        print(f"Number of edges in generated graph: {t.G.number_of_edges()}")
    else:
        print("Graph generation failed.")

    # Attribute pada edges
    attr_PR = {}
    attr_BW = {}

    for edge in t.G.edges():
        random_BW = random.randint(MIN_LINK_BW_BPS, MAX_LINK_BW_BPS)
        attr_BW[edge] = random_BW

        random_PR = random.randint(MIN_LINK_PD_MS, MAX_LINK_PD_MS)
        attr_PR[edge] = random_PR

    nx.set_edge_attributes(t.G, name="PR", values=attr_PR)
    nx.set_edge_attributes(t.G, name="BW", values=attr_BW)

    # Attribute pada nodes
    attr_RAM = {}
    attr_IPT = {}
    attr_TB = {}
    attr_CV = {}

    for node in t.G.nodes():
        random_RAM = random.randint(MIN_FOG_RAM_MB, MAX_FOG_RAM_MB)
        attr_RAM[node] = random_RAM

        random_IPT = random.randint(MIN_FOG_IPT_INSTR_MS, MAX_FOG_IPT_INSTR_MS)
        attr_IPT[node] = random_IPT

        random_TB = random.uniform(MIN_FOG_TB_TERABYTE, MAX_FOG_TB_TERABYTE)
        attr_TB[node] = random_TB

        # Generate komunitas
        community_id = (node % NUM_COMMUNITIES) + 1
        attr_CV[node] = f"CV_{community_id}"

    nx.set_node_attributes(t.G, name="IPT", values=attr_IPT)
    nx.set_node_attributes(t.G, name="RAM", values=attr_RAM)
    nx.set_node_attributes(t.G, name="TB", values=attr_TB)
    nx.set_node_attributes(t.G, name="CV", values=attr_CV)

    nx.write_gexf(t.G, folder_results +
                  f"graph_barabasi_albert_{BARABASI_M}.gexf")

    print(t.G.nodes())

    # Plotting the graph
    pos = nx.spring_layout(t.G)
    nx.draw_networkx(t.G, pos, with_labels=True)
    nx.draw_networkx_edge_labels(
        t.G, pos, alpha=0.5, font_size=5, verticalalignment="top")
    # plt.savefig(folder_results + "topology_visualization.png")
    # print(f"Plot saved to {folder_results}/topology_visualization.png")


if __name__ == '__main__':

    LOGGING_CONFIG = Path(__file__).parent / 'logging.ini'
    logging.config.fileConfig(LOGGING_CONFIG)

    folder_results = Path("results/")
    folder_results.mkdir(parents=True, exist_ok=True)
    folder_results = str(folder_results) + "/"

    nIterations = 1  # iterasi untuk tiap eksperimen
    simulationDuration = 20000

    for iteration in range(nIterations):
        random.seed(SEED)
        logging.info(f"Running experiment iter: - {iteration + 1}")

        start_time = time.time()
        main(stop_time=simulationDuration, iter=iteration,
             folder_results=folder_results)

        print(f"\n--- {time.time() - start_time} seconds ---")

    print("Simulation Done!")
