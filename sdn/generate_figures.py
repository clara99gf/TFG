#!/usr/bin/env python3
"""
sdn/generate_figures.py
Generación de figuras filtradas por el escenario experimental activo (scenario).
"""

import os
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
OUTPUT_DIR = "results/figures"

def load_data():
    if not os.path.exists(METRICS_PATH):
        print(f"[!] Archivo de métricas no encontrado: {METRICS_PATH}")
        return None
    
    df = pd.read_csv(METRICS_PATH)
    if not df.empty:
        df['relative_time_sec'] = df['timestamp'] - df['timestamp'].min()
    return df

def plot_ddos_attack(df):
    plt.figure(figsize=(9, 4))
    ddos_df = df[df['scenario'].isin(['ddos', 'normal'])]
    if not ddos_df.empty:
        plt.plot(ddos_df['relative_time_sec'], ddos_df['pkt_rate'], color='#1f77b4', linewidth=1.5, label='Tasa de Paquetes (pkt_rate)')
        drops = ddos_df[ddos_df['action_taken'] == 'DROP']
        if not drops.empty:
            plt.scatter(drops['relative_time_sec'], drops['pkt_rate'], color='red', s=40, zorder=5, label='Regla DROP Aplicada')

    plt.title("Mitigación de Ataque Volumétrico (DDoS)")
    plt.xlabel("Tiempo Transcurrido (s)")
    plt.ylabel("Paquetes / segundo")
    plt.legend(loc='upper right')
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "ddos_mitigation.png"), dpi=300)
    plt.close()

def plot_spoofing_attack(df):
    plt.figure(figsize=(9, 4))
    spf_df = df[df['scenario'].isin(['spoofing', 'normal'])]
    if not spf_df.empty:
        plt.plot(spf_df['relative_time_sec'], spf_df['pkt_rate'], color='#2ca02c', linewidth=1.5, label='Tasa de Paquetes (pkt_rate)')
        drops = spf_df[spf_df['action_taken'] == 'DROP']
        if not drops.empty:
            plt.scatter(drops['relative_time_sec'], drops['pkt_rate'], color='red', s=40, zorder=5, label='Regla DROP Aplicada')

    plt.title("Mitigación de Ataque IP Spoofing")
    plt.xlabel("Tiempo Transcurrido (s)")
    plt.ylabel("Paquetes / segundo")
    plt.legend(loc='upper right')
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "spoofing_mitigation.png"), dpi=300)
    plt.close()

def plot_scanning_attack(df):
    plt.figure(figsize=(9, 4))
    scan_df = df[df['scenario'] == 'scanning'].copy()
    if not scan_df.empty:
        scan_df['time_bin'] = (scan_df['relative_time_sec'] // 2) * 2
        ports_per_sec = scan_df.groupby('time_bin')['dst_port'].nunique() / 2.0
        
        plt.plot(ports_per_sec.index, ports_per_sec.values, color='#ff7f0e', marker='o', linewidth=1.8, label='Puertos Únicos / s')
        
        drops = scan_df[scan_df['action_taken'] == 'DROP']
        if not drops.empty:
            drop_x = drops['relative_time_sec'].values
            drop_y = [ports_per_sec.get((t // 2) * 2, 0) for t in drop_x]
            plt.scatter(drop_x, drop_y, color='red', s=50, zorder=5, label='Regla DROP Aplicada (Instante Real)')

    plt.title("Actividades de Reconocimiento (Scanning)")
    plt.xlabel("Tiempo Transcurrido (s)")
    plt.ylabel("Puertos Únicos / segundo")
    plt.legend(loc='upper right')
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "scanning_mitigation.png"), dpi=300)
    plt.close()

def plot_infrastructure_impact(df):
    fig, ax1 = plt.subplots(figsize=(10, 4.5))
    color_cpu = '#1f77b4'
    ax1.set_xlabel('Tiempo Transcurrido (s)')
    ax1.set_ylabel('Uso de CPU de Ryu (%)', color=color_cpu)
    line1 = ax1.plot(df['relative_time_sec'], df['cpu_percent'], color=color_cpu, alpha=0.8, label='CPU Process (%)')
    ax1.tick_params(axis='y', labelcolor=color_cpu)
    ax1.grid(True, linestyle=':', alpha=0.6)

    ax2 = ax1.twinx()
    color_lat = '#d62728'
    ax2.set_ylabel('Latencia del Plano de Control (ms)', color=color_lat)
    
    # Filtrar solo latencias cuando se instalan reglas de bloqueo para evitar ceros en tráfico normal
    control_drops = df[df['control_plane_latency_ms'] > 0]
    if not control_drops.empty:
        line2 = ax2.plot(control_drops['relative_time_sec'], control_drops['control_plane_latency_ms'], color=color_lat, alpha=0.7, linestyle='--', label='Latencia Control (ms)')
    else:
        line2 = ax2.plot(df['relative_time_sec'], df['control_plane_latency_ms'], color=color_lat, alpha=0.7, linestyle='--', label='Latencia Control (ms)')
        
    ax2.tick_params(axis='y', labelcolor=color_lat)

    lines = line1 + line2
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc='upper left')

    plt.title("Impacto en la Infraestructura (CPU vs Latencia del Controlador)")
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "cpu_vs_latencia_controlador.png"), dpi=300)
    plt.close()

def print_inference_time_metrics(df):
    summary = df.groupby('scenario')['inference_time_ms'].agg(
        Media='mean', Mediana='median', Maximo='max', P95=lambda x: x.quantile(0.95)
    ).round(3)
    summary.to_csv(os.path.join(OUTPUT_DIR, "inference_time_summary.csv"))

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    df = load_data()
    if df is not None and not df.empty:
        plot_ddos_attack(df)
        plot_spoofing_attack(df)
        plot_scanning_attack(df)
        plot_infrastructure_impact(df)
        print_inference_time_metrics(df)
        print(f"[+] Artefactos gráficos exportados correctamente en: {OUTPUT_DIR}")

if __name__ == '__main__':
    main()