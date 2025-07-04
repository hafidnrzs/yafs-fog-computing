import networkx as nx
import random
from config import config # Impor konfigurasi kita

def generate_network():
    """
    Membuat topologi jaringan berdasarkan model Barabasi-Albert.
    
    Spesifikasi:
    - Membuat graf fog node.
    - Menambahkan atribut acak ke node (RAM, IPT, Storage) dan link (BW, PR).
    - Mengidentifikasi Fog Gateways (FG) dan Cloud-Fog Gateways (CFG)
      berdasarkan betweenness centrality.
    - Menambahkan node Cloud dan menghubungkannya ke CFG.
    """
    # Set seed untuk reproducibility selama debug
    random.seed(config.RANDOM_SEED)
    
    # 1. Membuat graf dasar menggunakan model Barabasi-Albert
    # Parameter `m` (jumlah edge baru per node) tidak disebut di paper, kita asumsikan 2
    # untuk menciptakan graf yang cukup terhubung.
    G = nx.barabasi_albert_graph(n=config.NUM_FOG_NODES, m=2, seed=config.RANDOM_SEED)
    
    # 2. Menambahkan atribut acak ke setiap FOG NODE
    for node_id in G.nodes():
        G.nodes[node_id]['id'] = node_id
        G.nodes[node_id]['RAM'] = random.randint(*config.NODE_RAM_RANGE)
        G.nodes[node_id]['IPT'] = random.randint(*config.NODE_IPT_RANGE)
        G.nodes[node_id]['TB'] = random.uniform(*config.NODE_STORAGE_RANGE)
        G.nodes[node_id]['type'] = 'FOG_NODE' # Tipe default
        
    # 3. Menambahkan atribut acak ke setiap LINK
    for (u, v) in G.edges():
        G.edges[u, v]['PR'] = random.randint(*config.LINK_PROPAGATION_RANGE)
        G.edges[u, v]['BW'] = random.randint(*config.LINK_BANDWIDTH_RANGE)
        
    # 4. Mengidentifikasi FG dan CFG berdasarkan betweenness centrality
    centrality = nx.betweenness_centrality(G)
    sorted_nodes = sorted(centrality.items(), key=lambda item: item[1])
    
    num_fg = int(config.NUM_FOG_NODES * config.GATEWAY_NODES_PERCENTAGE)
    num_cfg = int(config.NUM_FOG_NODES * config.CLOUD_GATEWAY_NODES_PERCENTAGE)
    
    # Node dengan centrality terendah menjadi Fog Gateways (FG)
    fg_nodes = [node_id for node_id, _ in sorted_nodes[:num_fg]]
    for node_id in fg_nodes:
        G.nodes[node_id]['type'] = 'FOG_GATEWAY'
        
    # Node dengan centrality tertinggi menjadi Cloud-Fog Gateways (CFG)
    cfg_nodes = [node_id for node_id, _ in sorted_nodes[-num_cfg:]]
    for node_id in cfg_nodes:
        G.nodes[node_id]['type'] = 'CLOUD_FOG_GATEWAY'

    # 5. Menambahkan node CLOUD
    cloud_id = config.CLOUD_NODE_ID
    G.add_node(cloud_id, id=cloud_id, RAM=9e12, IPT=9e12, TB=9e12, type='CLOUD')
    
    # 6. Menghubungkan CFG ke CLOUD
    # Atribut link ke cloud tidak dispesifikasi, kita beri nilai BW tinggi & PR rendah
    for node_id in cfg_nodes:
        G.add_edge(node_id, cloud_id, PR=1, BW=1e9)
        
    return G