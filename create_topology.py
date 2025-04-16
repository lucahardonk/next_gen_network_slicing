import csv
import shutil
import random
from mininet.topo import Topo

def create_topology_from_csv(path: str) -> Topo:
    """Builds a Mininet Topo object from a CSV file describing links."""
    topo = Topo()
    created_nodes = {}

    with open(path, newline='') as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            if len(row) != 3:
                continue  # Skip invalid rows

            node1, node2, bw_str = row[0].strip(), row[1].strip(), row[2].strip()
            try:
                bw = int(bw_str)
            except ValueError:
                print(f"Invalid bandwidth: {bw_str}")
                continue

            for node in [node1, node2]:
                if node not in created_nodes:
                    if node.startswith("h"):
                        created_nodes[node] = topo.addHost(node)
                    elif node.startswith("s"):
                        created_nodes[node] = topo.addSwitch(node)

            topo.addLink(created_nodes[node1], created_nodes[node2], bw=bw)

    return topo

def load_from_csv(input_path: str, output_path: str) -> Topo:
    """Copies the CSV to output_path and builds a Mininet topology from it."""
    shutil.copy(input_path, output_path)
    return create_topology_from_csv(output_path)

def create_random_network(output_path: str, num_switches: int = 6, num_hosts: int = 5) -> Topo:
    """Generates a random Mininet Topo and saves it to a CSV file."""
    topo = Topo()
    link_list = []
    switches = [topo.addSwitch(f"s{i+1}") for i in range(num_switches)]

    for i in range(num_hosts):
        host = topo.addHost(f"h{i+1}")
        sw = random.choice(switches)
        bw = random.randint(10, 100)
        topo.addLink(host, sw, bw=bw)
        link_list.append((host, sw, bw))

    for i in range(len(switches)):
        for j in range(i + 1, len(switches)):
            bw = random.randint(50, 500)
            topo.addLink(switches[i], switches[j], bw=bw)
            link_list.append((switches[i], switches[j], bw))

    with open(output_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        for link in link_list:
            writer.writerow(link)

    return topo
