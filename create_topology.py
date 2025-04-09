import os
import csv
import shutil
import random
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel

def create_topology_from_csv(path):
    print(f"Reading CSV and creating topology from: {path}")
    topo = Topo()
    created_nodes = {}

    with open(path, newline='') as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            if len(row) != 3:
                print(f"Invalid row: {row}")
                continue

            node1, node2, bw = row[0].strip(), row[1].strip(), int(row[2].strip())

            for node in [node1, node2]:
                if node not in created_nodes:
                    if node.startswith("h"):
                        created_nodes[node] = topo.addHost(node)
                    elif node.startswith("s"):
                        created_nodes[node] = topo.addSwitch(node)
                    else:
                        print(f"Unknown node type: {node}")
                        continue

            topo.addLink(created_nodes[node1], created_nodes[node2], bw=bw)

    return topo

def load_from_csv(input_path, running_path):
    print(f"Copying user file to running network path: {running_path}")
    shutil.copy(input_path, running_path)
    topo = create_topology_from_csv(running_path)
    run_mininet(topo)

def create_random_network(running_path):
    print("Creating a random network...")

    # Maximum number of switches and hosts
    NUM_SWITCHES = 6
    NUM_HOSTS = 5

    topo = Topo()
    link_list = []  # List to store all links for later CSV saving

    # Create switches
    switches = [topo.addSwitch(f"s{i+1}") for i in range(NUM_SWITCHES)]

    # Create hosts and connect each to a random switch
    hosts = []
    for i in range(NUM_HOSTS):
        host = topo.addHost(f"h{i+1}")
        hosts.append(host)
        sw = random.choice(switches)
        bw = random.randint(10, 100)
        topo.addLink(host, sw, bw=bw)
        link_list.append((host, sw, bw))

    # Fully mesh the switches
    for i in range(len(switches)):
        for j in range(i + 1, len(switches)):
            bw = random.randint(50, 500)
            topo.addLink(switches[i], switches[j], bw=bw)
            link_list.append((switches[i], switches[j], bw))

    # Save the generated topology to CSV
    with open(running_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        for link in link_list:
            writer.writerow(link)

    # Launch the Mininet network
    run_mininet(topo)



def run_mininet(topo):
    setLogLevel('info')
    net = Mininet(topo=topo, link=TCLink, controller=RemoteController, switch=OVSSwitch)
    net.start()
    CLI(net)
    net.stop()
