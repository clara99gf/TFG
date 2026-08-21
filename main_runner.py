#!/usr/bin/env python3
"""
main_runner.py
Orquestador principal del ciclo experimental End-to-End.
"""

import os
import sys
import time
import json
import subprocess
import pandas as pd

# Directorio raíz del proyecto
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

RESULTS_DIR = os.path.join(BASE_DIR, "results")
SCENARIO_FILE = os.path.join(RESULTS_DIR, "current_scenario.txt")
METRICS_PATH = os.path.join(RESULTS_DIR, "metrics.csv")
TIMING_FILE = os.path.join(RESULTS_DIR, "timing.csv")
PIDS_FILE = "/tmp/mininet_pids.json"

def check_root():
    if os.geteuid() != 0:
        print("[!] Permisos insuficientes. Ejecuta el script con 'sudo'.")
        sys.exit(1)

def record_timing(scenario_name, battery_start_time=None):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    
    with open(SCENARIO_FILE, "w") as f:
        f.write(scenario_name)
    
    scenario_start_time = time.time()
    
    file_exists = os.path.exists(TIMING_FILE)
    with open(TIMING_FILE, "a") as f:
        if not file_exists:
            f.write("scenario,scenario_start_time,battery_start_time\n")
        f.write(f"{scenario_name},{scenario_start_time},{battery_start_time if battery_start_time else ''}\n")

