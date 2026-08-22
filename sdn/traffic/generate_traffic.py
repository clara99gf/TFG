#!/usr/bin/env python3
"""
sdn/traffic/generate_traffic.py
Generación multiclase de tráfico (Normal, DDoS, Scanning, Spoofing) en Mininet.
Controles de inicio/fin de grabación con vaciado garantizado de datos previo.
"""
import os
import sys
import time
import json
import csv
import subprocess

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from config.config import DATA_RAW_PATH, RESULTS_DIR

SCENARIO_FILE = os.path.join(RESULTS_DIR, "current_scenario.txt")
PIDS_FILE = "/tmp/mininet_pids.json"
RECORD_FLAG_FILE = "/tmp/record_mode.flag"

CSV_HEADERS = [
    "Flow Duration", "Flow Pkts/s", "Flow Byts/s", "Pkt Len Mean",
    "byte_count", "packet_count", "priority", "table_id",
    "hard_timeout", "idle_timeout", "flags", "Label"
]


def clean_and_init_dataset():
    """Vacía el contenido del CSV previo dejando únicamente los encabezados."""
    os.makedirs(os.path.dirname(DATA_RAW_PATH), exist_ok=True)
    try:
        with open(DATA_RAW_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADERS)
        print(f"[+] Contenido del CSV vaciado e inicializado en: '{DATA_RAW_PATH}'")
    except Exception as e:
        print(f"[!] Error al vaciar el CSV: {e}")


def enable_recording():
    """Vacía el CSV y activa el flag de captura para Ryu."""
    clean_and_init_dataset()
    with open(RECORD_FLAG_FILE, "w") as f:
        f.write("1")
    print("[+] Grabación de tráfico ACTIVADA.")


def disable_recording():
    """Desactiva la grabación en Ryu eliminando el flag."""
    if os.path.exists(RECORD_FLAG_FILE):
        try:
            os.remove(RECORD_FLAG_FILE)
            print("[+] Grabación de tráfico DESACTIVADA.")
        except Exception:
            pass


def get_host_pid(host_name: str):
    """Obtiene el PID del host desde el archivo de la topología."""
    if not os.path.exists(PIDS_FILE):
        return None
    try:
        with open(PIDS_FILE, "r") as f:
            pids = json.load(f)
        return pids.get(host_name)
    except Exception:
        return None


def run_cmd_in_netns(host: str, cmd: str):
    """Ejecuta un comando síncrono en el namespace del host."""
    pid = get_host_pid(host)
    if pid:
        full_cmd = f"mnexec -a {pid} {cmd}"
        subprocess.run(full_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def popen_cmd_in_netns(host: str, cmd: str):
    """Lanza un comando asíncrono en el namespace del host."""
    pid = get_host_pid(host)
    if pid:
        full_cmd = f"mnexec -a {pid} {cmd}"
        return subprocess.Popen(full_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return None


def kill_all_traffic_processes():
    """Detiene cualquier proceso de tráfico residual."""
    for host in ["h1", "h2", "h3", "h4", "h5"]:
        run_cmd_in_netns(host, "pkill -9 -f iperf3")
        run_cmd_in_netns(host, "pkill -9 -f hping3")
        run_cmd_in_netns(host, "pkill -9 -f nmap")
        run_cmd_in_netns(host, "pkill -9 -f ping")


def set_controller_scenario(scenario_name: str):
    """Informa al controlador Ryu del escenario activo."""
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(SCENARIO_FILE, "w") as f:
        f.write(scenario_name)
    print(f"\n[+] Escenario activo cambiado a: >>> {scenario_name.upper()} <<<")


def run_traffic_generation():
    if not os.path.exists(PIDS_FILE):
        print("[ERROR] No se detectó la topología activa de Mininet.")
        print("[!] Inicia primero la red con: sudo python3 sdn/topology.py")
        sys.exit(1)

    print("==========================================================")
    print("   GENERACIÓN AUTOMÁTICA DE DATASET MULTICLASE (MININET)  ")
    print("==========================================================")

    kill_all_traffic_processes()
    enable_recording()

    try:
        # 1. TRÁFICO NORMAL (30s)
        set_controller_scenario("normal")
        print("[+] Generando Tráfico Normal (iperf3 y pings)...")
        run_cmd_in_netns("h1", "iperf3 -s -D")
        time.sleep(1)

        procs = []
        p1 = popen_cmd_in_netns("h2", "iperf3 -c 10.0.0.1 -t 30 -b 10M")
        if p1: procs.append(p1)
        p2 = popen_cmd_in_netns("h3", "ping -i 0.2 10.0.0.1")
        if p2: procs.append(p2)

        time.sleep(30)
        for p in procs:
            if p:
                p.terminate()
                p.wait()
        kill_all_traffic_processes()
        time.sleep(1)

        # 2. DDOS (30s)
        set_controller_scenario("ddos")
        print("[+] Generando Tráfico DDoS (hping3)...")
        procs = []
        p1 = popen_cmd_in_netns("h2", "hping3 -i u1000 -S -p 80 10.0.0.1")
        if p1: procs.append(p1)
        p2 = popen_cmd_in_netns("h3", "hping3 -i u1000 -S -p 80 10.0.0.1")
        if p2: procs.append(p2)

        time.sleep(30)
        for p in procs:
            if p:
                p.terminate()
                p.wait()
        kill_all_traffic_processes()
        time.sleep(1)

        # 3. SCANNING (15s)
        set_controller_scenario("scanning")
        print("[+] Generando Tráfico Scanning (nmap)...")
        p_bg = popen_cmd_in_netns("h2", "ping -i 0.2 10.0.0.1")
        p_scan = popen_cmd_in_netns("h2", "nmap -sS -p 1-1000 --min-rate 500 10.0.0.1")

        time.sleep(15)
        if p_scan:
            p_scan.terminate()
            p_scan.wait()
        if p_bg:
            p_bg.terminate()
            p_bg.wait()
        kill_all_traffic_processes()
        time.sleep(1)

        # 4. SPOOFING (30s)
        set_controller_scenario("spoofing")
        print("[+] Generando Tráfico IP Spoofing...")
        procs = []
        p_bg = popen_cmd_in_netns("h1", "ping -i 0.2 10.0.0.1")
        if p_bg: procs.append(p_bg)
        p_spf = popen_cmd_in_netns("h4", "hping3 -i u2000 -a 10.0.0.99 -S -p 80 10.0.0.1")
        if p_spf: procs.append(p_spf)

        time.sleep(30)
        for p in procs:
            if p:
                p.terminate()
                p.wait()
        kill_all_traffic_processes()

    finally:
        disable_recording()
        kill_all_traffic_processes()

        if os.path.exists(SCENARIO_FILE):
            try:
                os.remove(SCENARIO_FILE)
            except Exception:
                pass

        print(f"\n[✔] Generación completada con éxito. Datos capturados en: {DATA_RAW_PATH}")
        print("[+] Grabación finalizada. La red queda en reposo sin registrar más datos.")


if __name__ == "__main__":
    run_traffic_generation()