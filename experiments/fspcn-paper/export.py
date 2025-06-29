"""Functions for exporting graph data to various formats."""
import pandas as pd
import networkx as nx
from pathlib import Path

def export_graph_data(graph_nx, base_filename="topology_export", export_folder="."):
    """
    Mengekspor data graf NetworkX ke format GEXF dan CSV.

    :param graph_nx: Objek graf NetworkX yang akan diekspor.
    :param base_filename: Nama dasar untuk file output (tanpa ekstensi).
    :param export_folder: Folder tempat menyimpan file output.
    """
    Path(export_folder).mkdir(parents=True, exist_ok=True)
    print(f"\nExporting graph data to folder: {Path(export_folder).resolve()}")

    # Export to GEXF
    gexf_path = Path(export_folder) / f"{base_filename}.gexf"
    try:
        nx.write_gexf(graph_nx, gexf_path, version="1.2draft")
        print(f"  Graf berhasil diekspor ke: {gexf_path}")
    except Exception as e:
        print(f"  Error saat mengekspor ke GEXF: {e}")
        print("    Pastikan semua atribut node/edge memiliki tipe data sederhana (string, int, float, bool).")
        print("    Atribut list/dict mungkin perlu di-flatten atau di-stringifikasi.")

    # Export Node List CSV
    nodes_data = []
    for node, attrs in graph_nx.nodes(data=True):
        node_info = {'node_id': node}
        node_info.update(attrs)
        nodes_data.append(node_info)
    
    nodes_df = pd.DataFrame(nodes_data)
    if 'node_id' in nodes_df.columns:
        cols = ['node_id'] + [col for col in nodes_df.columns if col != 'node_id']
        nodes_df = nodes_df[cols]

    nodes_csv_path = Path(export_folder) / f"{base_filename}_nodes.csv"
    try:
        nodes_df.to_csv(nodes_csv_path, index=False)
        print(f"  Node list berhasil diekspor ke: {nodes_csv_path}")
    except Exception as e:
        print(f"  Error saat mengekspor node list ke CSV: {e}")

    # Export Edge List CSV
    edges_data = []
    for u, v, attrs in graph_nx.edges(data=True):
        edge_info = {'source': u, 'target': v}
        edge_info.update(attrs)
        edges_data.append(edge_info)

    edges_df = pd.DataFrame(edges_data)
    if 'source' in edges_df.columns and 'target' in edges_df.columns:
        cols = ['source', 'target'] + [col for col in edges_df.columns if col not in ['source', 'target']]
        edges_df = edges_df[cols]
    
    edges_csv_path = Path(export_folder) / f"{base_filename}_edges.csv"
    try:
        edges_df.to_csv(edges_csv_path, index=False)
        print(f"  Edge list berhasil diekspor ke: {edges_csv_path}")
    except Exception as e:
        print(f"  Error saat mengekspor edge list ke CSV: {e}")
