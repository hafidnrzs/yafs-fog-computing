import networkx as nx
import random

# --- Konfigurasi Dasar ---
NUM_FOG_NODES = 100
NUM_COMMUNITIES = 10

# --- 1. Definisi Kromosom (Hardcoded Mock) ---
# Kromosom adalah list di mana index merepresentasikan ID fog node (setelah di-map)
# dan nilainya adalah ID komunitas.
# Kita akan menggunakan ID komunitas 1 hingga NUM_COMMUNITIES.
# Fog node ID akan kita representasikan sebagai integer 0 hingga 99 untuk kemudahan indexing list.
# (f1 -> 0, f2 -> 1, ..., f100 -> 99)

# Membuat mock kromosom yang sudah "terbentuk" (mirip sisi kanan gambar)
# Kita akan bagi node ke dalam komunitas secara berurutan untuk mock ini.
# Misal, node 0-9 ke komunitas 1, node 10-19 ke komunitas 2, dst.
chromosome = [0] * NUM_FOG_NODES
nodes_per_community_ideal = NUM_FOG_NODES // NUM_COMMUNITIES # Hasilnya 10

for i in range(NUM_FOG_NODES):
    # ID Komunitas dari 1 hingga NUM_COMMUNITIES
    community_id = (i // nodes_per_community_ideal) + 1
    # Pastikan tidak melebihi NUM_COMMUNITIES (penting jika NUM_FOG_NODES tidak habis dibagi NUM_COMMUNITIES)
    if community_id > NUM_COMMUNITIES:
        community_id = NUM_COMMUNITIES
    chromosome[i] = community_id

# Jika ingin variasi yang tidak terlalu seragam, kita bisa atur manual atau dengan sedikit random:
# Contoh variasi (opsional, untuk mock yang lebih "berantakan" tapi tetap terstruktur):
# random.seed(42) # untuk reproduktifitas
# community_assignments = []
# for _ in range(NUM_FOG_NODES):
#     community_assignments.append(random.randint(1, NUM_COMMUNITIES))
# chromosome = community_assignments
# Namun, untuk mock awal, pembagian blok lebih jelas. Yang di atas adalah contoh terstruktur.

print(f"Mock Chromosome (Node Index -> Community ID):")
for i in range(20): # Tampilkan 20 pertama sebagai contoh
    print(f"  Fog Node Index {i} (maps to f{i+1}) -> Community CV{chromosome[i]}")
print(f"  ...")
print(f"  Fog Node Index {NUM_FOG_NODES-1} (maps to f{NUM_FOG_NODES}) -> Community CV{chromosome[NUM_FOG_NODES-1]}")
print(f"\nTotal nodes: {len(chromosome)}")
# Verifikasi jumlah node per komunitas (jika menggunakan pembagian blok)
counts = {i:0 for i in range(1, NUM_COMMUNITIES + 1)}
for cid in chromosome:
    counts[cid] +=1
print(f"Node counts per community: {counts}")


# --- 2. Pembentukan Graf Fog Nodes dengan NetworkX dan Atribut Komunitas ---
G = nx.Graph()

# Tambahkan fog nodes ke graf. Kita akan menggunakan nama node f1, f2, ...
# dan menyimpan mapping ke komunitas sebagai atribut node.
for i in range(NUM_FOG_NODES):
    node_id_str = f"f{i+1}" # Nama node seperti di gambar f1, f2, ...
    assigned_community_id = chromosome[i] # Ambil dari kromosom yang kita buat
    
    # Tambahkan node dengan atribut komunitas
    G.add_node(node_id_str, community=f"CV{assigned_community_id}")

print(f"\nInformasi Graf NetworkX (contoh beberapa node):")
for i in range(5): # Tampilkan 5 node pertama
    node_name = f"f{i+1}"
    print(f"  Node {node_name}: Attributes {G.nodes[node_name]}")

print(f"\nTotal nodes di graf: {G.number_of_nodes()}")

# --- 3. (Untuk Proses Selanjutnya) Mengakses Anggota Komunitas ---
# Anda mungkin memerlukan fungsi untuk mendapatkan semua node dalam komunitas tertentu

def get_nodes_in_community(graph, community_label_str):
    """
    Mengembalikan list node yang tergabung dalam community_label_str.
    community_label_str contohnya "CV1", "CV2", dll.
    """
    return [node for node, data in graph.nodes(data=True) if data.get('community') == community_label_str]

# Contoh penggunaan:
print("\nContoh mengambil anggota komunitas:")
community1_members = get_nodes_in_community(G, "CV1")
print(f"Anggota Komunitas CV1 (maks 10 pertama): {community1_members[:10]}")

community5_members = get_nodes_in_community(G, "CV5")
print(f"Anggota Komunitas CV5 (maks 10 pertama): {community5_members[:10]}")

if NUM_COMMUNITIES >= 10:
    community10_members = get_nodes_in_community(G, "CV10")
    print(f"Anggota Komunitas CV10 (maks 10 pertama): {community10_members[:10]}")

# Variabel `G` (graf NetworkX) dan `chromosome` (list mapping node ke komunitas)
# sekarang siap digunakan untuk tahap selanjutnya.
# `G.nodes[node_id]['community']` akan memberikan Anda ID komunitas dari sebuah node.