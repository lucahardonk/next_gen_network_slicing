import os
import csv
import networkx as nx
import requests

# ─────────────────────────────
# Constants
# ─────────────────────────────
RUNNING_PATH = 'data/running_network.csv'
ALLOCATED_FLOW_CSV = 'data/allocated_flow.csv'
BASE_TCP_PORT = 5001

# ─────────────────────────────
# Utility Functions
# ─────────────────────────────

def load_graph_from_csv(path):
    G = nx.Graph()
    with open(path) as f:
        for row in csv.reader(f):
            if len(row) == 3:
                a, b, bw = row
                G.add_edge(a, b, weight=int(bw))
    return G

def save_graph_to_csv(G, path):
    with open(path, 'w', newline='') as f:
        writer = csv.writer(f)
        for u, v, data in G.edges(data=True):
            writer.writerow([u, v, data['weight']])

def least_segmentation(G, paths, alloc_bw):
    best_path, best_seg = None, float('inf')
    for path in paths:
        segments = [G[u][v]['weight'] - alloc_bw for u, v in zip(path[:-1], path[1:])]
        if any(s < 0 for s in segments):
            continue
        min_seg = min(segments)
        if min_seg < best_seg:
            best_path, best_seg = path, min_seg
    if not best_path:
        raise ValueError("No valid path found with enough bandwidth.")
    return best_path, best_seg

def assign_tunnel_id():
    if not os.path.exists(ALLOCATED_FLOW_CSV) or os.path.getsize(ALLOCATED_FLOW_CSV) == 0:
        return 1
    with open(ALLOCATED_FLOW_CSV) as f:
        last = list(csv.reader(f))[-1]
        return int(last[-2]) + 1

def update_graph_bandwidth(G, path, bw_delta):
    for u, v in zip(path[:-1], path[1:]):
        G[u][v]['weight'] -= bw_delta
        if G[u][v]['weight'] < 0:
            raise ValueError(f"Link {u}-{v} has negative bandwidth.")
    save_graph_to_csv(G, RUNNING_PATH)

def save_flow(path, bw, tunnel_id, tcp_port):
    with open(ALLOCATED_FLOW_CSV, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(path + [bw, tunnel_id, tcp_port])

def remove_flow_by_tunnel_id(tunnel_id):
    with open(ALLOCATED_FLOW_CSV) as f:
        lines = list(csv.reader(f))
    remaining = []
    removed = []
    for row in lines:
        if int(row[-2]) == tunnel_id:
            removed.append(row)
        else:
            remaining.append(row)
    with open(ALLOCATED_FLOW_CSV, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(remaining)
    return removed

def call_flow_api(command, path, tcp_port, rate, bidirectional=True):
    url = "http://localhost:5000/flow"
    payload = {
        "command": command,
        "path": path,
        "tcp_port": tcp_port,
        "rate": rate,
        "bidirectional": bidirectional
    }
    try:
        response = requests.post(url, json=payload, timeout=5)
        if response.ok:
            print(f"\U0001f310 Flow API success ({command}): TCP {tcp_port}")
            return True
        else:
            print(f"\u26a0\ufe0f Flow API failed ({command}): HTTP {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"\u274c Error calling flow API ({command}): {e}")
        return False

# ─────────────────────────────
# Main Loop
# ─────────────────────────────

def interactive_loop():
    G = load_graph_from_csv(RUNNING_PATH)
    while True:
        print("\nOptions:")
        print("1 - Allocate flow")
        print("2 - Deallocate flow")
        print("3 - Exit")
        choice = input("Choice: ").strip()

        if choice == '1':
            src = input("Source node: ").strip()
            dst = input("Destination node: ").strip()
            if src not in G or dst not in G:
                print("Invalid nodes.")
                continue

            k = int(input("K (number of paths): ").strip())
            bw = int(input("Bandwidth to allocate (Mbps): ").strip())

            try:
                # Step 1: Get K-shortest paths
                paths = list(nx.shortest_simple_paths(G, src, dst, weight='weight'))[:k]
                if not paths:
                    print("\u274c No paths found between nodes.")
                    continue

                for i, p in enumerate(paths, 1):
                    cost = sum(G[u][v]['weight'] for u, v in zip(p[:-1], p[1:]))
                    print(f"{i}: {p} | Cost: {cost}")

                # Step 2: Try Yen-style segmentation-aware selection
                try:
                    best_path, min_seg = least_segmentation(G, paths, bw)
                except ValueError as ve:
                    print(f"\u274c Segmentation check failed: {ve}")
                    continue

                print(f"\u2705 Selected path: {best_path} | Min segmentation: {min_seg}")

                # Step 3: Prepare for allocation
                tunnel_id = assign_tunnel_id()
                tcp_port = BASE_TCP_PORT + tunnel_id

                # Step 4: Call Flow API (only commit if success)
                success = call_flow_api("add", best_path, tcp_port, bw)
                if not success:
                    print("\u274c Flow API failed. Aborting allocation.")
                    continue

                # Step 5: Commit changes locally
                update_graph_bandwidth(G, best_path, bw)
                save_flow(best_path, bw, tunnel_id, tcp_port)
                print(f"\u2713 Flow saved (Tunnel ID {tunnel_id}, TCP Port {tcp_port})")

            except Exception as e:
                print(f"\u274c Allocation failed: {e}")

        elif choice == '2':
            try:
                with open(ALLOCATED_FLOW_CSV) as f:
                    flows = list(csv.reader(f))
                if not flows:
                    print("No flows allocated.")
                    continue

                # Group by tunnel ID
                tunnel_groups = {}
                for flow in flows:
                    tid = int(flow[-2])
                    tunnel_groups.setdefault(tid, []).append(flow)

                # Show summary per tunnel
                print("\nAllocated Flows:")
                for tid, group in tunnel_groups.items():
                    directions = [f"{' → '.join(f[:-3])} (TCP {f[-1]})" for f in group]
                    bw = group[0][-3]
                    print(f"TID {tid} | BW: {bw} | Paths: {' + '.join(directions)}")

                # Ask user for Tunnel ID
                tunnel_id = int(input("\nEnter Tunnel ID to remove: ").strip())
                if tunnel_id not in tunnel_groups:
                    print("Tunnel ID not found.")
                    continue

                removed_flows = remove_flow_by_tunnel_id(tunnel_id)

                for flow in removed_flows:
                    path = flow[:-3]
                    bw = int(flow[-3])
                    tcp_port = int(flow[-1])
                    if call_flow_api("delete", path, tcp_port, bw):
                        update_graph_bandwidth(G, path, -bw)
                        print(f"\u2713 Deallocated flow with TCP {tcp_port}")
                    else:
                        print(f"\u274c API failed to delete flow with TCP {tcp_port}")

            except Exception as e:
                print(f"\u274c Deallocation failed: {e}")


        elif choice == '3':
            print("Exiting.")
            break
        else:
            print("Invalid option.")

# ─────────────────────────────
# Entry Point
# ─────────────────────────────

if __name__ == "__main__":
    interactive_loop()