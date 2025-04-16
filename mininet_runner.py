from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel

def run_mininet(topo):
    setLogLevel('info')
    net = Mininet(topo=topo, link=TCLink, controller=RemoteController, switch=OVSSwitch)
    net.start()
    CLI(net)
    net.stop()
