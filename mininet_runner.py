from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel
from csv_topology import CSVTopology

INITIAL_PATH = 'data/initial_topology.csv'

def run_mininet():
    setLogLevel('info')

    # Create the topology
    topo = CSVTopology(INITIAL_PATH)

    # Set up a remote controller pointing to Ryu's default IP/port
    c0 = RemoteController('c0', ip='127.0.0.1', port=6633)

    # Start Mininet with the topology and controller
    net = Mininet(topo=topo, link=TCLink, controller=None, switch=OVSSwitch)
    net.addController(c0)

    net.start()

    # Force OpenFlow 1.3 on all switches
    for sw in net.switches:
        sw.cmd("ovs-vsctl set Bridge {} protocols=OpenFlow13".format(sw.name))

    print("✅ Mininet started. Use ping, iperf, etc. CLI active.")
    CLI(net)
    net.stop()

if __name__ == "__main__":
    run_mininet()
