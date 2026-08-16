#!/usr/bin/env python3
"""
sdn/generate_figures.py
Generación de figuras para el TFG: Rendimiento del sistema, latencia del controlador
y comportamiento de mitigación ante tráfico anómalo.
"""

import os
import pandas as pd
import matplotlib.pyplot as plt

plt.style.use('seaborn-v0_8-paper' if 'seaborn-v0_8-paper' in plt.style.available else 'default')
plt.rcParams.update({
    'font.size': 11,
    'axes.labelsize': 12,
    'axes.titlesize': 13,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'figure.titlesize': 14
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
        df['time_bin'] = (df['relative_time_sec'] // 2) * 2  # Ventanas de 2s
    return df

def plot_cpu_and_control_latency(df):
    """Figura 1: CPU del Proceso Ryu vs Latencia de Procesamiento y Respuesta del Controlador."""
    fig, ax1 = plt.subplots(figsize=(10, 4.5))
    
    color_cpu = '#1f77b4'
    ax1.set_xlabel('Tiempo Transcurrido (s)')
    ax1.set_ylabel('Uso de CPU de Ryu (%)', color=color_cpu)
    line1 = ax1.plot(df['relative_time_sec'], df['cpu_percent'], color=color_cpu, alpha=0.8, label='CPU Process (%)')
    ax1.tick_params(axis='y', labelcolor=color_cpu)
    ax1.grid(True, linestyle=':', alpha=0.6)

    ax2 = ax1.twinx()
    color_lat = '#d62728'
    ax2.set_ylabel('Latencia de Respuesta del Controlador (ms)', color=color_lat)
    line2 = ax2.plot(df['relative_time_sec'], df['control_plane_latency_ms'], color=color_lat, alpha=0.7, linestyle='--', label='Latencia Control (ms)')
    ax2.tick_params(axis='y', labelcolor=color_lat)

    lines = line1 + line2
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc='upper left')

    plt.title("Consumo de CPU y Latencia de Respuesta de Ryu")
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "cpu_y_latencia_controlador.png")
    plt.savefig(path, dpi=300)
    plt.close()
    print(f"[+] Gráfico guardado: {path}")

def plot_ddos_attack(df):
    """Figura 2: Evolución de Paquetes/s (pkt_rate) y Puntos de Mitigación (DROP)."""
    plt.figure(figsize=(10, 4.5))
    
    plt.plot(df['relative_time_sec'], df['pkt_rate'], color='#1f77b4', linewidth=1.5, label='Tasa de Paquetes (pkt_rate)')
    
    drops = df[df['action_taken'] == 'DROP']
    if not drops.empty:
        plt.scatter(drops['relative_time_sec'], drops['pkt_rate'], color='red', zorder=5, label='Regla DROP Aplicada')

    plt.title("Ataque Volumétrico (DDoS): Paquetes/s y Aplicación de Mitigación")
    plt.xlabel("Tiempo Transcurrido (s)")
    plt.ylabel("Paquetes / segundo")
    plt.legend(loc='upper right')
    plt.grid(True, linestyle=':', alpha=0.6)
    
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "ataque_ddos_paquetes.png")
    plt.savefig(path, dpi=300)
    plt.close()
    print(f"[+] Gráfico guardado: {path}")

def plot_scanning_attack(df):
    """Figura 3: Tasa de Puertos Destino Únicos por Segundo."""
    plt.figure(figsize=(10, 4.5))
    
    # Dividimos entre 2.0 para convertir el conteo de la ventana de 2s a Tasa Promedio por Segundo
    ports_per_sec = df.groupby('time_bin')['dst_port'].nunique() / 2.0
    
    plt.plot(ports_per_sec.index, ports_per_sec.values, color='#ff7f0e', marker='o', linewidth=1.8, label='Puertos Únicos / s')
    
    plt.title("Escaneo de Red (Scanning): Tasa de Puertos Destino Explorados")
    plt.xlabel("Tiempo Transcurrido (s)")
    plt.ylabel("Puertos Únicos por Segundo")
    plt.legend(loc='upper right')
    plt.grid(True, linestyle=':', alpha=0.6)
    
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "ataque_scanning_puertos.png")
    plt.savefig(path, dpi=300)
    plt.close()
    print(f"[+] Gráfico guardado: {path}")

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    df = load_data()
    if df is not None and not df.empty:
        plot_cpu_and_control_latency(df)
        plot_ddos_attack(df)
        plot_scanning_attack(df)
        print(f"\n[+] Figuras generadas con éxito en: {OUTPUT_DIR}")
    else:
        print("[!] CSV de métricas vacío o no encontrado.")

if __name__ == '__main__':
    main()