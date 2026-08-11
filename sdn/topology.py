#!/usr/bin/env python3
"""
sdn/topology.py
Topología personalizada para Mininet con OpenFlow 1.3.
"""

from mininet.net import Mininet
from mininet.node import RemoteController, OVSKernelSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info

def create_topology():
    net = Mininet(
        controller=RemoteController,
        switch=OVSKernelSwitch,
        autoSetMacs=True,
        autoStaticArp=True
    )

    info('[+] Añadiendo Controlador Remoto (Ryu)... \n')
    c0 = net.addController('c0', controller=RemoteController, ip='127.0.0.1', port=6653)

    info('[+] Añadiendo Conmutadores OpenFlow 1.3...\n')
    s1 = net.addSwitch('s1', protocols='OpenFlow13')
    s2 = net.addSwitch('s2', protocols='OpenFlow13')
    s3 = net.addSwitch('s3', protocols='OpenFlow13')

    info('[+] Añadiendo Hosts...\n')
    h1 = net.addHost('h1', ip='10.0.0.1/24', mac='00:00:00:00:00:01')
    h2 = net.addHost('h2', ip='10.0.0.2/24', mac='00:00:00:00:00:02')
    h3 = net.addHost('h3', ip='10.0.0.3/24', mac='00:00:00:00:00:03')
    h4 = net.addHost('h4', ip='10.0.0.4/24', mac='00:00:00:00:00:04')
    h5 = net.addHost('h5', ip='10.0.0.5/24', mac='00:00:00:00:00:05')

    info('[+] Creando Enlaces...\n')
    # Enlaces Switch-Host
    net.addLink(h1, s1)
    net.addLink(h2, s1)
    net.addLink(h3, s2)
    net.addLink(h4, s2)
    net.addLink(h5, s3)

    # Enlaces Inter-Switch
    net.addLink(s1, s2)
    net.addLink(s2, s3)

    info('[+] Iniciando Red...\n')
    net.build()
    c0.start()
    s1.start([c0])
    s2.start([c0])
    s3.start([c0])

    info('[+] Topología activa. Se puede probar la conectividad con "pingall"\n')
    CLI(net)

    info('[+] Deteniendo Red...\n')
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    create_topology()