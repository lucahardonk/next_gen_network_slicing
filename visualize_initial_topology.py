# visualize_initial_topology.py
import csv
import math
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib import cm
import os

INITIAL_PATH = 'data/initial_topology.csv'

def load_topology_from_csv(path):
    G = nx.Graph()
    with open(path, newline='') as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            if len(row) != 3:
                continue
            node1, node2, bw = row[0].strip(), row[1].strip(), row[2].strip()
            try:
                bw = int(bw)
            except ValueError:
                bw = 0
            G.add_edge(node1, node2, bandwidth=bw)
    return G

def get_switch_and_host_nodes(G):
    switches = sorted([n for n in G.nodes() if n.startswith("s")])
    hosts = sorted([n for n in G.nodes() if n.startswith("h")])
    return switches, hosts

def generate_polygon_layout(nodes, radius=2.5, center=(0, 0)):
    pos = {}
    angle_step = 2 * math.pi / len(nodes)
    cx, cy = center
    for i, node in enumerate(nodes):
        angle = i * angle_step
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        pos[node] = (x, y)
    return pos

def attach_hosts_to_switches(G, switch_pos, host_offset=0.7):
    pos = {}
    switch_to_hosts = {}
    for host in [n for n in G.nodes() if n.startswith("h")]:
        neighbors = list(G.neighbors(host))
        if not neighbors:
            pos[host] = (0, 0)
            continue
        sw = neighbors[0]
        switch_to_hosts.setdefault(sw, []).append(host)

    for sw, hosts in switch_to_hosts.items():
        if sw not in switch_pos:
            continue
        sx, sy = switch_pos[sw]
        angle_base = math.atan2(sy, sx)
        angle_step = math.pi / 6
        center_index = (len(hosts) - 1) / 2
        for i, host in enumerate(hosts):
            angle = angle_base + (i - center_index) * angle_step
            hx = sx + host_offset * math.cos(angle)
            hy = sy + host_offset * math.sin(angle)
            pos[host] = (hx, hy)
    return pos

def compute_node_positions(G):
    switches, _ = get_switch_and_host_nodes(G)
    switch_pos = generate_polygon_layout(switches, radius=2.5)
    host_pos = attach_hosts_to_switches(G, switch_pos, host_offset=0.7)
    return {**switch_pos, **host_pos}

def draw_edge_bandwidth_labels(G, pos, offset_amount=0.2, edge_color_map=None):
    edge_labels = nx.get_edge_attributes(G, 'bandwidth')
    edge_labels = {edge: f"{bw} Mbps" for edge, bw in edge_labels.items()}

    for (n1, n2), label in edge_labels.items():
        x1, y1 = pos[n1]
        x2, y2 = pos[n2]
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        offset_x = -dy / length * offset_amount if length else 0
        offset_y = dx / length * offset_amount if length else 0
        lx, ly = mx + offset_x, my + offset_y
        color = edge_color_map.get((n1, n2)) or edge_color_map.get((n2, n1)) if edge_color_map else "black"

        plt.text(
            lx, ly, label,
            fontsize=9,
            color=color,
            ha='center', va='center',
            bbox=dict(facecolor='white', edgecolor=color, boxstyle='round,pad=0.2', alpha=0.8)
        )

def visualize_initial_topology(path):
    if not os.path.exists(path):
        print(f"\033[91m[ERROR]\033[0m Initial topology file not found: {path}")
        return

    G = load_topology_from_csv(path)
    pos = compute_node_positions(G)
    switches, hosts = get_switch_and_host_nodes(G)
    node_colors = ['skyblue' if n in switches else 'lightgreen' for n in G.nodes()]
    edges = list(G.edges())
    cmap = cm.get_cmap('tab20', len(edges))
    edge_colors = [cmap(i) for i in range(len(edges))]
    edge_color_map = {edge: color for edge, color in zip(edges, edge_colors)}

    plt.figure("Initial Topology")
    for (edge, color) in edge_color_map.items():
        nx.draw_networkx_edges(G, pos, edgelist=[edge], edge_color=[color], width=2)
    nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=1400)
    nx.draw_networkx_labels(G, pos, font_size=12, font_weight='bold')
    draw_edge_bandwidth_labels(G, pos, edge_color_map=edge_color_map)
    plt.title("Initial Network Topology", fontsize=16)
    plt.axis('off')
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    visualize_initial_topology(INITIAL_PATH)
