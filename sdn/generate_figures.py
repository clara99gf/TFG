#!/usr/bin/env python3
"""
sdn/generate_figures.py
Generación modular de figuras de evaluación SDN-ML.
"""

import os
import argparse
import pandas as pd
import matplotlib.pyplot as plt

plt.style.use('seaborn-v0_8-paper' if 'seaborn-v0_8-paper' in plt.style.available else 'default')
plt.rcParams.update({
    'font.size': 10,
    'axes.labelsize': 11,
    'axes.titlesize': 12,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'figure.titlesize': 13
})

METRICS_PATH = "results/metrics.csv"
TIMING_PATH = "results/timing.csv"
OUTPUT_DIR = "results/figures"

def load_data():
    if not os.path.exists(METRICS_PATH):
        print(f"[!] Archivo de métricas no encontrado: {METRICS_PATH}")
        return None, None
    
    df_metrics = pd.read_csv(METRICS_PATH)
    df_timing = pd.read_csv(TIMING_PATH) if os.path.exists(TIMING_PATH) else pd.DataFrame()
    return df_metrics, df_timing

def plot_ddos_attack(df, df_timing):
    plt.figure(figsize=(9, 4))
    ddos_df = df[df['scenario'] == 'ddos'].copy()
    
    if not ddos_df.empty:
        if not df_timing.empty and 'ddos' in df_timing['scenario'].values:
            t0 = df_timing[df_timing['scenario'] == 'ddos']['scenario_start_time'].values[0]
        else:
            t0 = ddos_df['timestamp'].min()
            
        ddos_df['scenario_time_sec'] = ddos_df['timestamp'] - t0
        
        plt.plot(ddos_df['scenario_time_sec'], ddos_df['pkt_rate'], color='#1f77b4', linewidth=1.5, label='Tasa de Paquetes (pkt_rate/s)')
        drops = ddos_df[ddos_df['action_taken'] == 'DROP']
        if not drops.empty:
            plt.scatter(drops['scenario_time_sec'], drops['pkt_rate'], color='red', s=40, zorder=5, label='Inyección Regla DROP')

    plt.title("Comportamiento de Red: Mitigación de DDoS (hping3)")
    plt.xlabel("Tiempo desde inicio del escenario (s)")
    plt.ylabel("Paquetes / segundo")
    plt.legend(loc='upper right')
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "ddos_mitigation.png"), dpi=300)
    plt.close()
    print(f"[+] Figura generada: {OUTPUT_DIR}/ddos_mitigation.png")

def plot_spoofing_attack(df, df_timing):
    plt.figure(figsize=(9, 4))
    spf_df = df[df['scenario'] == 'spoofing'].copy()
    
    if not spf_df.empty:
        if not df_timing.empty and 'spoofing' in df_timing['scenario'].values:
            t0 = df_timing[df_timing['scenario'] == 'spoofing']['scenario_start_time'].values[0]
        else:
            t0 = spf_df['timestamp'].min()
            
        spf_df['scenario_time_sec'] = spf_df['timestamp'] - t0
        
        plt.plot(spf_df['scenario_time_sec'], spf_df['pkt_rate'], color='#2ca02c', linewidth=1.5, label='Tasa de Paquetes (pkt_rate/s)')
        drops = spf_df[spf_df['action_taken'] == 'DROP']
        if not drops.empty:
            plt.scatter(drops['scenario_time_sec'], drops['pkt_rate'], color='red', s=40, zorder=5, label='Inyección Regla DROP')

    plt.title("Comportamiento de Red: Mitigación IP Spoofing (hping3 --rand-source)")
    plt.xlabel("Tiempo desde inicio del escenario (s)")
    plt.ylabel("Paquetes / segundo")
    plt.legend(loc='upper right')
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "spoofing_mitigation.png"), dpi=300)
    plt.close()
    print(f"[+] Figura generada: {OUTPUT_DIR}/spoofing_mitigation.png")

