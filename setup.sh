#!/usr/bin/env bash
# ==============================================================================
# setup.sh - Instalador automatizado del entorno (SDN + ML)
# ==============================================================================

set -e  # Detener el script si ocurre algún error

echo "============================================================"
echo " [1/5] Instalando herramientas del sistema (APT)..."
echo "============================================================"
sudo apt update
sudo apt install -y mininet openvswitch-switch iperf3 nmap hping3 python3 python3-venv python3-pip

echo ""
echo "============================================================"
echo " [2/5] Creando y activando el entorno virtual (venv)..."
echo "============================================================"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "[+] Entorno virtual creado en 'venv/'."
else
    echo "[!] El entorno virtual 'venv/' ya existe."
fi

# Activar el entorno virtual para los siguientes pasos
source venv/bin/activate

echo ""
echo "============================================================"
echo " [3/5] Instalando dependencias de Python (requirements.txt)..."
echo "============================================================"
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

echo ""
echo "============================================================"
echo " [4/5] Instalando el proyecto en modo editable (pip install -e .)..."
echo "============================================================"
# Enlaza los paquetes declarados en setup.py (config, ml, sdn)
pip install -e .

echo ""
echo "============================================================"
echo " [5/5] Comprobando y aplicando parche WSGI/Eventlet en Ryu..."
echo "============================================================"
python3 -c "
import glob
import sys

# Detección dinámica basada en la ruta del entorno virtual activo
site_packages = glob.glob(
    sys.prefix + '/lib/python*/site-packages/ryu/app/wsgi.py'
)

if site_packages:
    wsgi_path = site_packages[0]

    with open(wsgi_path, 'r') as f:
        content = f.read()

    if 'from eventlet.wsgi import ALREADY_HANDLED' in content:
        content = content.replace(
            'from eventlet.wsgi import ALREADY_HANDLED',
            'try:\n'
            '    from eventlet.wsgi import ALREADY_HANDLED\n'
            'except ImportError:\n'
            '    ALREADY_HANDLED = None'
        )

        with open(wsgi_path, 'w') as f:
            f.write(content)

        print('[+] Parche de compatibilidad aplicado con éxito en:', wsgi_path)
    else:
        print('[+] El archivo wsgi.py ya cuenta con la corrección o no la requiere.')
else:
    print('[!] No se encontró ryu/app/wsgi.py en el entorno virtual actual.')
"

echo ""
echo "============================================================"
echo " ¡INSTALACIÓN COMPLETADA CON ÉXITO!"
echo "============================================================"