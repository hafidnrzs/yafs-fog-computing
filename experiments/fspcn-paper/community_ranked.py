import networkx as nx
import random

# --- Kelas Pembantu untuk Graf dengan Fitur Komunitas ---
class GraphWithCommunityFeatures(nx.Graph):
    def __init__(self, community_node_mapping=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.community_node_mapping = community_node_mapping if community_node_mapping else {}

    def set_community_mapping(self, mapping):
        self.community_node_mapping = mapping

    def get_nodes_in_community(self, community_id):
        return self.community_node_mapping.get(community_id, set())

    def common_neighbors_link_count(self, community_id_1, community_id_2):
        """
        Menghitung JUMLAH link penghubung langsung antara dua komunitas.
        Ini adalah implementasi untuk G.common_neighbors(Ci, Cj) dari pseudocode.
        """
        if community_id_1 == community_id_2: # Tidak membandingkan komunitas dengan dirinya sendiri
            return 0
            
        nodes_in_comm1 = self.get_nodes_in_community(community_id_1)
        nodes_in_comm2 = self.get_nodes_in_community(community_id_2)

        if not nodes_in_comm1 or not nodes_in_comm2:
            return 0 # Salah satu atau kedua komunitas tidak memiliki node atau tidak dikenal

        connecting_links_count = 0
        for node_u in nodes_in_comm1:
            # Pastikan node_u ada di graf utama
            if not self.has_node(node_u):
                continue
            for neighbor_of_u in self.neighbors(node_u):
                if neighbor_of_u in nodes_in_comm2:
                    connecting_links_count += 1
        return connecting_links_count

# --- Algorithm 2: Community Ranking ---
def algorithm_2_community_ranking(genetic_based_communities_ids, topology_graph_with_features):
    """
    Implementasi Algorithm 2 dari screenshot.

    Args:
        genetic_based_communities_ids (list): List dari ID komunitas, misal ['comm_0', 'comm_1'].
        topology_graph_with_features (GraphWithCommunityFeatures): Objek graf networkx 
                                                                   yang sudah memiliki pemetaan komunitas.
    Returns:
        dict: neighborRank, memetakan ID home community ke list tetangga terurut.
              Contoh: {'comm_0': [{'id': 'comm_1', 'rank_score': 0.5}, ...]}
    """
    C = genetic_based_communities_ids # Baris 2 dari pseudocode

    neighborDistance = {} # Struktur data seperti di pseudocode
    neighborRank = {}     # Output akhir

    # Baris 3: Calculate neighborhood distance list for each community Ci in C
    # Baris 4: for Ci in C do:
    for Ci_id in C:
        # Inisialisasi untuk home community Ci_id saat ini
        if Ci_id not in neighborDistance:
            neighborDistance[Ci_id] = {'commRank': [], 'commId': []}

        # Baris 5: for Cj in C do:
        for Cj_id in C:
            if Ci_id == Cj_id:
                continue # Lewati jika komunitasnya sama

            # Baris 6: # find common neighbors between each two communities Ci, Cj
            # Baris 7: neighborNumber = G.common_neighbors(Ci, Cj)
            # Menggunakan metode yang kita definisikan di GraphWithCommunityFeatures
            neighborNumber = topology_graph_with_features.common_neighbors_link_count(Ci_id, Cj_id)

            # Baris 8: neighborDistance[commRank][i].append ( 1 / |neighborNumber| )
            distance_score = float('inf') # Default jika tidak ada common neighbors
            if neighborNumber > 0:
                distance_score = 1.0 / neighborNumber
            
            neighborDistance[Ci_id]['commRank'].append(distance_score)

            # Baris 9: neighborDistance[commId][i].append (j)
            neighborDistance[Ci_id]['commId'].append(Cj_id)

    # Baris 10: # sort communities based on neighborhood distance
    # Baris 11: for Ci in C do:
    for Ci_id in C:
        # Ambil data untuk Ci_id saat ini
        ranks_for_ci = neighborDistance[Ci_id]['commRank']
        ids_for_ci = neighborDistance[Ci_id]['commId']

        # Gabungkan rank dan id menjadi list of dictionaries untuk sorting
        combined_list_for_ci = []
        for k in range(len(ranks_for_ci)):
            combined_list_for_ci.append({'id': ids_for_ci[k], 'rank_score': ranks_for_ci[k]})

        # Baris 12: neighborRank[i] = sort (neighborDistance[i], key = commRank, ascending order)
        sorted_neighbor_info = sorted(combined_list_for_ci, key=lambda x: x['rank_score'])
        
        neighborRank[Ci_id] = sorted_neighbor_info
        
    return neighborRank

# --- Fungsi untuk Membuat Dummy Data ---
def create_dummy_data(num_nodes=20, num_communities=4, nodes_per_community_range=(3, 7), edge_probability=0.2):
    """
    Membuat dummy topologi dan komunitas.
    """
    # 1. Buat Node
    nodes = [f"n{i}" for i in range(num_nodes)]

    # 2. Buat Komunitas (dummy assignment)
    community_node_mapping = {}
    community_ids = [f"comm_{i}" for i in range(num_communities)]
    
    assigned_nodes = set()
    for i, comm_id in enumerate(community_ids):
        community_node_mapping[comm_id] = set()
        # Ambil node secara acak untuk komunitas ini, pastikan tidak duplikat
        num_nodes_in_this_comm = random.randint(nodes_per_community_range[0], nodes_per_community_range[1])
        
        available_nodes = [n for n in nodes if n not in assigned_nodes]
        if len(available_nodes) < num_nodes_in_this_comm: # Jika node habis
            nodes_to_assign = available_nodes
        else:
            nodes_to_assign = random.sample(available_nodes, num_nodes_in_this_comm)
            
        for node in nodes_to_assign:
            community_node_mapping[comm_id].add(node)
            assigned_nodes.add(node)
            
    # Pastikan semua node ter-assign ke suatu komunitas (jika ada sisa)
    remaining_nodes = [n for n in nodes if n not in assigned_nodes]
    if remaining_nodes and community_ids:
        for node in remaining_nodes:
            # Assign ke komunitas acak
            random_comm_id = random.choice(community_ids)
            community_node_mapping[random_comm_id].add(node)

    # Filter komunitas yang mungkin kosong setelah assignment
    community_node_mapping = {k: v for k, v in community_node_mapping.items() if v}
    actual_community_ids = list(community_node_mapping.keys())


    # 3. Buat Topologi Graf (Erdos-Renyi untuk kesederhanaan)
    graph = GraphWithCommunityFeatures(community_node_mapping)
    graph.add_nodes_from(nodes) # Tambahkan semua node ke graf
    
    # Tambahkan edge di dalam komunitas (lebih padat)
    for comm_id, nodes_in_comm in community_node_mapping.items():
        node_list = list(nodes_in_comm)
        for i in range(len(node_list)):
            for j in range(i + 1, len(node_list)):
                # Peluang lebih tinggi untuk koneksi intra-komunitas
                if random.random() < edge_probability * 2: # Misal 2x lebih mungkin
                    graph.add_edge(node_list[i], node_list[j])

    # Tambahkan edge antar komunitas (lebih jarang)
    for i in range(len(actual_community_ids)):
        for j in range(i + 1, len(actual_community_ids)):
            comm1_id = actual_community_ids[i]
            comm2_id = actual_community_ids[j]
            nodes_in_comm1 = list(community_node_mapping[comm1_id])
            nodes_in_comm2 = list(community_node_mapping[comm2_id])

            # Coba buat beberapa link antar komunitas
            num_inter_links_to_try = random.randint(0, 2) # Misal, 0 sampai 2 link
            for _ in range(num_inter_links_to_try):
                if nodes_in_comm1 and nodes_in_comm2:
                    node1 = random.choice(nodes_in_comm1)
                    node2 = random.choice(nodes_in_comm2)
                    if random.random() < edge_probability: # Peluang standar
                        graph.add_edge(node1, node2)
                        
    # Pastikan graf terhubung (opsional, tapi baik untuk simulasi)
    # Jika tidak terhubung, tambahkan beberapa edge lagi untuk menghubungkannya
    if not nx.is_connected(graph) and len(graph.nodes) > 1:
        components = list(nx.connected_components(graph))
        if len(components) > 1:
            for k in range(len(components) - 1):
                node_from_comp1 = random.choice(list(components[k]))
                node_from_comp2 = random.choice(list(components[k+1]))
                graph.add_edge(node_from_comp1, node_from_comp2)

    return graph, actual_community_ids, community_node_mapping


# --- Main Execution ---
if __name__ == "__main__":
    random.seed(42) # Untuk reproduktifitas

    # 1. Buat Dummy Data
    NUM_NODES = 30
    NUM_COMMUNITIES = 5
    dummy_topology_graph, dummy_community_ids, dummy_community_map = create_dummy_data(
        num_nodes=NUM_NODES, 
        num_communities=NUM_COMMUNITIES,
        edge_probability=0.1 # Kurangi probabilitas agar tidak terlalu padat
    )
    # Set pemetaan komunitas ke objek graf kita
    dummy_topology_graph.set_community_mapping(dummy_community_map)

    print("--- Dummy Data Created ---")
    print(f"Total Nodes: {len(dummy_topology_graph.nodes())}")
    print(f"Total Edges: {len(dummy_topology_graph.edges())}")
    print(f"Community IDs: {dummy_community_ids}")
    for comm_id, nodes in dummy_community_map.items():
        print(f"  {comm_id}: {nodes}")
    print("-" * 30)

    # 2. Jalankan Algorithm 2
    # Input untuk Algoritma 2:
    genetic_based_communities_ids = dummy_community_ids # Ini adalah output dari GA (disimulasikan)
    topology_graph_with_features = dummy_topology_graph   # Graf dengan info komunitas

    print("--- Running Algorithm 2: Community Ranking ---")
    ranked_neighborhoods = algorithm_2_community_ranking(
        genetic_based_communities_ids,
        topology_graph_with_features
    )
    print("-" * 30)

    # 3. Tampilkan Hasil
    print("--- Ranked Community Neighborhoods (Output of Algorithm 2) ---")
    for home_comm_id, ranked_neighbors_list in ranked_neighborhoods.items():
        print(f"Home Community: {home_comm_id}")
        if not ranked_neighbors_list:
            print("  No neighbors found or ranked (possibly only one community or no inter-community links).")
        for neighbor_info in ranked_neighbors_list:
            print(f"  -> Neighbor: {neighbor_info['id']}, "
                  f"Distance Score: {neighbor_info['rank_score']:.4f} "
                  f"(Based on {topology_graph_with_features.common_neighbors_link_count(home_comm_id, neighbor_info['id'])} common links)")
        print("-" * 20)