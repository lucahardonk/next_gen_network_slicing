from mininet.topo import Topo
import csv

class CSVTopology(Topo):
    def __init__(self, csv_path):
        super().__init__()
        added = set()

        with open(csv_path, newline='') as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                if len(row) != 3:
                    continue
                node1, node2, bw = row[0].strip(), row[1].strip(), int(row[2].strip())

                # Add switches or hosts
                for node in [node1, node2]:
                    if node.startswith("s") and node not in added:
                        self.addSwitch(node)
                        added.add(node)
                    elif node.startswith("h") and node not in added:
                        self.addHost(node)
                        added.add(node)

                # Add link with bandwidth
                self.addLink(node1, node2, bw=bw)
