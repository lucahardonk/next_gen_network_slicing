# simple_switch_stp_13_next_gen.py
# Merged STP-aware simple switch with queue-based network slicing that
# installs rules only when ports enter FORWARD state.

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib import dpid as dpid_lib
from ryu.lib import stplib
from ryu.controller import dpset
from ryu.lib.packet import packet, ethernet
from ryu.lib import hub
from ryu.app import simple_switch_13
import os

# CSV path: <path hops...>,<bandwidth>,<tunnel_id>,<tcp_port>
ALLOCATED_FLOW_PATH = 'data/allocated_flow.csv'


class SimpleSwitch13(simple_switch_13.SimpleSwitch13):
    """STP-aware L2 switch + queue-based slicing.

    Inherits all MAC-learning & STP from simple_switch_13, plus:
    - Watches ALLOCATED_FLOW_PATH for <dst_host> flows.
    - Installs/removes queue rules on ALL datapaths when ports forward.
    """

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _CONTEXTS = {
        'stplib': stplib.Stp,
        'dpset': dpset.DPSet,
    }

    def __init__(self, *args, **kwargs):
        super(SimpleSwitch13, self).__init__(*args, **kwargs)
        self.stp = kwargs['stplib']
        self.dpset = kwargs['dpset']

        # Track installed queue flows: set of (dst_ip, tcp_port, queue_id)
        self.active_flows = set()
        self.poll_interval = 1.0

        # Optionally tune per-bridge STP priorities
        self.stp.set_config({
            dpid_lib.str_to_dpid('0000000000000001'): {'bridge': {'priority': 0x8000}},
            dpid_lib.str_to_dpid('0000000000000002'): {'bridge': {'priority': 0x9000}},
            dpid_lib.str_to_dpid('0000000000000003'): {'bridge': {'priority': 0xa000}},
        })

        # Start background CSV watcher
        self.csv_thread = hub.spawn(self._watch_allocation_csv)

    # ------------------------------------------------------------------
    # Queue flow utilities
    # ------------------------------------------------------------------
    def add_queue_flow(self, datapath, dst_ip, tcp_dst, queue_id):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        match = parser.OFPMatch(
            eth_type=0x0800, ip_proto=6,
            ipv4_dst=dst_ip, tcp_dst=tcp_dst
        )
        actions = [parser.OFPActionSetQueue(queue_id),
                   parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath, match=match,
                                priority=100, instructions=inst)
        datapath.send_msg(mod)

    def delete_flow_by_match(self, datapath, dst_ip, tcp_dst):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        match = parser.OFPMatch(
            eth_type=0x0800, ip_proto=6,
            ipv4_dst=dst_ip, tcp_dst=tcp_dst
        )
        mod = parser.OFPFlowMod(
            datapath=datapath,
            command=ofproto.OFPFC_DELETE,
            out_port=ofproto.OFPP_ANY,
            out_group=ofproto.OFPG_ANY,
            priority=100,
            match=match
        )
        datapath.send_msg(mod)

    @staticmethod
    def _host_to_ip(host):
        if host.startswith('h') and host[1:].isdigit():
            return f"10.0.0.{int(host[1:])}"
        return None

    # ------------------------------------------------------------------
    # CSV watcher thread: track additions/removals globally
    # ------------------------------------------------------------------
    def _watch_allocation_csv(self):
        while True:
            current = set()
            if os.path.exists(ALLOCATED_FLOW_PATH):
                try:
                    with open(ALLOCATED_FLOW_PATH) as f:
                        for line in f:
                            parts = line.strip().split(',')
                            if len(parts) < 4:
                                continue
                            *path, _bw, tid, port = parts
                            dst = path[-1]
                            ip = self._host_to_ip(dst)
                            if not ip:
                                continue
                            key = (ip, int(port), int(tid))
                            current.add(key)
                            if key not in self.active_flows:
                                self.logger.info("🔁 Installing queue flow %s", key)
                                for dp in self.dpset.dps.values():
                                    self.add_queue_flow(dp, ip, int(port), int(tid))
                                self.active_flows.add(key)
                except Exception as e:
                    self.logger.error("Error reading CSV %s: %s", ALLOCATED_FLOW_PATH, e)

            # Remove stale
            for ip, port, qid in self.active_flows - current:
                self.logger.info("❌ Removing queue flow %s", (ip, port, qid))
                for dp in self.dpset.dps.values():
                    self.delete_flow_by_match(dp, ip, port)
                self.active_flows.remove((ip, port, qid))

            hub.sleep(self.poll_interval)

    # ------------------------------------------------------------------
    # Override port-state change to install queues on FORWARD
    # ------------------------------------------------------------------
    @set_ev_cls(stplib.EventPortStateChange, MAIN_DISPATCHER)
    def _port_state_change_handler(self, ev):
        dp = ev.dp
        port_no = ev.port_no
        state = ev.port_state
        dpid_str = dpid_lib.dpid_to_str(dp.id)

        states = {
            stplib.PORT_STATE_DISABLE: 'DISABLE',
            stplib.PORT_STATE_BLOCK:   'BLOCK',
            stplib.PORT_STATE_LISTEN:  'LISTEN',
            stplib.PORT_STATE_LEARN:   'LEARN',
            stplib.PORT_STATE_FORWARD: 'FORWARD',
        }
        name = states.get(state, 'UNKNOWN')
        self.logger.debug("[dpid=%s][port=%d] %s", dpid_str, port_no, name)

        if state == stplib.PORT_STATE_FORWARD:
            self.logger.info(
                "[dpid=%s][port=%d] FORWARD → installing %d queue flows",
                dpid_str, port_no, len(self.active_flows)
            )
            for ip, port, qid in self.active_flows:
                self.add_queue_flow(dp, ip, port, qid)

    # ------------------------------------------------------------------
    # Other handlers delegate to parent for STP & MAC-learning
    # ------------------------------------------------------------------
    @set_ev_cls(stplib.EventTopologyChange, MAIN_DISPATCHER)
    def _topology_change_handler(self, ev):
        super(SimpleSwitch13, self)._topology_change_handler(ev)

    # PacketIn and delete_flow are inherited from the parent app
