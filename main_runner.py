#!/usr/bin/env python3
"""
main_runner.py
Orquestador principal con aislamiento de escenarios y matriz de predicciones.
"""

import os
import sys
import time
import subprocess
import pandas as pd

SCENARIO_FILE = "results/current_scenario.txt"
METRICS_PATH = "results/metrics.csv"

def check_root():
    if os.geteuid() != 0:
        print("[!] Este script requiere permisos de superusuario ('sudo').")
        sys.exit(1)

def set_scenario(scenario_name):
    os.makedirs("results", exist_ok=True)
    with open(SCENARIO_FILE, "w") as f:
        f.write(scenario_name)

def clear_switch_flows():
    """Elimina reglas dinámicas en los switches OVS para restaurar el estado limpio en cada prueba."""
    print("[+] Limpiando reglas de flujo OpenFlow en los switches...")
    subprocess.run("ovs-ofctl del-flows s1", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def cleanup_environment():
    print("\n[+] Limpiando entorno Mininet y procesos residuales...")
    subprocess.run(["mn", "-c"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["pkill", "-f", "ryu-manager"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["pkill", "-f", "iperf3"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["pkill", "-f", "hping3"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["pkill", "-f", "nmap"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def reset_metrics_csv():
    if os.path.exists(METRICS_PATH):
        os.remove(METRICS_PATH)

def start_ryu_controller():
    print("[+] Iniciando Controlador Ryu con ML-IDS...")
    log_file = open("ryu_controller.log", "w")
    cmd = ["ryu-manager", "sdn/controller/ryu_controller.py"]
    proc = subprocess.Popen(cmd, stdout=log_file, stderr=log_file)
    time.sleep(3)
    return proc, log_file

def start_mininet_topology():
    print("[+] Desplegando Topología Mininet...")
    cmd = ["python3", "sdn/topology.py"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(4)
    return proc

def run_cmd_in_netns(host="h2", cmd=""):
    full_cmd = f"ip netns exec mn.{host} {cmd}"
    subprocess.run(full_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def show_execution_summary():
    """Muestra el escenario ejecutado y las predicciones realizadas por el modelo."""
    if not os.path.exists(METRICS_PATH):
        return
    
    df = pd.read_csv(METRICS_PATH)
    if df.empty:
        return
    
    print("\n" + "="*55)
    print("      MATRIZ DE RESULTADOS: ESCENARIO VS PREDICCIÓN ML")
    print("="*55)
    summary = df.groupby(['scenario', 'predicted_label', 'action_taken']).size().reset_index(name='muestras')
    for _, row in summary.iterrows():
        print(f" Escenario Activo: {row['scenario'].upper():<10} | Predicción ML: {row['predicted_label']:<12} | Acción: {row['action_taken']:<5} | Muestras: {row['muestras']}")
    print("="*55 + "\n")

def run_scenario_normal(duration=25):
    clear_switch_flows()
    set_scenario("normal")
    print(f"\n[SCENARIO] Generando Tráfico Legítimo (iperf3) durante {duration}s...")
    run_cmd_in_netns("h1", "iperf3 -s -D")
    time.sleep(1)
    run_cmd_in_netns("h2", f"iperf3 -c 10.0.0.1 -t {duration} -b 10M -i 1")
    time.sleep(duration + 2)

def run_scenario_ddos(duration=25):
    clear_switch_flows()
    set_scenario("ddos")
    print(f"\n[SCENARIO] Lanzando Ataque DDoS SYN Flood desde h2, h3, h4 durante {duration}s...")
    p2 = subprocess.Popen("ip netns exec mn.h2 hping3 --flood -S -p 80 10.0.0.1", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    p3 = subprocess.Popen("ip netns exec mn.h3 hping3 --flood -S -p 80 10.0.0.1", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    p4 = subprocess.Popen("ip netns exec mn.h4 hping3 --flood -S -p 80 10.0.0.1", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(duration)
    p2.terminate(); p3.terminate(); p4.terminate()

def run_scenario_scanning():
    clear_switch_flows()
    set_scenario("scanning")
    print("\n[SCENARIO] Lanzando Escaneo de Puertos (nmap) desde h2...")
    run_cmd_in_netns("h2", "nmap -sS -p 1-1000 --min-rate 500 10.0.0.1")
    time.sleep(5)

def run_scenario_spoofing(duration=25):
    clear_switch_flows()
    set_scenario("spoofing")
    print(f"\n[SCENARIO] Lanzando Ataque IP Spoofing (hping3 --rand-source) desde h2 durante {duration}s...")
    p = subprocess.Popen("ip netns exec mn.h2 hping3 -i u2000 --rand-source -S -p 80 10.0.0.1", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(duration)
    p.terminate()

def execute_individual_test(scenario_func, *args):
    reset_metrics_csv()
    scenario_func(*args)
    show_execution_summary()
    print("[+] Generando figura para el escenario individual...")
    subprocess.run(["python3", "sdn/generate_figures.py"])

def run_all_scenarios():
    print("\n" + "="*60)
    print(" EJECUTANDO BATERÍA COMPLETA DE EVALUACIÓN (TFG)")
    print("="*60)
    
    reset_metrics_csv()
        
    run_scenario_normal(duration=25)
    time.sleep(3)
    run_scenario_ddos(duration=25)
    time.sleep(3)
    run_scenario_scanning()
    time.sleep(3)
    run_scenario_spoofing(duration=25)
    time.sleep(3)
    
    show_execution_summary()
    print("[+] Procesando métricas globales y generando las 5 figuras oficiales...")
    subprocess.run(["python3", "sdn/generate_figures.py"])

def interactive_menu(ryu_proc, mn_proc, log_file):
    while True:
        print("\n" + "="*55)
        print("    MENÚ INTEGRADO DE SIMULACIÓN SDN - TFG")
        print("="*55)
        print("1. Probar Tráfico Normal (iperf3)")
        print("2. Probar Ataque DDoS (SYN Flood)")
        print("3. Probar Ataque Scanning (nmap Probe)")
        print("4. Probar Ataque IP Spoofing (hping3 --rand-source)")
        print("5. EJECUTAR BATERÍA COMPLETA DE EVALUACIÓN")
        print("0. Salir y Limpiar Entorno")
        print("="*55)
        
        op = input("Selecciona una opción [0-5]: ").strip()
        
        if op == "1":
            execute_individual_test(run_scenario_normal)
        elif op == "2":
            execute_individual_test(run_scenario_ddos)
        elif op == "3":
            execute_individual_test(run_scenario_scanning)
        elif op == "4":
            execute_individual_test(run_scenario_spoofing)
        elif op == "5":
            run_all_scenarios()
        elif op == "0":
            print("[+] Saliendo del sistema...")
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
        print("\n[!] Interrupción detectada.")
        cleanup_environment()

if __name__ == '__main__':
    main()