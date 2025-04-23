import os
import shutil
import threading
import time
from create_topology import create_random_network, load_from_csv
from visualize_topology import start_visualization_thread, visualize_network_once_standalone
from mininet_runner import run_mininet 
from csv_topology import CSVTopology 
import csv
import networkx as nx

INITIAL_PATH = 'data/initial_topology.csv'
RUNNING_PATH = 'data/running_network.csv'
ALLOCATED_FLOW_PATH = 'data/allocated_flow.csv'


def load_graph_from_csv(path):
    G = nx.Graph()
    with open(path, 'r') as f:
        for line in f:
            src, dst, weight = line.strip().split(',')
            G.add_edge(src, dst, weight=int(weight))  # Ensure weight is int
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

def allocate_flow(csv_path, path_str, bandwidth):
    # Step 1: Parse the path
    path = path_str.split(',')

    # Step 2: Load running_path into a dictionary
    edges = {}
    with open(csv_path, 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            a, b, bw = row[0], row[1], int(row[2])
            # Store as a frozenset for undirected edges
            edges[frozenset((a, b))] = bw

    # Step 3: Subtract bandwidth from each edge in the path
    for i in range(len(path) - 1):
        edge = frozenset((path[i], path[i+1]))
        if edge in edges:
            edges[edge] -= bandwidth
        else:
            raise ValueError(f"Edge {path[i]} <-> {path[i+1]} not found in the network.")

    # Step 4: Write updated edges back to the CSV
    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        for edge, bw in edges.items():
            a, b = list(edge)
            writer.writerow([a, b, bw])

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


    # launch ryu controller
    print("Starting Ryu controller with stp...")
    os.system("gnome-terminal -- bash -c 'cd /home/vagrant/comnetsemu_dependencies/ryu-v4.34/ryu/ryu/app && ryu-manager simple_switch_stp_13.py; exec bash'")
    time.sleep(3)
    #launch mininet from another script
    print("Launching Mininet...")
    os.system("gnome-terminal -- bash -c 'sudo python3 mininet_runner.py; exec bash'")

    # Initial visualization (blocking until closed)
    visualize_network_once_standalone(INITIAL_PATH)

    # Start live-updating visualization
    start_visualization_thread(RUNNING_PATH)
    print("Live visualization running.")

    G = load_graph_from_csv(RUNNING_PATH)

    while True:
        print("\nChoose an option:")
        print("1 - Allocate flow")
        print("2 - Deallocate flow")
        print("3 - Exit")
        choice = input("Enter your choice (1/2/3): ").strip()

        if choice == '1':  # Allocate
            print("Current nodes:", G.nodes())
            source = input("Enter source node: ").strip()
            target = input("Enter target node: ").strip()
            k = int(input("Enter number of best paths (k): "))
            allocation_bandwidth = int(input("Enter bandwidth to allocate (Mbps): ").strip())

            if source not in G or target not in G:
                print("Invalid source or target node.")
                continue

            paths = list(nx.shortest_simple_paths(G, source, target, weight='weight'))[:k]

            print(f"\nTop {k} shortest paths from {source} to {target}:")
            for i, path in enumerate(paths, 1):
                path_weight = sum(G[u][v]['weight'] for u, v in zip(path[:-1], path[1:]))
                print(f"{i}: Path: {path}, Weight: {path_weight}")

            try:
                best_path, min_segmentation = least_segmentation(G, paths, allocation_bandwidth)
                print(f"\nBest path by least segmentation: {best_path}, Minimum Segmentation: {min_segmentation}")

                # Save the allocated flow
                with open(ALLOCATED_FLOW_PATH, 'a') as f:
                    path_str = ','.join(best_path)
                    f.write(f"{path_str},{int(allocation_bandwidth)}\n")

                # Update the running network
                allocate_flow(RUNNING_PATH, path_str, allocation_bandwidth)

                # Reload graph with updated values
                G = load_graph_from_csv(RUNNING_PATH)

            except ValueError as e:
                print(e)

        elif choice == '2':  # Deallocate
            print("\nDeallocating a flow from previously allocated list...")
            try:
                with open(ALLOCATED_FLOW_PATH, 'r') as f:
                    lines = f.readlines()

                if not lines:
                    print("No allocated flows to remove.")
                    continue

                # Show options to user
                for idx, line in enumerate(lines, 1):
                    print(f"{idx}: {line.strip()}")

                index = int(input("Enter the number of the flow to deallocate: ").strip()) - 1
                if index < 0 or index >= len(lines):
                    print("Invalid index.")
                    continue

                # Get the selected flow
                flow_line = lines[index].strip()
                *path_nodes, bandwidth = flow_line.split(',')
                path_str = ','.join(path_nodes)
                bandwidth = int(bandwidth)

                # Revert the bandwidth
                allocate_flow(RUNNING_PATH, path_str, -bandwidth)  # Re-add bandwidth

                # Remove from the CSV
                del lines[index]
                with open(ALLOCATED_FLOW_PATH, 'w') as f:
                    f.writelines(lines)

                # Reload graph
                G = load_graph_from_csv(RUNNING_PATH)

                print("Flow successfully deallocated.")

            except Exception as e:
                print(f"Error during deallocation: {e}")

        elif choice == '3':  # Exit
            print("Exiting...")
            print("Cleaning up Mininet...")
            os.system("sudo mn -c")
            os.system("pkill -f ryu-manager")
            break

        else:
            print("Invalid option. Try again.")


if __name__ == "__main__":
    main()

    #/home/vagrant/next_gen_network_slicing/data/my_topology.csv