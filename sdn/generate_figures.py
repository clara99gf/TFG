#!/usr/bin/env python3
"""
sdn/generate_figures.py
Genera gráficos de rendimiento, latencia y detección a partir del CSV de métricas.
"""

import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Configuración estética general para el TFG
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
        print(f"[!] No se encontró el archivo de métricas en: {METRICS_PATH}")
        return None
    
    df = pd.read_csv(METRICS_PATH)
    # Convertir timestamps relativos al inicio de la prueba
    if not df.empty:
        df['relative_time_sec'] = df['timestamp'] - df['timestamp'].min()
    return df

def plot_inference_latency(df):
    """Figura 1: Distribución y evolución temporal de la latencia de inferencia (ms)."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    
    # Serie temporal
    axes[0].plot(df['relative_time_sec'], df['inference_time_ms'], color='#1f77b4', alpha=0.7, linewidth=1.2)
    axes[0].axhline(df['inference_time_ms'].mean(), color='red', linestyle='--', label=f"Media: {df['inference_time_ms'].mean():.2f} ms")
    axes[0].set_title("Evolución Temporal de la Latencia")
    axes[0].set_xlabel("Tiempo Transcurrido (s)")
    axes[0].set_ylabel("Latencia de Inferencia (ms)")
    axes[0].legend()
    axes[0].grid(True, linestyle=':', alpha=0.6)
    
    # Histograma / Densidad
    sns.histplot(df['inference_time_ms'], kde=True, ax=axes[1], color='#2ca02c', bins=20)
    axes[1].set_title("Distribución de Latencias")
    axes[1].set_xlabel("Latencia de Inferencia (ms)")
    axes[1].set_ylabel("Frecuencia")
    axes[1].grid(True, linestyle=':', alpha=0.6)
    
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "latencia_inferencia.png")
    plt.savefig(path, dpi=300)
    plt.close()
    print(f"[+] Gráfico guardado: {path}")

def plot_detection_timeline(df):
    """Figura 2: Eventos de detección de tráfico Benigno vs Anómalo en el tiempo."""
    plt.figure(figsize=(10, 4.5))
    
    # Agrupar por bloques de 5 segundos
    df['time_bin'] = (df['relative_time_sec'] // 5) * 5
    grouped = df.groupby(['time_bin', 'action_taken']).size().unstack(fill_value=0)
    
    if 'ALLOW' not in grouped.columns:
        grouped['ALLOW'] = 0
    if 'DROP' not in grouped.columns:
        grouped['DROP'] = 0

    plt.bar(grouped.index, grouped['ALLOW'], width=4, label='Permitido (Normal)', color='#2ca02c', alpha=0.85)
    plt.bar(grouped.index, grouped['DROP'], width=4, bottom=grouped['ALLOW'], label='Mitigado / Bloqueado (DROP)', color='#d62728', alpha=0.85)
    
    plt.title("Acciones del Controlador SDN en el Tiempo")
    plt.xlabel("Tiempo de Simulación (s)")
    plt.ylabel("Número de Flujos Evaluados")
    plt.legend(loc='upper right')
    plt.grid(True, linestyle=':', alpha=0.6)
    
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "acciones_mitigacion.png")
    plt.savefig(path, dpi=300)
    plt.close()
    print(f"[+] Gráfico guardado: {path}")

def plot_class_distribution(df):
    """Figura 3: Proporción de clases de tráfico identificadas."""
    plt.figure(figsize=(7, 4.5))
    
    counts = df['predicted_label'].value_counts()
    colors = sns.color_palette("Set2", len(counts))
    
    bars = plt.bar(counts.index.astype(str), counts.values, color=colors, edgecolor='black', linewidth=0.8)
    
    for bar in bars:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2.0, yval + (max(counts.values)*0.01), f"{int(yval)}", ha='center', va='bottom')

    plt.title("Distribución de Clases Detectadas")
    plt.xlabel("Clase Predicha")
    plt.ylabel("Cantidad de Evaluaciones")
    plt.grid(axis='y', linestyle=':', alpha=0.6)
    
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "distribucion_clases.png")
    plt.savefig(path, dpi=300)
    plt.close()
    print(f"[+] Gráfico guardado: {path}")

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    df = load_data()
    if df is not None and not df.empty:
        plot_inference_latency(df)
        plot_detection_timeline(df)
        plot_class_distribution(df)
        print(f"\n[+] Proceso completado. Todas las figuras se guardaron en: {OUTPUT_DIR}")
    else:
        print("[!] El archivo CSV de métricas está vacío o no contiene datos válidos.")

if __name__ == '__main__':
    main()