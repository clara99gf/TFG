#!/usr/bin/env python3
"""
sdn/controller/ryu_controller.py
Controlador Ryu Learning Switch + Recolector de Dataset en tiempo real.
"""
import os
import sys
import csv
import time
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, DEAD_DISPATCHER, CONFIG_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib import hub
from ryu.lib.packet import packet, ethernet, ether_types

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from config.config import DATA_RAW_PATH, RESULTS_DIR

SCENARIO_FILE = os.path.join(RESULTS_DIR, "current_scenario.txt")
RECORD_FLAG_FILE = "/tmp/record_mode.flag"

CSV_HEADERS = [
    "Flow Duration", "Flow Pkts/s", "Flow Byts/s", "Pkt Len Mean",
    "byte_count", "packet_count", "priority", "table_id",
    "hard_timeout", "idle_timeout", "flags", "Label"
]


class RyuMLController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(RyuMLController, self).__init__(*args, **kwargs)
        self.datapaths = {}
        self.mac_to_port = {}
        self.flow_history = {}
        self.last_recording_state = False
        self.monitor_thread = hub.spawn(self._monitor)

    def _is_recording_enabled(self):
        return os.path.exists(RECORD_FLAG_FILE)

    def _ensure_csv_headers(self):
        """Crea el directorio y el archivo CSV con los encabezados si está vacío."""
        try:
            os.makedirs(os.path.dirname(DATA_RAW_PATH), exist_ok=True)
            if not os.path.isfile(DATA_RAW_PATH) or os.path.getsize(DATA_RAW_PATH) == 0:
                with open(DATA_RAW_PATH, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(CSV_HEADERS)
                self.logger.info(f"[+] Archivo CSV listo con encabezados en: {DATA_RAW_PATH}")
        except Exception as e:
            self.logger.error(f"[ERROR INICIALIZACIÓN CSV] {e}")

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

    def add_flow(self, datapath, priority, match, actions, buffer_id=None, idle=0, hard=0):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                    priority=priority, match=match,
                                    instructions=inst, idle_timeout=idle, hard_timeout=hard)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst,
                                    idle_timeout=idle, hard_timeout=hard)
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        dst = eth.dst
        src = eth.src
        dpid = datapath.id

        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][src] = in_port

        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]

        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst)
            if msg.buffer_id != ofproto.OFP_NO_BUFFER:
                self.add_flow(datapath, 1, match, actions, msg.buffer_id, idle=0, hard=0)
            else:
                self.add_flow(datapath, 1, match, actions, idle=0, hard=0)

        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)

    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def _state_change_handler(self, ev):
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            if datapath.id not in self.datapaths:
                self.logger.info(f"[+] Switch registrado para monitoreo: dpid={datapath.id}")
                self.datapaths[datapath.id] = datapath
        elif ev.state == DEAD_DISPATCHER:
            if datapath.id in self.datapaths:
                self.logger.info(f"[-] Switch desconectado: dpid={datapath.id}")
                del self.datapaths[datapath.id]

    def _monitor(self):
        while True:
            for dp in list(self.datapaths.values()):
                self._request_stats(dp)
            hub.sleep(1)

    def _request_stats(self, datapath):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        req = parser.OFPFlowStatsRequest(datapath)
        datapath.send_msg(req)

    def _get_current_scenario(self):
        if os.path.exists(SCENARIO_FILE):
            try:
                with open(SCENARIO_FILE, "r") as f:
                    return f.read().strip()
            except Exception:
                pass
        return "normal"

    def _append_to_raw_csv(self, features_dict, label):
        try:
            self._ensure_csv_headers()
            row = list(features_dict.values()) + [label]

            with open(DATA_RAW_PATH, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(row)

            self.logger.info(f"[+] Muestra guardada -> Escenario: {label}")
        except Exception as e:
            self.logger.error(f"[ERROR ESCRITURA CSV] {e}")

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def flow_stats_reply_handler(self, ev):
        is_rec = self._is_recording_enabled()

        if is_rec != self.last_recording_state:
            self.flow_history.clear()
            self.last_recording_state = is_rec
            if is_rec:
                self._ensure_csv_headers()
                self.logger.info("[REC] MODO GRABACIÓN ACTIVADO")
            else:
                self.logger.info("[REC] MODO GRABACIÓN DESACTIVADO")

        if not is_rec:
            return

        body = ev.msg.body
        current_scenario = self._get_current_scenario()
        now = time.time()

        for stat in body:
            match_items = tuple(sorted(stat.match.items()))
            flow_key = (ev.msg.datapath.id, stat.table_id, match_items)

            curr_pkts = stat.packet_count
            curr_bytes = stat.byte_count

            if flow_key in self.flow_history:
                prev_pkts, prev_bytes, prev_time = self.flow_history[flow_key]
                dt = now - prev_time

                if dt > 0.1:
                    delta_pkts = curr_pkts - prev_pkts
                    delta_bytes = curr_bytes - prev_bytes

                    # Permite guardar métricas cuando hay actividad o acumulados del flujo
                    if delta_pkts > 0 or curr_pkts > 0:
                        effective_pkts = max(delta_pkts, 1)
                        pkt_rate = delta_pkts / dt if delta_pkts >= 0 else 0
                        byte_rate = delta_bytes / dt if delta_bytes >= 0 else 0
                        pkt_len_mean = delta_bytes / effective_pkts if delta_bytes >= 0 else 0

                        features_map = {
                            "Flow Duration": round(stat.duration_sec + stat.duration_nsec * 1e-9, 4),
                            "Flow Pkts/s": round(max(pkt_rate, 0), 4),
                            "Flow Byts/s": round(max(byte_rate, 0), 4),
                            "Pkt Len Mean": round(max(pkt_len_mean, 0), 4),
                            "byte_count": curr_bytes,
                            "packet_count": curr_pkts,
                            "priority": stat.priority,
                            "table_id": stat.table_id,
                            "hard_timeout": stat.hard_timeout,
                            "idle_timeout": stat.idle_timeout,
                            "flags": stat.flags
                        }

                        self._append_to_raw_csv(features_map, current_scenario)

            self.flow_history[flow_key] = (curr_pkts, curr_bytes, now)