def plot_scanning_attack(df, df_timing):
    plt.figure(figsize=(9, 4))
    scan_df = df[df['scenario'] == 'scanning'].copy()
    
    if not scan_df.empty:
        if not df_timing.empty and 'scanning' in df_timing['scenario'].values:
            t0 = df_timing[df_timing['scenario'] == 'scanning']['scenario_start_time'].values[0]
        else:
            t0 = scan_df['timestamp'].min()
            
        scan_df['scenario_time_sec'] = scan_df['timestamp'] - t0
        scan_df['time_bin'] = (scan_df['scenario_time_sec'] // 2) * 2
        ports_per_sec = scan_df.groupby('time_bin')['dst_port'].nunique() / 2.0
        
        plt.plot(ports_per_sec.index, ports_per_sec.values, color='#ff7f0e', marker='o', linewidth=1.8, label='Puertos Únicos / s')
        
        drops = scan_df[scan_df['action_taken'] == 'DROP']
        if not drops.empty:
            drop_x = drops['scenario_time_sec'].values
            drop_y = [ports_per_sec.get((t // 2) * 2, 0) for t in drop_x]
            plt.scatter(drop_x, drop_y, color='red', s=50, zorder=5, label='Inyección Regla DROP')

    plt.title("Comportamiento de Red: Actividades de Reconocimiento / Scanning (nmap)")
    plt.xlabel("Tiempo desde inicio del escenario (s)")
    plt.ylabel("Puertos Únicos / segundo")
    plt.legend(loc='upper right')
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "scanning_mitigation.png"), dpi=300)
    plt.close()
    print(f"[+] Figura generada: {OUTPUT_DIR}/scanning_mitigation.png")

def plot_infrastructure_impact(df, df_timing):
    fig, ax1 = plt.subplots(figsize=(10, 4.5))
    color_cpu = '#1f77b4'
    
    if not df_timing.empty and 'battery_start_time' in df_timing.columns and not df_timing['battery_start_time'].dropna().empty:
        t0_global = df_timing['battery_start_time'].dropna().min()
    else:
        t0_global = df['timestamp'].min()
        
    df_global = df.copy()
    df_global['global_time_sec'] = df_global['timestamp'] - t0_global
    
    ax1.set_xlabel('Tiempo Global de Batería (s)')
    ax1.set_ylabel('Uso de CPU de Ryu (%)', color=color_cpu)
    line1 = ax1.plot(df_global['global_time_sec'], df_global['cpu_percent'], color=color_cpu, alpha=0.8, label='CPU Ryu (%)')
    ax1.tick_params(axis='y', labelcolor=color_cpu)
    ax1.grid(True, linestyle=':', alpha=0.6)

    ax2 = ax1.twinx()
    color_lat = '#d62728'
    ax2.set_ylabel('Latencia de Mitigación (ms) [OFPFlowMod]', color=color_lat)
    
    control_drops = df_global[df_global['mitigation_latency_ms'] > 0]
    if not control_drops.empty:
        line2 = ax2.plot(control_drops['global_time_sec'], control_drops['mitigation_latency_ms'], color=color_lat, alpha=0.7, linestyle='--', label='Latencia Mitigación (ms)')
    else:
        line2 = ax2.plot(df_global['global_time_sec'], df_global['mitigation_latency_ms'], color=color_lat, alpha=0.7, linestyle='--', label='Latencia Mitigación (ms)')
        
    ax2.tick_params(axis='y', labelcolor=color_lat)

    lines = line1 + line2
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc='upper left')

    plt.title("Impacto en Infraestructura (Batería Completa): CPU Ryu vs Latencia de Mitigación")
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "cpu_vs_latencia_controlador.png"), dpi=300)
    plt.close()
    print(f"[+] Figura generada: {OUTPUT_DIR}/cpu_vs_latencia_controlador.png")

def print_inference_time_metrics(df):
    summary = df.groupby('scenario')['inference_time_ms'].agg(
        Media='mean', Mediana='median', Maximo='max', P95=lambda x: x.quantile(0.95)
    ).round(3)
    summary.to_csv(os.path.join(OUTPUT_DIR, "inference_time_summary.csv"))
    print("\n[+] Resumen Estadístico de Tiempos de Inferencia ML (ms):")
    print(summary.to_string())

def main():
    parser = argparse.ArgumentParser(description="Generador modular de figuras de evaluación SDN-ML")
    parser.add_argument("--scenario", type=str, choices=["ddos", "scanning", "spoofing"], help="Genera únicamente la gráfica del escenario")
    parser.add_argument("--full", action="store_true", help="Genera la batería completa de comportamiento e impacto en infraestructura")
    
    args = parser.parse_args()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    df, df_timing = load_data()
    if df is None or df.empty:
        return

    if args.scenario == "ddos":
        plot_ddos_attack(df, df_timing)
    elif args.scenario == "scanning":
        plot_scanning_attack(df, df_timing)
    elif args.scenario == "spoofing":
        plot_spoofing_attack(df, df_timing)
    elif args.full:
        plot_ddos_attack(df, df_timing)
        plot_scanning_attack(df, df_timing)
        plot_spoofing_attack(df, df_timing)
        plot_infrastructure_impact(df, df_timing)
        print_inference_time_metrics(df)
    else:
        print("[!] Parámetro inválido. Utiliza --scenario [ddos|scanning|spoofing] o --full")

if __name__ == '__main__':
    main()