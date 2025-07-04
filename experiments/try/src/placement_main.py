import os
import json
import networkx as nx
import random

# Impor semua modul yang diperlukan dengan path yang benar
from config import config
from src.generators.network_generator import generate_network
from src.generators.app_generator import generate_applications
from src.generators.user_generator import generate_users
from src.algorithms.genetic_algorithm import GeneticAlgorithm
from src.algorithms.placement import Placement
from src.evaluation import metrics

# Tentukan path untuk menyimpan data yang dihasilkan
DATA_PATH = "data"
RESULTS_PATH = "results"

def save_to_json(data, filename, path):
    """Fungsi pembantu untuk menyimpan data ke file JSON."""
    filepath = os.path.join(path, filename)
    try:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"Berhasil menyimpan {filename} ke {filepath}")
    except IOError as e:
        print(f"Gagal menyimpan {filename}: {e}")

def run_single_experiment(num_apps, population_size, generations):
    """
    Menjalankan satu siklus penuh eksperimen untuk satu skenario.
    """
    print("\n" + "#"*60)
    print(f"### MENJALANKAN EKSPERIMEN: {num_apps} Aplikasi ###")
    print("#"*60 + "\n")

    # --- TAHAP 1: GENERATION ---
    print("--- [TAHAP 1] Membuat Definisi Lingkungan ---")
    network_graph = generate_network()
    app_definitions = generate_applications(num_apps=num_apps)
    user_definitions = generate_users(network=network_graph, num_apps=num_apps)
    
    # --- PERBAIKAN DI SINI ---
    # 1. Konversi graf ke dictionary, hilangkan warning dengan menambahkan `edges="links"`
    network_data_raw = nx.node_link_data(network_graph, edges="links")
    
    # 2. Ubah struktur dictionary agar sesuai dengan format yang diharapkan
    #    'nodes' -> 'entity'
    #    'links' -> 'link'
    #    'source'/'target' -> 's'/'d' di dalam setiap link
    remapped_links = []
    for link in network_data_raw.get("links", []):
        new_link = {
            's': link.pop('source'),
            'd': link.pop('target'),
            **link  # Tambahkan sisa atribut (PR, BW, dll)
        }
        remapped_links.append(new_link)

    network_data_for_json = {
        "entity": network_data_raw.get("nodes", []),
        "link": remapped_links
    }
    # --- AKHIR PERBAIKAN ---

    save_to_json(network_data_for_json, "networkDefinition.json", DATA_PATH)
    save_to_json(app_definitions, "appDefinition.json", DATA_PATH)
    
    print("\n--- [TAHAP 2] FSPCN - Fase 1: Pembuatan Komunitas (GA) ---")
    ga = GeneticAlgorithm(
        network_graph=network_graph,
        population_size=population_size,
        generations=generations
    )
    best_communities = ga.run()
    save_to_json(best_communities, f"communities_result_{num_apps}apps.json", RESULTS_PATH)

    print("\n--- [TAHAP 3] FSPCN - Fase 2: Penempatan Aplikasi ---")
    placement_algorithm = Placement(
        network=network_graph,
        communities=best_communities,
        applications=app_definitions,
        users=user_definitions
    )
    final_placement = placement_algorithm.run()
    save_to_json(final_placement, f"placement_result_{num_apps}apps.json", RESULTS_PATH)
    
    print("\n--- [TAHAP 4] Evaluasi Hasil ---")
    evaluation_results = {}
    
    # Hitung metrik yang bisa dihitung secara statis
    evaluation_results['placement_metrics'] = metrics.calculate_placement_metrics(final_placement, network_graph, app_definitions, config)
    evaluation_results['availability'] = metrics.calculate_availability_metric(final_placement, network_graph, app_definitions, user_definitions['sources'], config)
    evaluation_results['delay_metrics'] = metrics.calculate_delay_metrics(final_placement, network_graph, app_definitions, user_definitions['sources'], config)

    # Cetak ringkasan evaluasi
    metrics.print_evaluation_summary(evaluation_results)


def main():
    """
    Fungsi utama untuk menjalankan skenario eksperimen.
    """
    # Pastikan direktori ada
    for path in [DATA_PATH, RESULTS_PATH]:
        if not os.path.exists(path):
            os.makedirs(path)

    # Atur seed acak untuk reproducibility
    random.seed(config.RANDOM_SEED)
    
    # Jalankan satu skenario eksperimen (misal: 20 aplikasi)
    # Parameter GA bisa disesuaikan di sini
    run_single_experiment(num_apps=20, population_size=50, generations=100)
    
    # Anda bisa menambahkan loop di sini untuk menjalankan beberapa skenario
    # for num_apps in [10, 20, 40, 60, 80]:
    #     run_single_experiment(num_apps=num_apps, population_size=50, generations=100)


if __name__ == "__main__":
    main()
