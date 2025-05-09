from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel
from csv_topology import CSVTopology
import os
import time
import threading

INITIAL_PATH = 'data/initial_topology.csv'
ALLOCATED_FLOW_PATH = 'data/allocated_flow.csv'

def setup_queues_for_path(net, path_nodes, bandwidth, queue_id):
    for u, v in zip(path_nodes[:-1], path_nodes[1:]):
        if u.startswith('s') and v.startswith('s'):
            node_u = net.get(u)
            node_v = net.get(v)

            for intf in node_u.intfList():
                if intf.link and intf.link.intf1 and intf.link.intf2:
                    peer = intf.link.intf1 if intf.link.intf2.node == node_u else intf.link.intf2
                    if peer.node == node_v:
                        intf_name = intf.name
                        print(f"🛠️ Setting up queue on {u}:{intf_name} for queue {queue_id} @ {bandwidth} Mbps")
                        node_u.cmd(f"tc qdisc add dev {intf_name} root handle 1: htb default 10")
                        node_u.cmd(f"tc class add dev {intf_name} parent 1: classid 1:{queue_id} htb rate {bandwidth}mbit")

def watch_allocated_flows_and_apply_queues(net):
    seen_flows = set()

    while True:
        if not os.path.exists(ALLOCATED_FLOW_PATH):
            time.sleep(1)
            continue

        try:
            with open(ALLOCATED_FLOW_PATH, 'r') as f:
                lines = [line.strip() for line in f if line.strip()]
        except Exception as e:
            print(f"⚠️ Error reading {ALLOCATED_FLOW_PATH}: {e}")
            time.sleep(1)
            continue

        for line in lines:
            parts = line.split(',')
            if len(parts) < 4:
                continue  # malformed line

            *path_nodes, bandwidth_str, queue_id_str, tcp_port_str = parts

            try:
                bandwidth = int(bandwidth_str)
                queue_id = int(queue_id_str)
                key = tuple(path_nodes + [queue_id_str])  # use str for consistency in set
            except ValueError as e:
                print(f"⚠️ Skipping invalid line (non-integer values): {line}")
                continue

            if key not in seen_flows:
                try:
                    setup_queues_for_path(net, path_nodes, bandwidth, queue_id)
                    seen_flows.add(key)
                except Exception as e:
                    print(f"❌ Failed to set up queue for {key}: {e}")

        time.sleep(1)

def run_mininet():
    setLogLevel('info')
    print("🚀 mininet_runner.py started!")
    topo = CSVTopology(INITIAL_PATH)
    c0 = RemoteController('c0', ip='127.0.0.1', port=6633)
    net = Mininet(topo=topo, link=TCLink, controller=None, switch=OVSSwitch)
    net.addController(c0)
    net.start()

    for sw in net.switches:
        sw.cmd(f"ovs-vsctl set Bridge {sw.name} protocols=OpenFlow13")

    print("✅ Mininet started.")

    # Start background thread to apply queues
    threading.Thread(target=watch_allocated_flows_and_apply_queues, args=(net,), daemon=True).start()

    CLI(net)  # Optional: gives you a terminal inside mininet


if __name__ == "__main__":
    run_mininet()
