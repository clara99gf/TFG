import os
from typing import Any, Tuple
import joblib
import pandas as pd
import numpy as np

from config.config import DATA_PROCESSED_DIR, MODELS_DIR


# -------------------------------------------------------------------------
# Datos Procesados (CSV / NPY)
# -------------------------------------------------------------------------

def save_processed_data(
    X_train: pd.DataFrame, 
    X_test: pd.DataFrame, 
    y_train: np.ndarray, 
    y_test: np.ndarray
) -> None:
    """Guarda los conjuntos de datos procesados en data/processed/."""
    os.makedirs(DATA_PROCESSED_DIR, exist_ok=True)
    X_train.to_csv(os.path.join(DATA_PROCESSED_DIR, "X_train.csv"), index=False)
    X_test.to_csv(os.path.join(DATA_PROCESSED_DIR, "X_test.csv"), index=False)
    np.save(os.path.join(DATA_PROCESSED_DIR, "y_train.npy"), y_train)
    np.save(os.path.join(DATA_PROCESSED_DIR, "y_test.npy"), y_test)
    print(f"[+] Datos procesados guardados en: {DATA_PROCESSED_DIR}")


def load_processed_data() -> Tuple[pd.DataFrame, pd.DataFrame, np.ndarray, np.ndarray]:
    """Carga los conjuntos de datos de entrenamiento y prueba desde data/processed/."""
    try:
        X_train = pd.read_csv(os.path.join(DATA_PROCESSED_DIR, "X_train.csv"))
        X_test = pd.read_csv(os.path.join(DATA_PROCESSED_DIR, "X_test.csv"))
        y_train = np.load(os.path.join(DATA_PROCESSED_DIR, "y_train.npy"))
        y_test = np.load(os.path.join(DATA_PROCESSED_DIR, "y_test.npy"))
        return X_train, X_test, y_train, y_test
    except FileNotFoundError as e:
        raise FileNotFoundError(
            f"[ERROR] No se encontraron los datos procesados en '{DATA_PROCESSED_DIR}': {e}. "
            f"Asegúrate de ejecutar 'preprocessing.py' primero."
        )


# -------------------------------------------------------------------------
# Serialización de Objetos (.pkl)
# -------------------------------------------------------------------------

def save_artifact(obj: Any, filename: str) -> None:
    """Guarda cualquier objeto (modelo, scaler, encoder) en la carpeta models/."""
    os.makedirs(MODELS_DIR, exist_ok=True)
    path = os.path.join(MODELS_DIR, filename)
    joblib.dump(obj, path)
    print(f"[+] Objeto guardado en: {path}")


def load_artifact(filename: str) -> Any:
    """Carga cualquier objeto (modelo, scaler, encoder) desde la carpeta models/."""
    path = os.path.join(MODELS_DIR, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"[ERROR] El archivo '{filename}' no existe en '{MODELS_DIR}'.")
    return joblib.load(path)


# Alias semánticos para mantener compatibilidad total
save_model = save_artifact
load_model = load_artifact


def load_artifacts() -> Tuple[Any, list[str], Any, dict[str, Any]]:
    """Carga en bloque los 4 artefactos principales de preprocesamiento para inferencia."""
    artifact_files = ["scaler.pkl", "selected_features.pkl", "le_y.pkl", "encoders.pkl"]
    return tuple(load_artifact(fn) for fn in artifact_files)