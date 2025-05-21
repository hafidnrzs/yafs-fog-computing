from Simulation.Topology.topology import create_topology, export_topology_to_csv
from Simulation.ComunityGA.comunityGA import genetic_algorithm
from Simulation.Topology.topologyGA import create_topology_community, export_topology_ga_to_csv
from visualization.visualization import (
    visualize_layered_topology,
    visualize_topology_ga_with_communities,
    animate_service_placement,
    animate_routes_on_topology,
    animate_request_flow
)
from Simulation.Application.Application import generate_random_application
from Simulation.Placement.Placement import ga_service_placement, apply_placement_to_graph
from Simulation.Selection.Selection import select_routes
from Simulation.Population.Population import generate_population
from Simulation.Sim.sim_core import run_simulation
from Simulation.Evaluasi.Evaluasi import evaluate_simulation
import networkx as nx
from pathlib import Path
import time


def main():
    # Buat folder utama untuk hasil
    folder_results = Path("./results/")
    folder_results.mkdir(parents=True, exist_ok=True)

    # Buat subfolder untuk PNG, CSV, dan GEXF
    folder_png = folder_results / "png"
    folder_csv = folder_results / "csv"
    folder_gexf = folder_results / "gexf"
    folder_png.mkdir(parents=True, exist_ok=True)
    folder_csv.mkdir(parents=True, exist_ok=True)
    folder_gexf.mkdir(parents=True, exist_ok=True)

    start_time = time.time()

    # 1. Buat topologi dasar
    print("Step 1: Creating base topology...")
    topology = create_topology()

    # 2. Simpan topologi ke file CSV
    print("Exporting base topology to CSV...")
    export_topology_to_csv(
        topology.G,
        folder_path=folder_csv,  # Simpan ke folder CSV
        node_filename="topology_nodes.csv",
        edge_filename="topology_edges.csv"
    )
    print(f"Base topology exported to {folder_csv}/topology_nodes.csv and {folder_csv}/topology_edges.csv")

    # 3. Simpan topologi dasar ke file GEXF
    nx.write_gexf(topology.G, folder_gexf / "base_topology.gexf")
    print(f"Base topology saved to {folder_gexf}/base_topology.gexf")

    # 4. Visualisasikan topologi dasar
    visualize_layered_topology(
        topology.G,
        title="Base Topology Visualization",
        save_path=folder_png / "base_topology_visualization.png"  # Simpan ke folder PNG
    )
    print(f"Base topology visualization saved to {folder_png}/base_topology_visualization.png")
    print("========================================================================================================================")
    # 5. Jalankan Community GA untuk menentukan komunitas
    print("Step 2: Running Community GA...")
    num_communities = 10  # Jumlah komunitas yang diinginkan
    best_chromosome = genetic_algorithm(topology.G, num_communities)
    print(f"Best chromosome from Community GA: {best_chromosome}")

    # 6. Perbarui topologi dengan hasil Community GA
    print("Updating topology with community assignments...")
    updated_graph = create_topology_community(topology.G, best_chromosome)

    # 7. Simpan topologi yang diperbarui ke file GEXF
    nx.write_gexf(updated_graph, folder_gexf / "community_topology.gexf")
    print(f"Community topology saved to {folder_gexf}/community_topology.gexf")

    # 8. Simpan topologi yang diperbarui ke file CSV
    print("Exporting updated topology to CSV...")
    export_topology_ga_to_csv(
        updated_graph,
        folder_path=folder_csv,  # Simpan ke folder CSV
        node_filename="community_nodes.csv",
        edge_filename="community_edges.csv"
    )
    print(f"Updated topology exported to {folder_csv}/community_nodes.csv and {folder_csv}/community_edges.csv")

    # 9. Visualisasikan Topology GA dengan warna komunitas
    visualize_topology_ga_with_communities(
        updated_graph,
        title="Topology GA with Communities",
        save_path=folder_png / "topology_ga_with_communities.png"  # Simpan ke folder PNG
    )
    print(f"Topology GA with Communities visualization saved to {folder_png}/topology_ga_with_communities.png")
    print("========================================================================================================================")
    # 10. Generate Application & Service
    print("Step 3: Generating random application and services...")
    application = generate_random_application()
    services = application.to_dict_list()
    print(f"Application deadline: {application.deadline} ms")
    print(f"Services: {[svc['name'] for svc in services]}")
    print("========================================================================================================================")
    # 11. Placement dengan GA pada topology komunitas
    print("Step 4: Running GA-based service placement on community topology...")
    placement = ga_service_placement(updated_graph, services)
    print("Service placement result:", placement)
    apply_placement_to_graph(updated_graph, placement)
    print("Service placement applied to graph.")
    animate_service_placement(
        updated_graph,  # graph topology komunitas yang sudah ada placement
        services,       # list of dict service
        placement,      # dict mapping service_name -> node_name
        save_path=folder_png / "service_placement.gif")
    print("========================================================================================================================")
    print("Step 5 : Selecting routes between services...")
    service_pairs = []
    for i in range(len(services)-1):
        service_pairs.append((services[i]['name'], services[i+1]['name']))

    routes = select_routes(updated_graph, placement, service_pairs, routing="shortest")
    print("Selected routes between services:")
    for k, v in routes.items():
        print(f"{k}: {v}")
    animate_routes_on_topology(
        updated_graph,
        routes,
        save_path=folder_png / "routes_on_topology.gif"
    )
    print("========================================================================================================================")
    print("Step 6 : Generating population (request generators)...")
    population = generate_population(services, num_sources=3)
    print("Population (request generators):")
    for p in population:
        print(p) 
    
    print("========================================================================================================================")
    print("Step 7 : Running simulation (request flow & delay calculation)...")
    sim_results = run_simulation(
        updated_graph,
        population,
        placement,
        routes,
        services,
        service_pairs
    )
    print("Simulation results (per population entity):")
    for r in sim_results:
        print(r)
    animate_request_flow(
        updated_graph,
        sim_results,
        save_path=folder_png / "request_flow.gif"
    )    
        
        # ===================== EVALUASI ==========================
    print("========================================================================================================================")
    print("Step 8 : Evaluation (latency, deadline miss, etc)...")
    eval_result = evaluate_simulation(sim_results, deadline_ms=application.deadline)
    print("Evaluation result:")
    for k, v in eval_result.items():
        print(f"{k}: {v}")

    print("========================================================================================================================")
    print(f"\n--- {time.time() - start_time} seconds ---")
    print("Simulation Done!")


if __name__ == "__main__":
    main()