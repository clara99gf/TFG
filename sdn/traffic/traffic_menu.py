#!/usr/bin/env python3
"""
sdn/traffic/traffic_menu.py
Generador interactivo de tráfico y ataques para Mininet.
"""

import os
import sys
import subprocess

def get_host_namespace(host_name="h2"):
    res = subprocess.run(["ip", "netns", "list"], capture_output=True, text=True)
    for line in res.stdout.splitlines():
        ns_name = line.split()[0]
        if host_name in ns_name:
            return ns_name
    return f"mn.{host_name}"

def run_cmd_in_host(host_ns, cmd):
    full_cmd = f"ip netns exec {host_ns} {cmd}"
    print(f"\n[+] Ejecutando en {host_ns}: {cmd}\n")
    try:
        subprocess.run(full_cmd, shell=True)
    except KeyboardInterrupt:
        print("\n[!] Tráfico detenido por el usuario.")

def menu():
    h2_ns = get_host_namespace("h2")
    
    while True:
        print("\n" + "="*55)
        print("    MENÚ DE SIMULACIÓN DE TRÁFICO - TFG SDN")
        print("="*55)
        print("1. Tráfico Legítimo (Ping normal h2 -> h1)")
        print("2. Ataque ICMP Flood / DDoS (h2 -> h1)")
        print("3. Ataque SYN Flood / hping3 (h2 -> h1:80)")
        print("4. Escaneo de Puertos / nmap (h2 -> h1)")
        print("5. Ataque IP Spoofing / hping3 --rand-source (h2 -> h1:80)")
        print("0. Salir")
        print("="*55)
        
        op = input("Selecciona una opción [0-5]: ").strip()
        
        if op == "1":
            run_cmd_in_host(h2_ns, "ping -c 10 10.0.0.1")
        elif op == "2":
            run_cmd_in_host(h2_ns, "ping -f 10.0.0.1")
        elif op == "3":
            run_cmd_in_host(h2_ns, "hping3 --flood -S -p 80 10.0.0.1")
        elif op == "4":
            run_cmd_in_host(h2_ns, "nmap -sS -p 1-1000 10.0.0.1")
        elif op == "5":
            run_cmd_in_host(h2_ns, "hping3 --flood --rand-source -S -p 80 10.0.0.1")
        elif op == "0":
            sys.exit(0)

if __name__ == "__main__":
    if os.geteuid() != 0:
        print("[!] Ejecuta este script con permisos de superusuario ('sudo').")
        sys.exit(1)
    menu()