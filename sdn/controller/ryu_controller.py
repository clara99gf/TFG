#!/usr/bin/env python3
"""
sdn/controller/ryu_controller.py
Controlador Ryu con medición precisa de la latencia de mitigación por flujo.
"""

import os
import time
import psutil
import joblib
import pandas as pd

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib import hub
from ryu.lib.packet import packet, ethernet, ether_types

from sdn.metrics_collector import MetricsCollector

MODELS_DIR = "models"
MODEL_PATH = os.path.join(MODELS_DIR, "modelo_final.pkl")
SCALER_PATH = os.path.join(MODELS_DIR, "scaler.pkl")
FEATURES_PATH = os.path.join(MODELS_DIR, "selected_features.pkl")
ENCODER_PATH = os.path.join(MODELS_DIR, "le_y.pkl")
SCENARIO_FILE = "results/current_scenario.txt"
TIMING_FILE = "results/timing.csv"

class MLIDSController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(MLIDSController, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.datapaths = {}
        self.flow_history = {}
        
        self.collector = MetricsCollector()
        self.process = psutil.Process(os.getpid())
        self.process.cpu_percent(interval=None)

        try:
            self.model = joblib.load(MODEL_PATH)
            self.scaler = joblib.load(SCALER_PATH)
            self.selected_features = joblib.load(FEATURES_PATH)
            self.le_y = joblib.load(ENCODER_PATH)
            print(f"\n[+] Modelo ML cargado exitosamente. Features: {self.selected_features}\n")
        except Exception as e:
            print(f"[ERROR] Carga de artefactos ML: {e}")
            self.model = None

        self.monitor_thread = hub.spawn(self._monitor)

    def _get_current_scenario_info(self):
        scenario = "normal"
        if os.path.exists(SCENARIO_FILE):
            with open(SCENARIO_FILE, "r") as f:
                scenario = f.read().strip()
        
        t_scenario_start = time.time()
        t_battery_start = None
        
        if os.path.exists(TIMING_FILE):
            try:
                df_t = pd.read_csv(TIMING_FILE)
                if not df_t.empty:
                    match_sc = df_t[df_t['scenario'] == scenario]
                    if not match_sc.empty:
                        t_scenario_start = match_sc['scenario_start_time'].iloc[-1]
                    if 'battery_start_time' in df_t.columns and not df_t['battery_start_time'].isna().all():
                        t_battery_start = df_t['battery_start_time'].dropna().iloc[-1]
            except Exception:
                pass

        return scenario, t_scenario_start, t_battery_start

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        self.datapaths[datapath.id] = datapath
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

    def add_flow(self, datapath, priority, match, actions, idle_timeout=0, hard_timeout=0):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(
            datapath=datapath, priority=priority, match=match,
            instructions=inst, idle_timeout=idle_timeout, hard_timeout=hard_timeout
        )
        datapath.send_msg(mod)

    def block_flow(self, datapath, match_args, priority=200):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        match = parser.OFPMatch(**match_args)
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, [])]
        mod = parser.OFPFlowMod(
            datapath=datapath, priority=priority, match=match,
            instructions=inst, hard_timeout=300
        )
        datapath.send_msg(mod)

    def _monitor(self):
        while True:
            for dp in list(self.datapaths.values()):
                self._request_stats(dp)
            hub.sleep(1)

    def _request_stats(self, datapath):
        parser = datapath.ofproto_parser
        req = parser.OFPFlowStatsRequest(datapath)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def flow_stats_reply_handler(self, ev):
        body = ev.msg.body
        datapath = ev.msg.datapath
        dpid = datapath.id
        now = time.time()
        
        cpu_usage = self.process.cpu_percent(interval=None)
        current_scenario, t_sc_start, t_bat_start = self._get_current_scenario_info()
        t_sc_rel = max(0.0, now - t_sc_start)

        for stat in body:
            # Medición exacta desde la inspección de esta regla estadística
            t_start_flow_eval = time.perf_counter()

            if stat.priority == 0:
                continue

            in_port = stat.match.get('in_port')
            eth_src = stat.match.get('eth_src')
            eth_dst = stat.match.get('eth_dst')
            dst_port = stat.match.get('tcp_dst') or stat.match.get('udp_dst') or 0

            flow_key = (dpid, in_port, eth_src, eth_dst, dst_port)
            prev_pkts, prev_bytes, prev_time = self.flow_history.get(flow_key, (0, 0, now))
            dt = max(now - prev_time, 1.0)

            packet_count = stat.packet_count
            byte_count = stat.byte_count
            flow_duration = stat.duration_sec + (stat.duration_nsec / 1e9)

            pkt_rate = (packet_count - prev_pkts) / dt
            byte_rate = (byte_count - prev_bytes) / dt
            pkt_len_mean = (byte_count / packet_count) if packet_count > 0 else 0

            self.flow_history[flow_key] = (packet_count, byte_count, now)

            if self.model and pkt_rate > 0:
                # Mapeo ajustado estrictamente a las Top 6 características seleccionadas
                features_map = {
                    'Flow Duration': flow_duration,
                    'Flow Pkts/s': pkt_rate,
                    'Pkt Len Mean': pkt_len_mean,
                    'byte_count': byte_count,
                    'Flow Byts/s': byte_rate,
                    'packet_count': packet_count
                }

                X_raw = pd.DataFrame([features_map])[self.selected_features]

                try:
                    X_scaled = pd.DataFrame(self.scaler.transform(X_raw), columns=self.selected_features)

                    t_start_inf = time.perf_counter()
                    pred = self.model.predict(X_scaled)[0]
                    inf_latency_ms = (time.perf_counter() - t_start_inf) * 1000

                    pred_label = self.le_y.inverse_transform([pred])[0] if self.le_y else str(pred)
                    pred_str = str(pred_label).lower()
                    
                    is_threat = pred_str not in ["normal", "benign", "0"]
                    action = "DROP" if is_threat else "ALLOW"
                    mitigation_latency_ms = 0.0

                    if is_threat:
                        match_args = {}
                        if current_scenario == "spoofing":
                            if in_port: match_args['in_port'] = in_port
                        else:
                            if in_port: match_args['in_port'] = in_port
                            if eth_src: match_args['eth_src'] = eth_src

                        if match_args:
                            self.block_flow(datapath, match_args)
                            # Latencia de mitigación individual: desde el inicio de evaluación hasta el envío del OFPFlowMod DROP
                            mitigation_latency_ms = (time.perf_counter() - t_start_flow_eval) * 1000

                    if t_bat_start is not None:
                        t_bat_rel = now - t_bat_start
                        print(f"[ML] Global t={t_bat_rel:5.2f}s | Escenario: {current_scenario:<8} | t_escenario={t_sc_rel:5.2f}s | Pred: {pred_label:<10} | Acción: {action}")
                    else:
                        print(f"[ML] t={t_sc_rel:5.2f}s | Escenario: {current_scenario:<8} | Predicción: {pred_label:<10} | Acción: {action}")

                    self.collector.log_event(
                        dpid=dpid,
                        in_port=in_port if in_port else 0,
                        eth_src=eth_src if eth_src else "N/A",
                        dst_port=dst_port,
                        pkt_rate=pkt_rate,
                        byte_rate=byte_rate,
                        inference_time_ms=inf_latency_ms,
                        mitigation_latency_ms=mitigation_latency_ms,
                        cpu_percent=cpu_usage,
                        predicted_label=pred_label,
                        action_taken=action,
                        scenario=current_scenario
                    )

                except Exception as e:
                    self.logger.error(f"[ERROR INFERENCIA ML] {e}")

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match.get('in_port')

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        dst = eth.dst
        src = eth.src
        dpid = datapath.id

        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][src] = in_port

        out_port = self.mac_to_port[dpid].get(dst, ofproto.OFPP_FLOOD)
        actions = [parser.OFPActionOutput(out_port)]

        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst, eth_src=src)
            self.add_flow(datapath, 1, match, actions, idle_timeout=20, hard_timeout=100)

        data = msg.data if msg.buffer_id == ofproto.OFP_NO_BUFFER else None
        out = parser.OFPPacketOut(
            datapath=datapath, buffer_id=msg.buffer_id,
            in_port=in_port, actions=actions, data=data
        )
        datapath.send_msg(out)