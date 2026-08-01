import os
import joblib
import pandas as pd
import numpy as np

# Importar rutas desde config
from config.config import DATA_PROCESSED_DIR, MODELS_DIR


def load_processed_data():
    # Cargar conjuntos de datos limpios y procesados
    X_train = pd.read_csv(os.path.join(DATA_PROCESSED_DIR, "X_train.csv"))
    X_test = pd.read_csv(os.path.join(DATA_PROCESSED_DIR, "X_test.csv"))
    y_train = np.load(os.path.join(DATA_PROCESSED_DIR, "y_train.npy"))
    y_test = np.load(os.path.join(DATA_PROCESSED_DIR, "y_test.npy"))
    
    return X_train, X_test, y_train, y_test


def save_model(model, filename: str):
    # Guardar modelo o artefacto en la carpeta models/
    os.makedirs(MODELS_DIR, exist_ok=True)
    path = os.path.join(MODELS_DIR, filename)
    joblib.dump(model, path)
    print(f"[+] Modelo guardado en: {path}")


def load_model(filename: str):
    # Cargar modelo o artefacto desde la carpeta models/
    path = os.path.join(MODELS_DIR, filename)
    return joblib.load(path)