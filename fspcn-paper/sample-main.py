"""Example main script demonstrating topology generation, visualization and export."""
from pathlib import Path
import random
import numpy as np

from config import *
from topology import create_topology
from visualization import visualize_layered_topology
from export import export_graph_data

def main():
    random.seed(SEED)
    np.random.seed(SEED)

    MAIN_OUTPUT_FOLDER = "topology_outputs"
    Path(MAIN_OUTPUT_FOLDER).mkdir(parents=True, exist_ok=True)

    # Create topology
    print("\n=== Creating FSPCN Topology ===")
    topology_instance = create_topology()
    graph = topology_instance.G

    # Export graph data
    print("\n=== Exporting Graph Data ===")
    export_subfolder = Path(MAIN_OUTPUT_FOLDER) / "graph_exports"
    base_export_filename = f"fspcn_topo_N{NUM_FOG_NODES}_C{NUM_COMMUNITIES}"
    export_graph_data(graph, 
                     base_filename=base_export_filename, 
                     export_folder=export_subfolder)

    # Visualize and save
    print("\n=== Generating Visualization ===")
    output_image_path = Path(RESULTS_FOLDER) / f"topology_fspcn_layers_N{NUM_FOG_NODES}_C{NUM_COMMUNITIES}.png"
    visualize_layered_topology(
        graph,
        num_communities_param=NUM_COMMUNITIES,
        title=f"Layered FSPCN Topology ({NUM_FOG_NODES} Fog Nodes, {NUM_COMMUNITIES} Communities)",
        save_path=output_image_path
    )
    
    print(f"\nScript execution completed. Generated files:")
    print(f"- Visualization: {output_image_path.resolve()}")
    print(f"- Graph exports: {export_subfolder.resolve()}")

if __name__ == "__main__":
    main()
