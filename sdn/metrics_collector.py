#!/usr/bin/env python3
"""
sdn/metrics_collector.py
Módulo para el registro persistente de métricas de telemetría e inferencia ML.
"""

import os
import csv
import time
from threading import Lock

class MetricsCollector:
    def __init__(self, output_dir="results", filename="metrics.csv"):
        self.output_dir = output_dir
        self.filepath = os.path.join(self.output_dir, filename)
        self.lock = Lock()
        
        # Crear directorio si no existe
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir, exist_ok=True)
            
        # Inicializar CSV con encabezados si no existe
        if not os.path.exists(self.filepath):
            with open(self.filepath, mode='w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp', 
                    'dpid', 
                    'in_port', 
                    'eth_src', 
                    'pkt_rate', 
                    'byte_rate', 
                    'inference_time_ms', 
                    'predicted_label', 
                    'action_taken'
                ])

    def log_event(self, dpid, in_port, eth_src, pkt_rate, byte_rate, inference_time_ms, predicted_label, action_taken):
        """Registra un evento de evaluación e inferencia de forma segura entre hilos."""
        with self.lock:
            with open(self.filepath, mode='a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    time.time(),
                    dpid,
                    in_port,
                    eth_src,
                    round(pkt_rate, 2),
                    round(byte_rate, 2),
                    round(inference_time_ms, 3),
                    predicted_label,
                    action_taken
                ])