import os
import shutil
import threading
import time
from create_topology import create_random_network, load_from_csv
from visualize_topology import start_visualization_thread, visualize_network_once_standalone
from mininet_runner import run_mininet 
from csv_topology import CSVTopology 

import networkx as nx

INITIAL_PATH = 'data/initial_topology.csv'
RUNNING_PATH = 'data/running_network.csv'


def load_graph_from_csv(path):
    G = nx.Graph()
    with open(path, 'r') as f:
        for line in f:
            src, dst, weight = line.strip().split(',')
            G.add_edge(src, dst, weight=float(weight))  # Ensure weight is float
    return G


def least_segmentation(G, paths, allocation_bandwidth):
    best_path = None
    best_min_segmentation = None

    for path in paths:
        # Calculate residual bandwidth for each link on the path
        segmentations = [G[u][v]['weight'] - allocation_bandwidth for u, v in zip(path[:-1], path[1:])]
        
        # Check if every link has enough bandwidth
        if any(seg < 0 for seg in segmentations):
            continue  # skip paths that cannot fully satisfy the allocation
        
        # Find the minimum segmentation for the valid path
        min_segmentation = min(segmentations)
        
        # Choose the path with the least minimum segmentation
        if best_min_segmentation is None or min_segmentation < best_min_segmentation:
            best_min_segmentation = min_segmentation
            best_path = path

    if best_path is None:
        raise ValueError("No valid path found: insufficient bandwidth on all paths.")

    return best_path, best_min_segmentation



def main():
    user_input = input("Press 'r' to create a random network or insert the path to a CSV file: ").strip()

    if user_input.lower() == 'r':
        topo = create_random_network(INITIAL_PATH)
    elif os.path.isfile(user_input):
        topo = load_from_csv(user_input, INITIAL_PATH)
    else:
        print("Invalid input.")
        return

    shutil.copyfile(INITIAL_PATH, RUNNING_PATH)

    # Initial visualization (blocking until closed)
    visualize_network_once_standalone(INITIAL_PATH)

    # Start live-updating visualization
    start_visualization_thread(RUNNING_PATH)

    print("Live visualization running.")

    # ✅ Create and run the Mininet network (interactive CLI)
    '''
    print("Launching Mininet...")
    
    net_topo = CSVTopology(INITIAL_PATH)
    run_mininet(net_topo)
    '''
    print("please add a bandwith reservation for example: h1,h2,10")


   

    G = load_graph_from_csv(RUNNING_PATH)

    print("Current nodes:", G.nodes())
    source = input("Enter source node: ").strip()
    target = input("Enter target node: ").strip()
    k = int(input("Enter number of best paths (k): "))
    allocation_bandwidth = float(input("Enter bandwidth to allocate (Mbps): ").strip())


    if source not in G or target not in G:
        print("Invalid source or target node.")
        return

    paths = list(nx.shortest_simple_paths(G, source, target, weight='weight'))[:k]

    print(f"\nTop {k} shortest paths from {source} to {target}:")
    for i, path in enumerate(paths, 1):
        path_weight = sum(G[u][v]['weight'] for u, v in zip(path[:-1], path[1:]))
        print(f"{i}: Path: {path}, Weight: {path_weight}")

    try:
        best_path, min_segmentation = least_segmentation(G, paths, allocation_bandwidth)
        print(f"\nBest path by least segmentation: {best_path}, Minimum Segmentation: {min_segmentation}")
    except ValueError as e:
        print(e)


    # put the result in calculared_request.cvs ( entire path), 
    # eg. Best path by least segmentation: ['h1', 's6', 's1', 's5', 'h4'], Minimum Segmentation: 0.0
    #update running netwodk (openflow) with a lower badwith for each time csv updates

    #undo (delete flow) from calculared_request later on
    #grafici iperf



#/home/vagrant/next_gen_network_slicing/data/my_topology.csv


if __name__ == "__main__":
    main()
