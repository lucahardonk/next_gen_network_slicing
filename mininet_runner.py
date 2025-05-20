#mininet_runner.py
from flask import Flask, request, jsonify
from threading import Thread
from werkzeug.serving import make_server
import json, os
from mininet.topo import Topo
from mininet.node import OVSSwitch, RemoteController
from mininet.link import TCLink
from mininet.net import Mininet
from mininet.cli import CLI
from mininet.log import setLogLevel
import shutil

app = Flask(__name__)
net = None  # Global Mininet object

INITIAL_PATH = 'data/initial_topology.csv'
RUNNING_PATH = 'data/running_network.csv'
TOPOLOGY_CSV = 'data/my_topology.csv'

ALLOC_FILE = "data/allocated_flows.json"

# Ensure JSON file exists
if not os.path.exists(ALLOC_FILE):
    with open(ALLOC_FILE, "w") as f:
        json.dump([], f)

# ──────────────────────────────
# Utility Functions
# ──────────────────────────────

def load_allocated_flows():
    with open(ALLOC_FILE, "r") as f:
        return json.load(f)

def save_allocated_flows(flows):
    with open(ALLOC_FILE, "w") as f:
        json.dump(flows, f, indent=2)

def snapshot_initial_topology(source_csv):
    shutil.copyfile(source_csv, INITIAL_PATH)
    print(f"\033[94m[SNAPSHOT]\033[0m Initial topology overwritten at: {INITIAL_PATH}")


# ──────────────────────────────
# API: Add or Remove Flows
# ──────────────────────────────

@app.route('/flow', methods=['POST'])
def handle_flow():
    data = request.json
    command = data.get("command")
    path = data.get("path")
    tcp_port = data.get("tcp_port")
    rate = data.get("rate")
    bidirectional = data.get("bidirectional", True)

    if not (command and path and tcp_port is not None and rate is not None):
        return jsonify({"error": "Missing required fields"}), 400

    if len(path) < 3 or not (path[0].startswith('h') and path[-1].startswith('h')):
        return jsonify({"error": "Path must start and end with hosts"}), 400

    try:
        flows = load_allocated_flows()

        src_host, dst_host = path[0], path[-1]
        src_node = net.get(src_host)
        dst_node = net.get(dst_host)

        src_ip = src_node.IP()
        dst_ip = dst_node.IP()
        src_mac = src_node.MAC()
        dst_mac = dst_node.MAC()

        out_ports = {}
        in_ports = {}
        links = []

        # Host → First switch
        first_switch = path[1]
        link = net.linksBetween(src_node, net.get(first_switch))[0]
        if link.intf1.node == src_node:
            out_ports[src_host] = src_node.ports[link.intf1]
            in_ports[first_switch] = net.get(first_switch).ports[link.intf2]
        else:
            out_ports[src_host] = src_node.ports[link.intf2]
            in_ports[first_switch] = net.get(first_switch).ports[link.intf1]
        links.append([src_host, first_switch])

        # Switch-to-switch segments
        for i in range(1, len(path) - 2):
            a = path[i]
            b = path[i + 1]
            link = net.linksBetween(net.get(a), net.get(b))[0]
            if link.intf1.node.name == a:
                out_ports[a] = net.get(a).ports[link.intf1]
                in_ports[b] = net.get(b).ports[link.intf2]
            else:
                out_ports[a] = net.get(a).ports[link.intf2]
                in_ports[b] = net.get(b).ports[link.intf1]
            links.append([a, b])

        # Last switch → Host
        last_switch = path[-2]
        link = net.linksBetween(net.get(last_switch), dst_node)[0]
        if link.intf1.node == dst_node:
            out_ports[last_switch] = net.get(last_switch).ports[link.intf2]
            in_ports[dst_host] = dst_node.ports[link.intf1]
        else:
            out_ports[last_switch] = net.get(last_switch).ports[link.intf1]
            in_ports[dst_host] = dst_node.ports[link.intf2]
        links.append([last_switch, dst_host])

        # Build forward flow
        forward_flow = {
            "src_ip": src_ip,
            "dst_ip": dst_ip,
            "src_mac": src_mac,
            "dst_mac": dst_mac,
            "tcp_port": tcp_port,
            "rate": rate,
            "path": path[1:-1],
            "out_ports": out_ports,
            "in_ports": in_ports,
            "links": links
        }

        # Build reverse flow
        reverse_path = path[::-1]
        reverse_out_ports = {k: v for k, v in in_ports.items()}
        reverse_in_ports = {k: v for k, v in out_ports.items()}
        reverse_links = [link[::-1] for link in reversed(links)]

        reverse_flow = {
            "src_ip": dst_ip,
            "dst_ip": src_ip,
            "src_mac": dst_mac,
            "dst_mac": src_mac,
            "tcp_port": tcp_port,
            "rate": rate,
            "path": reverse_path[1:-1],
            "out_ports": reverse_out_ports,
            "in_ports": reverse_in_ports,
            "links": reverse_links
        }

        # Apply command
        if command == "add":
            flows.append(forward_flow)
            if bidirectional:
                flows.append(reverse_flow)

        elif command == "delete":
            flows = [f for f in flows if not (
                (f['src_ip'], f['dst_ip'], f['tcp_port']) == (src_ip, dst_ip, tcp_port) or
                (bidirectional and (f['src_ip'], f['dst_ip'], f['tcp_port']) == (dst_ip, src_ip, tcp_port))
            )]
        else:
            return jsonify({"error": "Invalid command"}), 400

        save_allocated_flows(flows)
        return jsonify({"status": "ok", "flows": len(flows)})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ──────────────────────────────
