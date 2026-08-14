#!/usr/bin/env python3
"""
setup.py
Permite instalar el proyecto en modo editable (pip install -e .)
para resolver la importación de módulos locales de forma nativa.
"""

from setuptools import setup, find_packages

setup(
    name="sdn-cybersecurity-ml",
    version="1.0.0",
    description="Preprocesamiento de datos de tráfico de red para la detección de anomalías en entornos SDN.",
    author="Clara",
    packages=find_packages(),
)