def clear_switch_flows():
    """Limpia reglas de forwarding dinámicas instaladas por PacketIn (p=1) y mitigaciones (p=200)."""
    print("[+] Limpiando reglas dinámicas en switches OVS...")
    for s in ["s1", "s2", "s3"]:
        subprocess.run(f"ovs-ofctl del-flows {s} 'priority=1'", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(f"ovs-ofctl del-flows {s} 'priority=200'", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def cleanup_environment():
    print("\n[+] Limpiando procesos residuales y estado de Mininet...")
    subprocess.run(["mn", "-c"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["pkill", "-f", "iperf3"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["pkill", "-f", "hping3"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["pkill", "-f", "nmap"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if os.path.exists(PIDS_FILE):
        try:
            os.remove(PIDS_FILE)
        except Exception:
            pass

def reset_metrics_csv():
    if os.path.exists(METRICS_PATH):
        os.remove(METRICS_PATH)
    if os.path.exists(TIMING_FILE):
        os.remove(TIMING_FILE)

def start_ryu_controller():
    print("[+] Desplegando Controlador Ryu con ML-IDS...")
    log_path = os.path.join(BASE_DIR, "ryu_controller.log")
    log_file = open(log_path, "w")
    
    ryu_app_path = os.path.join(BASE_DIR, "sdn", "controller", "ryu_controller.py")
    cmd = [
        sys.executable,
        "-m",
        "ryu.cmd.manager",
        "--ofp-tcp-listen-port",
        "6653",
        ryu_app_path
    ]
    proc = subprocess.Popen(cmd, stdout=log_file, stderr=log_file, cwd=BASE_DIR)
    time.sleep(3)
    return proc, log_file

def get_host_pid(host_name):
    """Obtiene el PID del host de Mininet desde el archivo temporal JSON."""
    if not os.path.exists(PIDS_FILE):
        return None
    try:
        with open(PIDS_FILE, "r") as f:
            pids = json.load(f)
        return pids.get(host_name)
    except Exception:
        return None

def run_cmd_in_netns(host="h2", cmd=""):
    """Ejecuta un comando dentro del namespace del host usando mnexec y su PID."""
    pid = get_host_pid(host)
    if pid:
        full_cmd = f"mnexec -a {pid} {cmd}"
        subprocess.run(full_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        print(f"[!] No se encontró el PID para el host {host}. Comando no ejecutado: {cmd}")

def start_mininet_topology():
    print("[+] Desplegando Topología Mininet...")
    topology_path = os.path.join(BASE_DIR, "sdn", "topology.py")
    cmd = [sys.executable, topology_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=BASE_DIR)
    
    print("[+] Esperando a que la infraestructura OpenFlow responda...")
    ready = False
    for _ in range(15):
        pid_h1 = get_host_pid("h1")
        if pid_h1:
            res = subprocess.run(f"mnexec -a {pid_h1} ping -c 1 -W 1 10.0.0.2", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if res.returncode == 0:
                ready = True
                break
        time.sleep(1)
        
    if ready:
        print("[✔] Infraestructura verificada y totalmente operacional.")
    else:
        print("[!] Tiempo de espera superado. Procediendo con la ejecución...")
        
    return proc

def show_execution_summary():
    if not os.path.exists(METRICS_PATH):
        return
    df = pd.read_csv(METRICS_PATH)
    if df.empty:
        return
    
    print("\n" + "="*60)
    print("      MATRIZ DE PREDICCIONES Y MITIGACIÓN (ML-IDS)")
    print("="*60)
    summary = df.groupby(['scenario', 'predicted_label', 'action_taken']).size().reset_index(name='Muestras')
    for _, row in summary.iterrows():
        print(f" Escenario: {row['scenario'].upper():<10} | Predicción: {row['predicted_label']:<12} | Acción: {row['action_taken']:<5} | Muestras: {row['Muestras']}")
    print("="*60 + "\n")

def run_scenario_normal(duration=20, battery_start_time=None):
    clear_switch_flows()
    print(f"\n[TRÁFICO] Limpiando e iniciando servidor iperf3...")
    run_cmd_in_netns("h1", "pkill -f iperf3")
    time.sleep(0.5)
    run_cmd_in_netns("h1", "iperf3 -s -D")
    time.sleep(1)
    
    record_timing("normal", battery_start_time)
    print(f"[TRÁFICO] Generando Tráfico Benigno (iperf3) durante {duration}s...")
    run_cmd_in_netns("h2", f"iperf3 -c 10.0.0.1 -t {duration} -b 10M -i 1")
    
    run_cmd_in_netns("h1", "pkill -f iperf3")

def run_scenario_ddos(duration=20, battery_start_time=None):
    clear_switch_flows()
    record_timing("ddos", battery_start_time)
    print(f"\n[ATAQUE] Lanzando DDoS SYN Flood (hping3) durante {duration}s...")
    
    pid_h2 = get_host_pid("h2")
    pid_h3 = get_host_pid("h3")
    pid_h4 = get_host_pid("h4")
    
    procs = []
    if pid_h2: procs.append(subprocess.Popen(f"mnexec -a {pid_h2} hping3 --flood -S -p 80 10.0.0.1", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    if pid_h3: procs.append(subprocess.Popen(f"mnexec -a {pid_h3} hping3 --flood -S -p 80 10.0.0.1", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    if pid_h4: procs.append(subprocess.Popen(f"mnexec -a {pid_h4} hping3 --flood -S -p 80 10.0.0.1", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    
    time.sleep(duration)
    
    for p in procs:
        p.terminate()
        p.wait()

def run_scenario_scanning(battery_start_time=None):
    clear_switch_flows()
    record_timing("scanning", battery_start_time)
    print("\n[ATAQUE] Lanzando Escaneo de Puertos Reconocimiento (nmap)...")
    
    run_cmd_in_netns("h2", "nmap -sS -p 1-1000 --min-rate 500 10.0.0.1")
    time.sleep(1)

def run_scenario_spoofing(duration=20, battery_start_time=None):
    clear_switch_flows()
    record_timing("spoofing", battery_start_time)
    print(f"\n[ATAQUE] Lanzando IP Spoofing (hping3 --rand-source) durante {duration}s...")
    
    pid_h2 = get_host_pid("h2")
    if pid_h2:
        p = subprocess.Popen(f"mnexec -a {pid_h2} hping3 -i u2000 --rand-source -S -p 80 10.0.0.1", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(duration)
        p.terminate()
        p.wait()

def run_generate_figures(extra_args=None):
    gen_script = os.path.join(BASE_DIR, "sdn", "generate_figures.py")
    cmd = [sys.executable, gen_script]
    if extra_args:
        cmd.extend(extra_args)
    subprocess.run(cmd, cwd=BASE_DIR)

def run_all_scenarios():
    print("\n" + "="*60)
    print(" EJECUTANDO BATERÍA COMPLETA DE EVALUACIÓN EXPERIMENTAL")
    print("="*60)
    
    reset_metrics_csv()
    battery_start_time = time.time()
    
    run_scenario_normal(duration=20, battery_start_time=battery_start_time)
    time.sleep(2)
    run_scenario_ddos(duration=20, battery_start_time=battery_start_time)
    time.sleep(2)
    run_scenario_scanning(battery_start_time=battery_start_time)
    time.sleep(2)
    run_scenario_spoofing(duration=20, battery_start_time=battery_start_time)
    time.sleep(2)
    
    show_execution_summary()
    print("[+] Generando figuras de red, métricas de infraestructura y tiempos de inferencia...")
    run_generate_figures(["--full"])

def interactive_menu(ryu_proc, mn_proc, log_file):
    while True:
        print("\n" + "="*55)
        print("    MENÚ INTEGRADO DE SIMULACIÓN SDN - TFG")
        print("="*55)
        print("1. Probar Tráfico Normal (iperf3) [Sin Figuras]")
        print("2. Probar Ataque DDoS (hping3) [Genera ddos_mitigation.png]")
        print("3. Probar Scanning (nmap) [Genera scanning_mitigation.png]")
        print("4. Probar IP Spoofing [Genera spoofing_mitigation.png]")
        print("5. EJECUTAR BATERÍA COMPLETA [Genera 4 Figuras + Resumen CSV]")
        print("0. Salir y Limpiar Entorno")
        print("="*55)
        
        op = input("Selecciona una opción [0-5]: ").strip()
        
        if op == "1":
            reset_metrics_csv()
            run_scenario_normal()
            show_execution_summary()
        elif op == "2":
            reset_metrics_csv()
            run_scenario_ddos()
            show_execution_summary()
            run_generate_figures(["--scenario", "ddos"])
        elif op == "3":
            reset_metrics_csv()
            run_scenario_scanning()
            show_execution_summary()
            run_generate_figures(["--scenario", "scanning"])
        elif op == "4":
            reset_metrics_csv()
            run_scenario_spoofing()
            show_execution_summary()
            run_generate_figures(["--scenario", "spoofing"])
        elif op == "5":
            run_all_scenarios()
        elif op == "0":
            print("[+] Saliendo del entorno experimental...")
            break

    if mn_proc: mn_proc.terminate()
    if ryu_proc: ryu_proc.terminate()
    if log_file: log_file.close()
    cleanup_environment()

def main():
    check_root()
    cleanup_environment()
    
    ryu_proc, log_file = start_ryu_controller()
    mn_proc = start_mininet_topology()
    
    try:
        interactive_menu(ryu_proc, mn_proc, log_file)
    except KeyboardInterrupt:
        print("\n[!] Proceso interrumpido.")
        cleanup_environment()

if __name__ == '__main__':
    main()