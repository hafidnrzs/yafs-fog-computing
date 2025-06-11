# Algoritma 2 - community ranking

import networkx as nx
import random # For example usage
from typing import List, Dict, Set, Any, Union

class GACommunityRankerStrict:

    def __init__(self, graph: nx.Graph):
        if not isinstance(graph, nx.Graph):
            raise TypeError("Input 'graph' must be a networkx.Graph object.")
        self.graph: nx.Graph = graph
        self._all_nodes_in_graph: Set[Any] = set(self.graph.nodes())

    def _get_common_neighbors_count(self, community_i_nodes: List[Any], community_j_nodes: List[Any]) -> int:
        if not community_i_nodes or not community_j_nodes:
            return 0
        valid_c_i_nodes = [node for node in community_i_nodes if node in self._all_nodes_in_graph]
        valid_c_j_nodes = [node for node in community_j_nodes if node in self._all_nodes_in_graph]
        if not valid_c_i_nodes or not valid_c_j_nodes:
            return 0
            
        common_neighbor_nodes_set: Set[Any] = set()
        for k_node_id in self._all_nodes_in_graph:
            is_connected_to_c_i = any(self.graph.has_edge(k_node_id, c_i_node) for c_i_node in valid_c_i_nodes)
            if not is_connected_to_c_i:
                continue
            is_connected_to_c_j = any(self.graph.has_edge(k_node_id, c_j_node) for c_j_node in valid_c_j_nodes)
            if is_connected_to_c_j:
                common_neighbor_nodes_set.add(k_node_id)
        return len(common_neighbor_nodes_set)

    def rank_communities(
        self, 
        # Input: genetic based communities (C)
        communities_map: Dict[Union[int, str], List[Any]]
    ) -> Dict[Union[int, str], List[Dict[str, Union[float, Any]]]]:
        
        # Corresponds to `neighborRank` in the pseudocode's final state (line 12).
        output_neighbor_rank: Dict[Union[int, str], List[Dict[str, Union[float, Any]]]] = {}
        
        # Algorithm 2, Line 2: C <- Communities resulted from genetic algorithm
        active_community_ids: List[Union[int, str]] = [
            comm_id for comm_id, nodes in communities_map.items() if nodes
        ]
        
        if not active_community_ids:
            print("Warning: No active (non-empty) communities found in `communities_map`.")
            return {}

        for i_idx, home_comm_id_ci in enumerate(active_community_ids): 
            home_community_nodes: List[Any] = communities_map[home_comm_id_ci]
            
            neighbor_distance_for_ci: List[Tuple[float, Any]] = []

            # Algorithm 2, Line 5: for C_j in C do:
            for j_idx, neighbor_comm_id_cj in enumerate(active_community_ids): 
                if home_comm_id_ci == neighbor_comm_id_cj: 
                    continue 

                neighbor_community_nodes: List[Any] = communities_map[neighbor_comm_id_cj]
                
                # Algorithm 2, Line 7: neighborNumber = G.common_neighbors(C_i, C_j)
                num_common_neighbors: int = self._get_common_neighbors_count(
                    home_community_nodes,
                    neighbor_community_nodes
                )
                # Algorithm 2, Line 8: neighborDistance[commRank][i].append(1 / |neighborNumber|)
                distance_score: float = 1.0 / (1.0 + num_common_neighbors)
                # This prepares for line 9: neighborDistance[commId][i].append(j)
                neighbor_distance_for_ci.append((distance_score, neighbor_comm_id_cj))
            
            # Algorithm 2, Lines 10, 11, 12: # sort communities based on neighborhood distance
            sorted_neighbors_for_ci: List[Tuple[float, Any]] = sorted(
                neighbor_distance_for_ci,
                key=lambda item: item[0] # Sort by distance_score (commRank)
            )
            
            # Transform the sorted list into the desired output format for `neighborRank[i]`
            output_neighbor_rank[home_comm_id_ci] = [
                {'neighbor_comm_id': neighbor_id, 'commRank_score': score}
                for score, neighbor_id in sorted_neighbors_for_ci
            ]
            
        return output_neighbor_rank

    @staticmethod
    def transform_ga_chromosome_to_communities_map(
        best_chromosome: List[int],
        num_nodes_in_graph: int, 
        num_nominal_communities: int 
    ) -> Dict[int, List[int]]:
        if not isinstance(best_chromosome, list):
            print("Error transforming chromosome: `best_chromosome` is not a list.")
            return {}
        if len(best_chromosome) != num_nodes_in_graph:
            print("Error transforming chromosome: Length mismatch with graph nodes.")
            return {}
        
        # Initialize map with all possible community IDs (1-based)
        communities_map: Dict[int, List[int]] = {
            i: [] for i in range(1, num_nominal_communities + 1)
        }
        
        for node_id, assigned_comm_id in enumerate(best_chromosome):
            if not (1 <= assigned_comm_id <= num_nominal_communities):
                print(f"Warning transforming chromosome: Node {node_id} has invalid community ID {assigned_comm_id}. Skipping.")
                continue
            communities_map[assigned_comm_id].append(node_id)
            
        # Filter out communities that ended up empty.
        active_communities_map = {k: v for k, v in communities_map.items() if v}
        if not active_communities_map:
            print("Warning transforming chromosome: No active communities formed.")
        return active_communities_map


