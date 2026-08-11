#!/usr/bin/env python3
"""
sdn/controller/ryu_controller.py
Controlador Ryu con inferencia ML en tiempo real, mitigación dinámica
y recolección de métricas para el TFG.
"""

import os
import time
import joblib
import numpy as np
import pandas as pd

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib import hub
from ryu.lib.packet import packet, ethernet, ether_types

# Módulo recolector de métricas
from sdn.metrics_collector import MetricsCollector

# Rutas de los artefactos generados en el entrenamiento
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

        # Instanciar el recolector de métricas
        self.collector = MetricsCollector()

        # Cargar artefactos del pipeline de ML
        try:
            self.model = joblib.load(MODEL_PATH)
            self.scaler = joblib.load(SCALER_PATH)
            self.selected_features = joblib.load(FEATURES_PATH)
            self.le_y = joblib.load(ENCODER_PATH)

            self.logger.info(f"[+] Modelo ML cargado exitosamente desde: {MODEL_PATH}")
            self.logger.info(f"[+] Scaler y Top-{len(self.selected_features)} características cargados.")
        except Exception as e:
            self.logger.error(f"[ERROR] No se pudieron cargar los artefactos de ML: {e}")
            self.model = None

        # Hilo de monitoreo (consulta de estadísticas cada 5 segundos)
        self.monitor_thread = hub.spawn(self._monitor)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        """Instala la regla por defecto Table-Miss (enviar al controlador)."""
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        self.datapaths[datapath.id] = datapath

        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)
        self.logger.info(f"[+] Switch conectado: DPID {datapath.id}")

    def add_flow(self, datapath, priority, match, actions, idle_timeout=0, hard_timeout=0):
        """Añade una regla de flujo al conmutador."""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(
            datapath=datapath, priority=priority, match=match,
            instructions=inst, idle_timeout=idle_timeout, hard_timeout=hard_timeout
        )
        datapath.send_msg(mod)

    def block_flow(self, datapath, match_args, priority=100):
        """Aplica mitigación inyectando una regla DROP de alta prioridad."""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        match = parser.OFPMatch(**match_args)
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, [])]  # Acción vacía = DROP
        mod = parser.OFPFlowMod(
            datapath=datapath, priority=priority, match=match,
            instructions=inst, hard_timeout=300  # Bloqueo durante 5 minutos
        )
        datapath.send_msg(mod)
        self.logger.info(f"[!] REGLA DE MITIGACIÓN APLICADA (DROP) en DPID {datapath.id}: {match_args}")

    def _monitor(self):
        """Hilo en segundo plano para solicitar estadísticas periódicamente."""
        while True:
            for dp in list(self.datapaths.values()):
                self._request_stats(dp)
            hub.sleep(5)

    def _request_stats(self, datapath):
        """Solicita estadísticas de flujos al conmutador."""
        parser = datapath.ofproto_parser
        req = parser.OFPFlowStatsRequest(datapath)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def flow_stats_reply_handler(self, ev):
        """Procesa métricas, las escala, ejecuta inferencia, registra en CSV y aplica mitigación."""
        body = ev.msg.body
        datapath = ev.msg.datapath
        dpid = datapath.id
        now = time.time()

        for stat in body:
            if stat.priority == 0:
                continue

            in_port = stat.match.get('in_port')
            eth_src = stat.match.get('eth_src')
            eth_dst = stat.match.get('eth_dst')

            flow_key = (dpid, in_port, eth_src, eth_dst)
            prev_pkts, prev_bytes, prev_time = self.flow_history.get(flow_key, (0, 0, now))
            dt = max(now - prev_time, 1.0)

            pkt_rate = (stat.packet_count - prev_pkts) / dt
            byte_rate = (stat.byte_count - prev_bytes) / dt

            self.flow_history[flow_key] = (stat.packet_count, stat.byte_count, now)

            if self.model and pkt_rate > 0:
                # Mapeo de métricas hacia los nombres posibles del dataset InSDN
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

                # Construir DataFrame con las Top-N características seleccionadas
                X_raw = pd.DataFrame(0.0, index=[0], columns=self.selected_features)
                for col in self.selected_features:
                    if col in metrics_map:
                        X_raw[col] = metrics_map[col]

                try:
                    # Escalado estandarizado idéntico al entrenamiento
                    X_scaled = pd.DataFrame(
                        self.scaler.transform(X_raw),
                        columns=self.selected_features
                    )

                    start_lat = time.time()
                    pred = self.model.predict(X_scaled)[0]
                    latency = (time.time() - start_lat) * 1000

                    # Descodificar la predicción
                    pred_label = self.le_y.inverse_transform([pred])[0] if self.le_y else pred
                    
                    # Determinar si es tráfico anómalo o normal
                    is_threat = str(pred_label).lower() not in ["normal", "benign", "0"]
                    action = "DROP" if is_threat else "ALLOW"

                    # Registrar la métrica en el CSV (results/metrics.csv)
                    self.collector.log_event(
                        dpid=dpid,
                        in_port=in_port if in_port else 0,
                        eth_src=eth_src if eth_src else "N/A",
                        pkt_rate=pkt_rate,
                        byte_rate=byte_rate,
                        inference_time_ms=latency,
                        predicted_label=pred_label,
                        action_taken=action
                    )

                    # Aplicar bloqueo si es una amenaza
                    if is_threat:
                        self.logger.warning(
                            f"[ALERTA ML] Tráfico Anómalo Detectado: Clase '{pred_label}' "
                            f"en DPID {dpid} | In_Port: {in_port} | Latencia: {latency:.2f}ms"
                        )
                        match_args = {}
                        if in_port:
                            match_args['in_port'] = in_port
                        if eth_src:
                            match_args['eth_src'] = eth_src

                        if match_args:
                            self.block_flow(datapath, match_args)

                except Exception as e:
                    self.logger.error(f"[ERROR INFERENCIA] {e}")

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        """Conmutador L2 básico (Learning Switch)."""
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