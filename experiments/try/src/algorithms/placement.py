import random
import networkx as nx
from collections import defaultdict
from config import config
import copy

class Placement:
    """
    Mengimplementasikan Fase 2 dari FSPCN: Community Ranking dan Application Placement.
    Menerjemahkan Algoritma 2 dan 3 dari paper.
    """
    def __init__(self, network, communities, applications, users):
        """
        Inisialisasi algoritma penempatan.

        Args:
            network (nx.Graph): Graf jaringan.
            communities (dict): Komunitas yang dihasilkan oleh GA. {comm_id: [node_list]}.
            applications (list): Daftar definisi aplikasi.
            users (dict): Definisi pengguna/sumber beban kerja.
        """
        self.network = network
        self.communities = communities
        self.applications = applications
        self.users = users.get('sources', [])
        
        self.placement_matrix = {}
        self.community_of_node = {}
        self.existing_placements = defaultdict(list)
        
        self.available_resources = {
            node: data.get('RAM', 0) 
            for node, data in self.network.nodes(data=True)
        }

        for comm_id, nodes in self.communities.items():
            for node_id in nodes:
                self.community_of_node[node_id] = comm_id

    def _rank_communities(self):
        """
        Memberi peringkat pada komunitas berdasarkan neighborhood distance.
        Implementasi dari Algoritma 2.
        """
        print("Memulai Community Ranking (Algoritma 2)...")
        ranked_neighbors = defaultdict(list)
        community_ids = list(self.communities.keys())

        for i in range(len(community_ids)):
            for j in range(i + 1, len(community_ids)):
                comm_id1 = community_ids[i]
                comm_id2 = community_ids[j]
                
                nodes1 = self.communities[comm_id1]
                nodes2 = self.communities[comm_id2]
                
                # --- PERBAIKAN DI SINI ---
                # Menghitung jumlah edge yang menghubungkan dua komunitas.
                # Ini adalah implementasi yang lebih tepat dari 'common neighbors' antar grup.
                boundary_edges_count = len(list(nx.edge_boundary(self.network, nodes1, nodes2)))
                
                # Neighborhood distance adalah invers dari jumlah koneksi antar komunitas
                neighbor_distance = 1 / (boundary_edges_count + 1e-6)
                
                ranked_neighbors[comm_id1].append({'rank': neighbor_distance, 'id': comm_id2})
                ranked_neighbors[comm_id2].append({'rank': neighbor_distance, 'id': comm_id1})

        # Urutkan daftar tetangga untuk setiap komunitas berdasarkan peringkat
        for comm_id in ranked_neighbors:
            ranked_neighbors[comm_id].sort(key=lambda x: x['rank'])
            
        print("Community Ranking selesai.")
        return ranked_neighbors

    def _try_place_app_in_community(self, app, community_nodes):
        """
        Mencoba menempatkan semua layanan dari satu aplikasi ke dalam node-node 
        di satu komunitas. Menggunakan pendekatan greedy First-Fit.
        """
        services_to_place = app['module']
        temp_placement = {}
        
        # Buat salinan sumber daya yang tersedia untuk simulasi penempatan ini
        temp_community_resources = {node_id: self.available_resources[node_id] for node_id in community_nodes}

        for service in services_to_place:
            service_placed = False
            required_ram = service.get('RAM', 1)
            
            # Urutkan node di komunitas berdasarkan sisa RAM (opsional, tapi bisa meningkatkan peluang)
            sorted_nodes = sorted(community_nodes, key=lambda n: temp_community_resources.get(n, 0), reverse=True)

            for node_id in sorted_nodes:
                if temp_community_resources.get(node_id, 0) >= required_ram:
                    # Di sini kita hanya mencatat penempatan sementara
                    if service['name'] not in temp_placement:
                        temp_placement[service['name']] = []
                    temp_placement[service['name']].append(node_id)
                    
                    temp_community_resources[node_id] -= required_ram
                    service_placed = True
                    break 
            
            if not service_placed:
                return None # Gagal menempatkan satu service, batalkan untuk community ini

        return temp_placement

    def run(self):
        """
        Menjalankan proses penempatan aplikasi.
        Implementasi dari Algoritma 3.
        """
        ranked_neighbors = self._rank_communities()

        print("Memulai Application Placement (Algoritma 3)...")
        
        sorted_apps = sorted(self.applications, key=lambda x: x['deadline'])
        
        app_requests = defaultdict(list)
        for user in self.users:
            app_requests[user['app']].append(user)

        for app in sorted_apps:
            app_id = app['name']
            requests = app_requests.get(app_id, [])
            
            if not requests: 
                continue

            # Proses penempatan hanya perlu dilakukan sekali per aplikasi
            # Kita asumsikan satu permintaan representatif sudah cukup untuk memicu penempatan
            req = requests[0]
            requester_gateway_id = req['id_resource']
            
            home_community_id = self.community_of_node.get(requester_gateway_id)
            if home_community_id is None:
                continue

            # Cek apakah aplikasi ini sudah ditempatkan karena permintaan lain
            # Ini adalah penyederhanaan; kita anggap penempatan app bersifat global
            if any(s['name'] in self.placement_matrix for s in app['module']):
                continue

            placement_done = False
            # Coba tempatkan di home community
            placement_result = self._try_place_app_in_community(app, self.communities[home_community_id])
            
            if placement_result:
                placement_done = True
            else:
                # Gagal, coba di neighbor communities
                for neighbor in ranked_neighbors.get(home_community_id, []):
                    if neighbor['rank'] <= config.RANK_THRESHOLD:
                        neighbor_id = neighbor['id']
                        neighbor_nodes = self.communities[neighbor_id]
                        
                        placement_result = self._try_place_app_in_community(app, neighbor_nodes)
                        
                        if placement_result:
                            placement_done = True
                            break # Berhasil, keluar dari loop neighbor
            
            # Jika penempatan berhasil (di home atau neighbor), update state global
            if placement_done and placement_result:
                for service_name, node_ids in placement_result.items():
                    if service_name not in self.placement_matrix:
                        self.placement_matrix[service_name] = []
                    
                    # Update matriks penempatan global
                    self.placement_matrix[service_name].extend(node_ids)
                    
                    # Update sumber daya yang tersedia
                    service_ram = next(s['RAM'] for s in app['module'] if s['name'] == service_name)
                    for node_id in node_ids:
                         self.available_resources[node_id] -= service_ram
        
        print("Application Placement selesai.")
        return self.placement_matrix
