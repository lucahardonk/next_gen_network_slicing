
#!/usr/bin/env python2

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel
import random

class CustomSDNTopo(Topo):
    def build(self, num_switches=3, num_hosts=5):
        switches = []
        hosts = []

        # Create switches
        for i in range(num_switches):
            switch = self.addSwitch('s{}'.format(i+1))
            switches.append(switch)

        # Create hosts and randomly connect them to switches
        for i in range(num_hosts):
            host = self.addHost('h{}'.format(i+1))
            hosts.append(host)
            sw = random.choice(switches)
            self.addLink(host, sw, bw=random.randint(10, 100))  # Random bandwidth 10-100 Mbps

        # Create dense connections between switches
        for i in range(len(switches)):
            for j in range(i+1, len(switches)):
                bw = random.randint(50, 500)  # Random link capacity in Mbps
                self.addLink(switches[i], switches[j], bw=bw)

if __name__ == '__main__':
    setLogLevel('info')
    topo = CustomSDNTopo(num_switches=5, num_hosts=8)
    net = Mininet(topo=topo, link=TCLink, controller=RemoteController)
    net.start()
   # print (Running CLI)
    CLI(net)
    net.stop()
