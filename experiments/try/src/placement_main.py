import json
import os
import random
import networkx as nx

# Impor modul-modul lain dari proyek
from config import config
from src.generators.network_generator import generate_network
from src.generators.app_generator import generate_applications
from src.generators.user_generator import generate_users
from src.algorithms.genetic_algorithm import GeneticAlgorithm
from src.algorithms.placement import Placement
from src.evaluation import metrics

RESULTS_PATH = "results"
DATA_PATH = "data"

def save_to_json(data, filename, path):
    """Fungsi pembantu untuk menyimpan data ke file JSON."""
    filepath = os.path.join(path, filename)
    try:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"Berhasil menyimpan {filename} ke {filepath}")
    except IOError as e:
        print(f"Gagal menyimpan {filename}: {e}")

# --- FUNGSI BARU UNTUK KONVERSI FORMAT ---
def reformat_placement_for_yafs(placement_result, app_definitions):
    """
    Mengubah format hasil penempatan dari FSPCN ke format yang diharapkan
    oleh kelas JSONPlacement dari YAFS.
    """
    # Buat peta dari nama modul ke nama aplikasi untuk pencarian cepat
    module_to_app_map = {}
    for app in app_definitions:
        for module in app['module']:
            module_to_app_map[module['name']] = app['name']

    initial_allocation_list = []
    for module_name, node_ids in placement_result.items():
        app_name = module_to_app_map.get(module_name, "unknown_app")
        for node_id in node_ids:
            initial_allocation_list.append({
                "module_name": module_name,
                "app": app_name,
                "id_resource": node_id
            })
    
    return {"initialAllocation": initial_allocation_list}


def run_single_experiment(num_apps, population_size, generations):
    """
    Menjalankan satu siklus penuh eksperimen untuk satu skenario.
    """
    print("\n" + "#"*60)
    print(f"### MENJALANKAN EKSPERIMEN: {num_apps} Aplikasi ###")
    print("#"*60 + "\n")

    print("--- [TAHAP 1] Membuat Definisi Lingkungan ---")
    network_graph = generate_network()
    app_definitions = generate_applications(num_apps=num_apps)
    user_definitions = generate_users(network=network_graph, num_apps=num_apps)
    
    network_data_raw = nx.node_link_data(network_graph, edges="links")
    remapped_links = [{'s': link.pop('source'), 'd': link.pop('target'), **link} for link in network_data_raw.get("links", [])]
    network_data_for_json = {"entity": network_data_raw.get("nodes", []), "link": remapped_links}

    save_to_json(network_data_for_json, "networkDefinition.json", DATA_PATH)
    save_to_json(app_definitions, "appDefinition.json", DATA_PATH)
    
    print("\n--- [TAHAP 2] FSPCN - Fase 1: Pembuatan Komunitas (GA) ---")
    ga = GeneticAlgorithm(network_graph=network_graph, population_size=population_size, generations=generations)
    best_communities = ga.run()
    save_to_json(best_communities, f"communities_result_{num_apps}apps.json", RESULTS_PATH)

    print("\n--- [TAHAP 3] FSPCN - Fase 2: Penempatan Aplikasi ---")
    placement_algorithm = Placement(network=network_graph, communities=best_communities, applications=app_definitions, users=user_definitions)
    final_placement = placement_algorithm.run()
    
    # --- PERBAIKAN DI SINI ---
    # Ubah format hasil penempatan sebelum menyimpannya
    yafs_compatible_placement = reformat_placement_for_yafs(final_placement, app_definitions)
    save_to_json(yafs_compatible_placement, f"placement_result_{num_apps}apps.json", RESULTS_PATH)
    
    print("\n--- [TAHAP 4] Evaluasi Hasil ---")
    evaluation_results = {}
    evaluation_results['placement_metrics'] = metrics.calculate_placement_metrics(final_placement, network_graph, app_definitions, config)
    evaluation_results['availability'] = metrics.calculate_availability_metric(final_placement, network_graph, app_definitions, user_definitions['sources'], config)
    evaluation_results['delay_metrics'] = metrics.calculate_delay_metrics(final_placement, network_graph, app_definitions, user_definitions['sources'], config)
    metrics.print_evaluation_summary(evaluation_results)
    
    return evaluation_results


def main():
    """
    Fungsi utama untuk menjalankan skenario eksperimen.
    """
    for path in [DATA_PATH, RESULTS_PATH]:
        if not os.path.exists(path):
            os.makedirs(path)

    random.seed(config.RANDOM_SEED)
    run_single_experiment(num_apps=20, population_size=50, generations=100)


if __name__ == "__main__":
    main()