# Example usage:
if __name__ == "__main__":
    # 1. Create an example graph (network topology)
    NUM_NODES_EXAMPLE = 10
    example_graph = nx.erdos_renyi_graph(n=NUM_NODES_EXAMPLE, p=0.4, seed=42) 
    print(f"Example graph: {NUM_NODES_EXAMPLE} nodes, {example_graph.number_of_edges()} edges.")

    # 2. Output from GA_community.py
    best_chromosome_from_ga: List[int] = [3, 2, 3, 3, 2, 1, 1, 1, 2, 2]
    # Determine num_nominal_communities from the chromosome or have it as a known parameter
    # For this example, it's 3 since max ID is 3.
    num_nominal_communities_example = 0
    if best_chromosome_from_ga:
        num_nominal_communities_example = max(best_chromosome_from_ga) if best_chromosome_from_ga else 0
    
    if num_nominal_communities_example == 0:
        print("Error: Cannot determine number of nominal communities from GA output.")
        exit()

    # 3. Transform GA chromosome to `communities_map` (Input 'C' for Algorithm 2)
    # This uses the static helper method for clarity.
    communities_map_c: Dict[int, List[int]] = \
        GACommunityRankerStrict.transform_ga_chromosome_to_communities_map(
            best_chromosome_from_ga,
            NUM_NODES_EXAMPLE,
            num_nominal_communities_example
    )

    print("\nInput 'C' (Communities Map derived from GA chromosome):")
    if communities_map_c:
        for comm_id, nodes in communities_map_c.items():
            print(f"  Community {comm_id}: Nodes {nodes}")
    else:
        print("  Failed to create a valid communities map from GA output. Exiting.")
        exit()

    # 4. Initialize the GACommunityRankerStrict with the 'topology'
    ranker_instance = GACommunityRankerStrict(graph=example_graph)

    # 5. Run the community ranking algorithm (Algorithm 2)
    # Output: List of ranked communities
    ranked_lists_output: Dict[Union[int, str], List[Dict[str, Union[float, Any]]]] = \
        ranker_instance.rank_communities(communities_map=communities_map_c)

    # 6. Display the ranked results (Output of Algorithm 2, `neighborRank`)
    print("\n--- Algorithm 2: Community Ranking Output (`neighborRank`) ---")
    if ranked_lists_output:
        for home_comm_id_i, ranked_neighbors_list_for_i in ranked_lists_output.items():
            print(f"\n  Ranking for Home Community C_i = '{home_comm_id_i}': (neighborRank[{home_comm_id_i}])")
            if ranked_neighbors_list_for_i:
                # The list is already sorted by 'commRank_score'
                for rank_idx, neighbor_data in enumerate(ranked_neighbors_list_for_i):
                    # neighbor_data is {'neighbor_comm_id': id_of_Cj, 'commRank_score': score}
                    print(f"    {rank_idx+1}. Neighbor Community C_j = '{neighbor_data['neighbor_comm_id']}' "
                          f"-> Distance (commRank): {neighbor_data['commRank_score']:.4f}")
            else:
                print("      (No other active communities to rank against).")
    else:
        print("  No ranking results produced. Check input 'C' or graph 'topology'.")