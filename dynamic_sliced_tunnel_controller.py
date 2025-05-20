#dynamic_sliced_tunnel.py
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
import requests
import json
import time
import threading
from collections import defaultdict

#file to keep track of the flows we are using
FLOWS_FILE = "data/allocated_flows.json"
#maxixmum switches number to map their name
SWITCHES = 20

# Automatically generate DPID to switch name mapping
dpid_to_name = {dpid: f"s{dpid}" for dpid in range(1, SWITCHES + 1)}


class ModularSliceController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        print("[+] ModularSliceController initialized")
        self.datapaths = {}
        self.last_flows = []
        threading.Thread(target=self.flow_monitor_loop, daemon=True).start()

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        self.datapaths[datapath.id] = datapath
        parser = datapath.ofproto_parser

        # Install default drop rule
        self._add_flow(datapath, 0, parser.OFPMatch(), [])
        print(f"[~] Default drop rule installed on {dpid_to_name.get(datapath.id, datapath.id)}")

    def flow_monitor_loop(self):
        path = FLOWS_FILE

        while True:
            try:
                with open(path) as f:
                    flows = json.load(f)
            except Exception as e:
                print(f"[!] Error reading JSON: {e}")
                time.sleep(2)
                continue

            added = [f for f in flows if f not in self.last_flows]
            removed = [f for f in self.last_flows if f not in flows]

            for flow in removed:
                self.remove_flow_from_all(flow)

            for flow in added:
                self.install_flow_on_all(flow)

            self.last_flows = flows
            time.sleep(2)

    def install_flow_on_all(self, flow):
        for dpid, datapath in self.datapaths.items():
            sw_name = dpid_to_name.get(dpid)
            if sw_name and sw_name in flow["path"]:
                self.install_slice(datapath, sw_name, flow)

    def remove_flow_from_all(self, flow):
        for dpid, datapath in self.datapaths.items():
            sw_name = dpid_to_name.get(dpid)
            if sw_name and sw_name in flow["path"]:
                self.remove_slice(datapath, sw_name, flow)

    def install_slice(self, datapath, sw_name, s):
        parser = datapath.ofproto_parser

        match_fwd = parser.OFPMatch(
            eth_type=0x0800,
            eth_src=s["src_mac"],
            eth_dst=s["dst_mac"],
            ip_proto=6,
            ipv4_src=s["src_ip"],
            ipv4_dst=s["dst_ip"],
            tcp_dst=s["tcp_port"]
        )
        out_port = s["out_ports"][sw_name]
        actions_fwd = [parser.OFPActionOutput(out_port)]
        self._add_flow(datapath, 100, match_fwd, actions_fwd)

        match_rev = parser.OFPMatch(
            eth_type=0x0800,
            eth_src=s["dst_mac"],
            eth_dst=s["src_mac"],
            ip_proto=6,
            ipv4_src=s["dst_ip"],
            ipv4_dst=s["src_ip"],
            tcp_src=s["tcp_port"]
        )
        in_port = s["in_ports"][sw_name]
        actions_rev = [parser.OFPActionOutput(in_port)]
        self._add_flow(datapath, 100, match_rev, actions_rev)

        if sw_name == s["path"][0]:
            for n1, n2 in s.get("links", []):
                self.set_link_bw(n1, n2, s["rate"])

            src_host = self.ip_to_host(s["src_ip"])
            dst_host = self.ip_to_host(s["dst_ip"])
            self.push_static_arp(src_host, s["dst_ip"], s["dst_mac"])
            self.push_static_arp(dst_host, s["src_ip"], s["src_mac"])

    def remove_slice(self, datapath, sw_name, s):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        match_fwd = parser.OFPMatch(
            eth_type=0x0800,
            eth_src=s["src_mac"],
            eth_dst=s["dst_mac"],
            ip_proto=6,
            ipv4_src=s["src_ip"],
            ipv4_dst=s["dst_ip"],
            tcp_dst=s["tcp_port"]
        )
        match_rev = parser.OFPMatch(
            eth_type=0x0800,
            eth_src=s["dst_mac"],
            eth_dst=s["src_mac"],
            ip_proto=6,
            ipv4_src=s["dst_ip"],
            ipv4_dst=s["src_ip"],
            tcp_src=s["tcp_port"]
        )

        self._del_flow(datapath, match_fwd)
        self._del_flow(datapath, match_rev)
        print(f"[x] Removed slice on {sw_name} for port {s['tcp_port']}")

    def _add_flow(self, datapath, priority, match, actions):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
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
        print(f"[✓] Flow installed on {dpid_to_name.get(datapath.id)}: {match}")

    def _del_flow(self, datapath, match):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        mod = parser.OFPFlowMod(
            datapath=datapath,
            command=ofproto.OFPFC_DELETE,
            out_port=ofproto.OFPP_ANY,
            out_group=ofproto.OFPG_ANY,
            match=match,
            priority=100
        )
        datapath.send_msg(mod)

    def push_static_arp(self, host, ip, mac):
        url = "http://127.0.0.1:5000/exec"
        payload = {"cmd": f"{host} arp -s {ip} {mac}"}
        try:
            response = requests.post(url, json=payload, timeout=2)
            if response.ok:
                print(f"[✓] ARP pushed: {payload['cmd']}")
            else:
                print(f"[!] ARP push failed: {payload['cmd']}, status={response.status_code}")
        except Exception as e:
            print(f"[!] Error in ARP push: {e}")

    def set_link_bw(self, node1, node2, bw):
        url = "http://127.0.0.1:5000/set_bw"
        payload = {"node1": node1, "node2": node2, "bw": bw}
        try:
            response = requests.post(url, json=payload, timeout=2)
            if response.ok:
                print(f"[✓] Link BW set: {node1}<->{node2} to {bw} Mbps")
            else:
                print(f"[!] BW setting failed: {payload} → status={response.status_code}")
        except Exception as e:
            print(f"[!] Error setting link BW: {e}")

    def ip_to_host(self, ip):
        # Assumes format 10.0.0.X → hX
        return f"h{int(ip.strip().split('.')[-1])}"


'''
▶ Test Slice 1: h1 ➜ h2 on port 5005

mininet> h2 iperf -s -p 5005 &
mininet> h1 iperf -c 10.0.0.2 -p 5005 -t 10

◀ Test Slice 2: h2 ➜ h1 on port 5005

mininet> h1 iperf -s -p 5005 &
mininet> h2 iperf -c 10.0.0.1 -p 5005 -t 10

▶ Test Slice 3: h1 ➜ h2 on port 5006

mininet> h2 iperf -s -p 5006 &
mininet> h1 iperf -c 10.0.0.2 -p 5006 -t 10

◀ Test Slice 4: h2 ➜ h1 on port 5006

mininet> h1 iperf -s -p 5006 &
mininet> h2 iperf -c 10.0.0.1 -p 5006 -t 10



'''