from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
import requests

# Define your slice configurations with MACs and rate
slices = [
    # Forward slice: h1 → h2 on port 5005
    {
        "src_ip": "10.0.0.1",
        "dst_ip": "10.0.0.2",
        "src_mac": "00:00:00:00:00:01",
        "dst_mac": "00:00:00:00:00:02",
        "tcp_port": 5005,
        "rate": 10,  # Mbps
        "path": ["s1", "s3", "s2"],
        "out_ports": { "s1": 3, "s3": 2, "s2": 2 },
        "in_ports":  { "s2": 3, "s3": 1, "s1": 1 },
        "links": [["s1", "s3"], ["s3", "s2"], ["s2", "h2"], ["h1", "s1"]]
    },
    # Reverse slice: h2 → h1 on port 5005 
    {
        "src_ip": "10.0.0.2",
        "dst_ip": "10.0.0.1",
        "src_mac": "00:00:00:00:00:02",
        "dst_mac": "00:00:00:00:00:01",
        "tcp_port": 5005,
        "rate": 10,  # Mbps
        "path": ["s2", "s3", "s1"],
        "out_ports": { "s2": 3, "s3": 1, "s1": 1 },
        "in_ports":  { "s1": 3, "s3": 2, "s2": 2 },
        "links": [["s2", "s3"], ["s3", "s1"], ["s1", "h1"], ["h2", "s2"]]
    },
    # Forward slice: h1 → h2 on port 5006
    {
        "src_ip": "10.0.0.1",
        "dst_ip": "10.0.0.2",
        "src_mac": "00:00:00:00:00:01",
        "dst_mac": "00:00:00:00:00:02",
        "tcp_port": 5006,
        "rate": 50,  # Mbps
        "path": ["s1", "s2"],
        "out_ports": { "s1": 2, "s2": 2 },
        "in_ports":  { "s2": 1, "s1": 1 },
        "links": [["s1", "s2"], ["s2", "h2"], ["h1", "s1"]]
    },
    # Reverse slice: h2 → h1 on port 5006
    {
        "src_ip": "10.0.0.2",
        "dst_ip": "10.0.0.1",
        "src_mac": "00:00:00:00:00:02",
        "dst_mac": "00:00:00:00:00:01",
        "tcp_port": 5006,
        "rate": 50,  # Mbps
        "path": ["s2", "s1"],
        "out_ports": { "s2": 1, "s1": 1 },
        "in_ports":  { "s1": 2, "s2": 2 },
        "links": [["s2", "s1"], ["s1", "h1"], ["h2", "s2"]]
    }
]



# Map DPID to switch names
dpid_to_name = {
    1: "s1",
    2: "s2",
    3: "s3"
}

class ModularSliceController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        print("[+] ModularSliceController initialized")

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        dpid = datapath.id
        sw_name = dpid_to_name.get(dpid)

        if not sw_name:
            print(f"[!] Unknown switch DPID: {dpid}")
            return

        print(f"[+] Configuring switch {sw_name} (DPID={dpid})")

        for s in slices:
            if sw_name in s['path']:
                print(f"[~] Setting up slice on {sw_name} for TCP port {s['tcp_port']}")

                # Install forward rule
                match_fwd = parser.OFPMatch(
                    eth_type=0x0800,
                    eth_src=s["src_mac"],
                    eth_dst=s["dst_mac"],
                    ip_proto=6,
                    ipv4_src=s["src_ip"],
                    ipv4_dst=s["dst_ip"],
                    tcp_dst=s["tcp_port"]
                )
                out_port = s['out_ports'][sw_name]
                actions_fwd = [parser.OFPActionOutput(out_port)]
                self._add_flow(datapath, 100, match_fwd, actions_fwd)
                print(f"[+] Forward rule added on {sw_name}: {s['src_ip']}:{s['tcp_port']} → {s['dst_ip']} via port {out_port}")

                # Install reverse rule
                match_rev = parser.OFPMatch(
                    eth_type=0x0800,
                    eth_src=s["dst_mac"],
                    eth_dst=s["src_mac"],
                    ip_proto=6,
                    ipv4_src=s["dst_ip"],
                    ipv4_dst=s["src_ip"],
                    tcp_src=s["tcp_port"]
                )
                in_port = s['in_ports'][sw_name]
                actions_rev = [parser.OFPActionOutput(in_port)]
                self._add_flow(datapath, 100, match_rev, actions_rev)
                print(f"[+] Reverse rule added on {sw_name}: {s['dst_ip']}:{s['tcp_port']} → {s['src_ip']} via port {in_port}")

                # Set link bandwidth limits only once from the first switch
                if sw_name == s['path'][0]:
                    for n1, n2 in s.get("links", []):
                        self.set_link_bw(n1, n2, s["rate"])

                    self.push_static_arp("h1", s["dst_ip"], s["dst_mac"])
                    self.push_static_arp("h2", s["src_ip"], s["src_mac"])

        # Default drop rule
        self._add_flow(datapath, 0, parser.OFPMatch(), [])
        print(f"[~] Default drop rule installed on {sw_name}")

    def _add_flow(self, datapath, priority, match, actions):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=priority,
            match=match,
            instructions=inst,
            idle_timeout=0,
            hard_timeout=0
        )
        datapath.send_msg(mod)
        print(f"[✓] Flow installed on {dpid_to_name[datapath.id]}: match={match}, actions={actions}")

    def push_static_arp(self, host, ip, mac):
        url = "http://127.0.0.1:5000/exec"
        payload = {"cmd": f"{host} arp -s {ip} {mac}"}
        try:
            response = requests.post(url, json=payload, timeout=2)
            if response.ok:
                print(f"[✓] ARP pushed: {payload['cmd']}")
            else:
                print(f"[!] Failed ARP push: {payload['cmd']} - HTTP {response.status_code}")
        except Exception as e:
            print(f"[!] Error calling Flask API for ARP push: {e}")

    def set_link_bw(self, node1, node2, bw):
        url = "http://127.0.0.1:5000/set_bw"
        payload = {"node1": node1, "node2": node2, "bw": bw}
        try:
            response = requests.post(url, json=payload, timeout=2)
            if response.ok:
                print(f"[✓] Link BW set: {node1}<->{node2} to {bw} Mbps")
            else:
                print(f"[!] Link BW setting failed: {payload} → HTTP {response.status_code}")
        except Exception as e:
            print(f"[!] Error setting link BW: {e}")


#working with flask api in mininet


'''
# Forward
mininet> h2 iperf -s -p 5005 &
mininet> h1 iperf -c 10.0.0.2 -p 5005

# Reverse
mininet> h1 iperf -s -p 5005 &
mininet> h2 iperf -c 10.0.0.1 -p 5005

#Foward 
mininet> h2 iperf -s -p 5006 &
mininet> h1 iperf -c 10.0.0.2 -p 5006
# Reverse
mininet> h1 iperf -s -p 5006 &
mininet> h2 iperf -c 10.0.0.1 -p 5006


'''