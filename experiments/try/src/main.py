import os
import json
import networkx as nx

# Impor fungsi generator dari modul yang relevan
from src.generators.network_generator import generate_network
from src.generators.app_generator import generate_applications
from src.generators.user_generator import generate_users
from config import config

# Tentukan path untuk menyimpan data yang dihasilkan
DATA_PATH = "data"

def save_to_json(data, filename):
    """Fungsi pembantu untuk menyimpan data ke file JSON."""
    filepath = os.path.join(DATA_PATH, filename)
    try:
        with open(filepath, 'w') as f:
            # Menggunakan indent=4 agar file JSON mudah dibaca
            json.dump(data, f, indent=4)
        print(f"Berhasil menyimpan {filename} ke {filepath}")
    except IOError as e:
        print(f"Gagal menyimpan {filename}: {e}")

def main():
    """
    Fungsi utama untuk menjalankan proses pembuatan data eksperimen.
    """
    print("--- Memulai Proses Pembuatan Data Eksperimen ---")

    # 1. Pastikan direktori 'data' ada
    if not os.path.exists(DATA_PATH):
        os.makedirs(DATA_PATH)
        print(f"Direktori '{DATA_PATH}/' telah dibuat.")

    # 2. Buat Topologi Jaringan
    print("\n1. Membuat topologi jaringan...")
    network_graph = generate_network()
    
    # Konversi objek graf NetworkX ke format dictionary yang bisa di-serialize
    # agar sesuai dengan struktur networkDefinition.json
    network_data_for_json = nx.node_link_data(network_graph)
    save_to_json(network_data_for_json, "networkDefinition.json")

    # 3. Buat Definisi Aplikasi
    # Kita akan membuat 20 aplikasi untuk skenario ini
    num_apps_to_generate = 20
    print(f"\n2. Membuat definisi untuk {num_apps_to_generate} aplikasi...")
    app_definitions = generate_applications(num_apps=num_apps_to_generate)
    save_to_json(app_definitions, "appDefinition.json")

    # 4. Buat Definisi Pengguna (Sumber Beban Kerja)
    # Fungsi ini memerlukan graf jaringan dan jumlah aplikasi
    print("\n3. Membuat definisi pengguna (workload)...")
    generate_users(network=network_graph, num_apps=num_apps_to_generate)

    print("\n--- Proses Pembuatan Data Selesai ---")
    print("File 'networkDefinition.json', 'appDefinition.json', dan 'usersDefinition.json' telah dibuat di folder 'data/'.")

if __name__ == "__main__":
    # Jalankan fungsi utama
    main()
