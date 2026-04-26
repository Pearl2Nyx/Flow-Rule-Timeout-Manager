from os_ken.base import app_manager
from os_ken.controller import ofp_event
from os_ken.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER, set_ev_cls
from os_ken.ofproto import ofproto_v1_3
import time
import threading

# -------------------------------
# Flow Entry Class
# -------------------------------
class FlowEntry:
    def __init__(self, datapath, match, idle_timeout, hard_timeout):
        self.datapath = datapath
        self.match = match
        self.idle_timeout = idle_timeout
        self.hard_timeout = hard_timeout
        self.created_time = time.time()
        self.last_used = time.time()


# -------------------------------
# Main App
# -------------------------------
class FlowTimeoutApp(app_manager.OSKenApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(FlowTimeoutApp, self).__init__(*args, **kwargs)
        self.flow_table = []

        t = threading.Thread(target=self.timeout_manager)
        t.daemon = True
        t.start()

    # -------------------------------
    # Switch connects → table-miss
    # -------------------------------
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER)]

        inst = [parser.OFPInstructionActions(
            ofproto.OFPIT_APPLY_ACTIONS, actions)]

        mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=0,
            match=match,
            instructions=inst
        )

        datapath.send_msg(mod)
        print("[*] Switch connected → Table-miss installed")

    # -------------------------------
    # Packet In → install flow
    # -------------------------------
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        in_port = msg.match['in_port']

        match = parser.OFPMatch(in_port=in_port)
        actions = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]

        self.add_flow(datapath, match, actions, idle=10, hard=30)

        flow = FlowEntry(datapath, match, 10, 30)
        self.flow_table.append(flow)

        print(f"[+] Flow added | port={in_port}")

    # -------------------------------
    # Add flow
    # -------------------------------
    def add_flow(self, datapath, match, actions, idle, hard):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        inst = [parser.OFPInstructionActions(
            ofproto.OFPIT_APPLY_ACTIONS, actions)]

        mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=1,
            match=match,
            instructions=inst,
            idle_timeout=idle,
            hard_timeout=hard
        )

        datapath.send_msg(mod)

    # -------------------------------
    # Timeout Manager
    # -------------------------------
    def timeout_manager(self):
        while True:
            now = time.time()

            for flow in self.flow_table[:]:
                if flow.idle_timeout > 0 and now - flow.last_used > flow.idle_timeout:
                    self.remove_flow(flow, "Idle Timeout")

                elif flow.hard_timeout > 0 and now - flow.created_time > flow.hard_timeout:
                    self.remove_flow(flow, "Hard Timeout")

            time.sleep(2)

    # -------------------------------
    # Remove flow
    # -------------------------------
    def remove_flow(self, flow, reason):
        datapath = flow.datapath
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        mod = parser.OFPFlowMod(
            datapath=datapath,
            command=ofproto.OFPFC_DELETE,
            match=flow.match
        )

        datapath.send_msg(mod)

        self.flow_table.remove(flow)

        print(f"[-] Flow removed ({reason})")
