#!/usr/bin/env python3
"""
sdn/metrics_collector.py
Módulo de recolección y persistencia de métricas de red, rendimiento e inferencia.
"""

import os
import csv
import time

class MetricsCollector:
    def __init__(self, output_path="results/metrics.csv"):
        self.output_path = output_path
        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
        self._init_csv()

    def _init_csv(self):
        """Inicializa el archivo CSV escribiendo las cabeceras si no existe."""
        if not os.path.exists(self.output_path) or os.path.getsize(self.output_path) == 0:
            headers = [
                "timestamp",
                "dpid",
                "in_port",
                "eth_src",
                "dst_port",
                "pkt_rate",
                "byte_rate",
                "inference_time_ms",
                "mitigation_latency_ms",
                "cpu_percent",
                "predicted_label",
                "action_taken",
                "scenario"
            ]
            with open(self.output_path, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(headers)

    def log_event(self, dpid, in_port, eth_src, dst_port, pkt_rate, byte_rate,
                  inference_time_ms, mitigation_latency_ms, cpu_percent,
                  predicted_label, action_taken, scenario):
        """Registra un evento de telemetría en tiempo real."""
        self._init_csv()

        row = [
            time.time(),
            dpid,
            in_port,
            eth_src,
            dst_port,
            round(pkt_rate, 2),
            round(byte_rate, 2),
            round(inference_time_ms, 3),
            round(mitigation_latency_ms, 3),
            round(cpu_percent, 2),
            predicted_label,
            action_taken,
            scenario
        ]

        with open(self.output_path, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(row)