# Exec & Bandwidth Endpoints
# ──────────────────────────────

@app.route('/exec', methods=['POST'])
def exec_cmd():
    data = request.json
    cmd = data.get("cmd", "")
    tokens = cmd.strip().split()
    if len(tokens) < 2:
        return jsonify({"error": "Command must include host and action"}), 400
    host, host_cmd = tokens[0], " ".join(tokens[1:])
    try:
        result = net.get(host).cmd(host_cmd)
        return jsonify({"result": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/set_bw', methods=['POST'])
def set_bw():
    data = request.json
    node1, node2, bw = data['node1'], data['node2'], data['bw']
    link = net.linksBetween(net.get(node1), net.get(node2))[0]
    link.intf1.config(bw=bw)
    link.intf2.config(bw=bw)
    return jsonify({"status": "ok"})

# ──────────────────────────────
# Flask in background
# ──────────────────────────────

class FlaskThread(Thread):
    def __init__(self, app):
        super().__init__()
        self.server = make_server('0.0.0.0', 5000, app)
        self.ctx = app.app_context()
        self.ctx.push()

    def run(self):
        print("[INFO] Starting Flask API on http://0.0.0.0:5000")
        self.server.serve_forever()

    def shutdown(self):
        print("[INFO] Stopping Flask API...")
        self.server.shutdown()

# ──────────────────────────────
# Mininet Topology
# ──────────────────────────────

class SimpleTopo(Topo):
    def build(self):
        h1 = self.addHost('h1', ip='10.0.0.1/24', mac='00:00:00:00:00:01')
        h2 = self.addHost('h2', ip='10.0.0.2/24', mac='00:00:00:00:00:02')
        h3 = self.addHost('h3', ip='10.0.0.3/24', mac='00:00:00:00:00:03')
        s1 = self.addSwitch('s1')
        s2 = self.addSwitch('s2')
        s3 = self.addSwitch('s3')
        s4 = self.addSwitch('s4')
        self.addLink(h1, s1, cls=TCLink, bw=100)
        self.addLink(h2, s2, cls=TCLink, bw=100)
        self.addLink(h3, s3, cls=TCLink, bw=100)
        self.addLink(s1, s2, cls=TCLink, bw=100)
        self.addLink(s1, s3, cls=TCLink, bw=100)
        self.addLink(s2, s3, cls=TCLink, bw=100)
        self.addLink(s1, s4, cls=TCLink, bw=100)
        self.addLink(s2, s4, cls=TCLink, bw=100)
        self.addLink(s3, s4, cls=TCLink, bw=100)

# ──────────────────────────────
# Runner
# ──────────────────────────────

def run():
    """
    Launches a Mininet topology based on user choice: CSV-defined, Random, or Exit.
    Starts Flask API on port 5000 and opens Mininet CLI.
    """
    import csv
    import random

    global net
    setLogLevel('info')

    # Ensure the runtime CSV exists and is empty
    os.makedirs("data", exist_ok=True)
    open(RUNNING_PATH, 'w').close()

    print("\n\033[96m[TOPO SETUP]\033[0m Choose a topology source:")
    print("  1 - Load from CSV file (data/my_topology.csv)")
    print("  2 - Generate a random topology")
    print("  3 - Exit\n")
    choice = input("Enter your choice [1/2/3]: ").strip()

    if choice == '1':
        if not os.path.exists(TOPOLOGY_CSV):
            print(f"\033[91m[ERROR]\033[0m File '{TOPOLOGY_CSV}' not found.")
            return

        print(f"\033[92m[INFO]\033[0m Loading topology from: {TOPOLOGY_CSV}")
        shutil.copyfile(TOPOLOGY_CSV, RUNNING_PATH)  # 👈 Copy to live version

        class CSVTopo(Topo):
            def build(self):
                nodes = {}
                link_count = 0
                with open(RUNNING_PATH) as f:
                    reader = csv.reader(f)
                    for row in reader:
                        n1, n2, bw = row[0].strip(), row[1].strip(), float(row[2])
                        for n in (n1, n2):
                            if n not in nodes:
                                nodes[n] = self.addHost(n) if n.startswith('h') else self.addSwitch(n)
                        self.addLink(nodes[n1], nodes[n2], cls=TCLink, bw=bw)
                        link_count += 1
                print(f"\033[92m[INFO]\033[0m Created {len(nodes)} nodes and {link_count} links from CSV.")

        topo = CSVTopo()

    elif choice == '2':
        print(f"\033[93m[INFO]\033[0m Generating random topology...")
        hosts = [f'h{i}' for i in range(1, 7)]
        switches = [f's{i}' for i in range(1, 7)]
        links = []

        for h, s in zip(hosts, switches):
            bw = random.choice([10, 50, 100])
            links.append((h, s, bw))

        for i in range(len(switches)):
            for j in range(i + 1, len(switches)):
                if random.random() > 0.3:
                    bw = random.choice([10, 50, 100])
                    links.append((switches[i], switches[j], bw))

        # Save to running_network.csv
        with open(RUNNING_PATH, 'w') as f:
            writer = csv.writer(f)
            for link in links:
                writer.writerow(link)

        class RandomTopo(Topo):
            def build(self):
                nodes = {}
                for n1, n2, bw in links:
                    for n in (n1, n2):
                        if n not in nodes:
                            nodes[n] = self.addHost(n) if n.startswith('h') else self.addSwitch(n)
                    self.addLink(nodes[n1], nodes[n2], cls=TCLink, bw=bw)
                print(f"\033[92m[INFO]\033[0m Created {len(nodes)} nodes and {len(links)} links randomly.")

        topo = RandomTopo()

    else:
        print("\033[93m[INFO]\033[0m Exiting.")
        return
    
    snapshot_initial_topology(RUNNING_PATH)
    print("\n\033[94m[MININET]\033[0m Initializing Mininet with RemoteController at 127.0.0.1:6633...")
    controller = RemoteController('c0', ip='127.0.0.1', port=6633)
    net = Mininet(topo=topo, controller=controller, switch=OVSSwitch, link=TCLink, autoSetMacs=True)
    net.start()

    # ──────────────────────────────
    # Fix file ownership to user (if run with sudo)
    # ──────────────────────────────
    user_uid = os.getenv("SUDO_UID") or "1000"
    try:
        os.system(f"chown {user_uid}:{user_uid} data/*.csv")
        os.system(f"chown {user_uid}:{user_uid} {ALLOC_FILE}")
        print(f"\033[92m[INFO]\033[0m File ownership set to UID {user_uid}")
    except Exception as e:
        print(f"\033[91m[ERROR]\033[0m Failed to change file ownership: {e}")


    flask_thread = FlaskThread(app)
    flask_thread.start()

    print("\n\033[92m[READY]\033[0m Flask API is running at http://localhost:5000")
    print("\033[92m[READY]\033[0m Type Mininet CLI commands below, or access the REST API.\n")
    try:
        CLI(net)
    finally:
        print("\n\033[91m[SHUTDOWN]\033[0m Stopping network...")
        net.stop()
        flask_thread.shutdown()





if __name__ == '__main__':
    setLogLevel('info')
    run()

