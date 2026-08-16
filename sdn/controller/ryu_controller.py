#!/usr/bin/env python3
"""
sdn/controller/ryu_controller.py
Controlador Ryu con inferencia ML en tiempo real, mitigación dinámica
y recolección de métricas de rendimiento.
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


class MLIDSController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(MLIDSController, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.datapaths = {}
        self.flow_history = {}

        self.collector = MetricsCollector()
        
        # Monitorización de CPU: Inicialización previa para evitar lectura 0.0
        self.process = psutil.Process(os.getpid())
        self.process.cpu_percent(interval=None)

        try:
            self.model = joblib.load(MODEL_PATH)
            self.scaler = joblib.load(SCALER_PATH)
            self.selected_features = joblib.load(FEATURES_PATH)
            self.le_y = joblib.load(ENCODER_PATH)

            self.logger.info(f"[+] Modelo ML cargado desde: {MODEL_PATH}")
        except Exception as e:
            self.logger.error(f"[ERROR] Carga de artefactos ML: {e}")
            self.model = None

        self.monitor_thread = hub.spawn(self._monitor)

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

    def block_flow(self, datapath, match_args, priority=100):
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
            hub.sleep(5)

    def _request_stats(self, datapath):
        parser = datapath.ofproto_parser
        req = parser.OFPFlowStatsRequest(datapath)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def flow_stats_reply_handler(self, ev):
        t_start_control = time.perf_counter()  # T0: Recepción del evento
        body = ev.msg.body
        datapath = ev.msg.datapath
        dpid = datapath.id
        now = time.time()
        
        cpu_usage = self.process.cpu_percent(interval=None)

        for stat in body:
            if stat.priority == 0:
                continue

            in_port = stat.match.get('in_port')
            eth_src = stat.match.get('eth_src')
            eth_dst = stat.match.get('eth_dst')
            dst_port = stat.match.get('tcp_dst') or stat.match.get('udp_dst') or 0

            flow_key = (dpid, in_port, eth_src, eth_dst)
            prev_pkts, prev_bytes, prev_time = self.flow_history.get(flow_key, (0, 0, now))
            dt = max(now - prev_time, 1.0)

            pkt_rate = (stat.packet_count - prev_pkts) / dt
            byte_rate = (stat.byte_count - prev_bytes) / dt

            self.flow_history[flow_key] = (stat.packet_count, stat.byte_count, now)

            if self.model and pkt_rate > 0:
                metrics_map = {
                    'pkt_rate': pkt_rate,
                    'byte_rate': byte_rate,
                    'packet_count': stat.packet_count,
                    'byte_count': stat.byte_count,
                    'duration_sec': stat.duration_sec,
                    'Flow Duration': stat.duration_sec,
                    'Tot Pkts': stat.packet_count,
                    'Tot Bytes': stat.byte_count,
                    'Pkt Size Avg': (stat.byte_count / stat.packet_count) if stat.packet_count > 0 else 0,
                    'Flow Byts/s': byte_rate,
                    'Flow Pkts/s': pkt_rate
                }

                X_raw = pd.DataFrame(0.0, index=[0], columns=self.selected_features)
                for col in self.selected_features:
                    if col in metrics_map:
                        X_raw[col] = metrics_map[col]

                try:
                    X_scaled = pd.DataFrame(
                        self.scaler.transform(X_raw),
                        columns=self.selected_features
                    )

                    t_start_inf = time.perf_counter()
                    pred = self.model.predict(X_scaled)[0]
                    inf_latency_ms = (time.perf_counter() - t_start_inf) * 1000

                    pred_label = self.le_y.inverse_transform([pred])[0] if self.le_y else pred
                    is_threat = str(pred_label).lower() not in ["normal", "benign", "0"]
                    action = "DROP" if is_threat else "ALLOW"

                    if is_threat:
                        match_args = {}
                        if in_port:
                            match_args['in_port'] = in_port
                        if eth_src:
                            match_args['eth_src'] = eth_src

                        if match_args:
                            self.block_flow(datapath, match_args)

                    # T1: Tiempo hasta completar procesamiento y dispatch del FlowMod
                    control_latency_ms = (time.perf_counter() - t_start_control) * 1000

                    self.collector.log_event(
                        dpid=dpid,
                        in_port=in_port if in_port else 0,
                        eth_src=eth_src if eth_src else "N/A",
                        dst_port=dst_port,
                        pkt_rate=pkt_rate,
                        byte_rate=byte_rate,
                        inference_time_ms=inf_latency_ms,
                        control_plane_latency_ms=control_latency_ms,
                        cpu_percent=cpu_usage,
                        predicted_label=pred_label,
                        action_taken=action
                    )

                except Exception as e:
                    self.logger.error(f"[ERROR INFERENCIA] {e}")

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