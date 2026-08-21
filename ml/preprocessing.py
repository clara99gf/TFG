import os
import sys
from dataclasses import dataclass
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.ensemble import RandomForestClassifier

from config.config import (
    DATA_RAW_PATH,
    DROP_COLS,
    N_FEATURES,
    TEST_SIZE,
    RANDOM_STATE,
    N_ESTIMATORS
)
from ml.utils import save_artifact, save_processed_data


@dataclass
class PreprocessResult:
    """Contenedor de salida para los datos y artefactos del preprocesamiento."""
    X_train: pd.DataFrame
    X_test: pd.DataFrame
    y_train: np.ndarray
    y_test: np.ndarray
    scaler: StandardScaler
    selected_features: list[str]
    encoders: dict[str, LabelEncoder]
    le_y: LabelEncoder


def preprocess_insdn(
    csv_path: str = DATA_RAW_PATH, 
    n_features: int = N_FEATURES
) -> PreprocessResult:
    """
    Realiza el preprocesamiento completo del dataset InSDN.

    Incluye:
    - Carga del dataset original
    - Construcción de características sintéticas para concordancia con OpenFlow
    - Limpieza de datos y descarte de columnas no reproducibles
    - Codificación de variables categóricas
    - División train/test de forma estratificada
    - Selección de características más importantes con Random Forest
    - Escalado de variables con StandardScaler

    Returns:
        PreprocessResult: Dataclass con los DataFrames escalados, etiquetas,
                          escalador y codificadores.
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"[ERROR] No se encontró el dataset original en '{csv_path}'.")

    print(f"[+] Cargando dataset desde: {csv_path}")
    df = pd.read_csv(csv_path)

    # -------------------------------------------------------------------------
    # Construcción de características compatibles con OpenFlow/Ryu
    # -------------------------------------------------------------------------
    df["packet_count"] = (
        df["Tot Fwd Pkts"] + df["Tot Bwd Pkts"]
    )

    df["byte_count"] = (
        df["TotLen Fwd Pkts"] + df["TotLen Bwd Pkts"]
    )

    print("[+] Características compatibles con Ryu construidas:")
    print("    - packet_count = Tot Fwd Pkts + Tot Bwd Pkts")
    print("    - byte_count   = TotLen Fwd Pkts + TotLen Bwd Pkts")

    # Eliminar identificadores fijos, componentes sustituidos por los contadores globales y features no reproducibles mediante OFPFlowStatsReply
    existing_drop_cols = [c for c in DROP_COLS if c in df.columns]
    df = df.drop(columns=existing_drop_cols)
    print(f"[+] Columnas eliminadas: {existing_drop_cols}")

    # Limpieza de duplicados e infinitos/nulos
    df = df.drop_duplicates()
    df = df.replace([np.inf, -np.inf], np.nan).dropna()
    print(f"[+] Dataset limpio: {df.shape[0]} filas x {df.shape[1]} columnas")

    # Separar X e y
    target_col = 'Label' if 'Label' in df.columns else df.columns[-1]
    X = df.drop(columns=[target_col])
    y = df[target_col]

    # Codificar variables categóricas
    encoders = {}
    for col in X.select_dtypes(include=['object', 'category']).columns:
        le = LabelEncoder()
        X[col] = le.fit_transform(X[col])
        encoders[col] = le

    le_y = LabelEncoder()
    y = le_y.fit_transform(y)

    print("\n[+] Clases detectadas y su codificación:")
    for idx, class_name in enumerate(le_y.classes_):
        print(f"    - [{idx}] {class_name}")

    # División train/test
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
    )

    # Ranking de importancia de características con Random Forest
    print("\n[+] Calculando importancia de las características...")
    rf_selector = RandomForestClassifier(
        n_estimators=N_ESTIMATORS,
        class_weight='balanced',
        random_state=RANDOM_STATE
    )
    rf_selector.fit(X_train, y_train)

    importances = rf_selector.feature_importances_
    indices = np.argsort(importances)[::-1]
    selected_features = list(X_train.columns[indices[:n_features]])

    X_train = X_train[selected_features]
    X_test = X_test[selected_features]

    print(f"[+] Características ordenadas por importancia:")
    for i, col in enumerate(selected_features, 1):
        score = importances[indices[i-1]]
        print(f"    {i:2d}. {col:<30} (Importancia: {score:.4f})")

    # Escalado
    scaler = StandardScaler()
    X_train_scaled = pd.DataFrame(
        scaler.fit_transform(X_train),
        columns=selected_features,
        index=X_train.index
    )
    X_test_scaled = pd.DataFrame(
        scaler.transform(X_test),
        columns=selected_features,
        index=X_test.index
    )

    # Resumen del volumen de datos procesados
    print("\n[+] Resumen del procesado de datos:")
    print(f"    - Conjunto Train: {X_train_scaled.shape[0]} muestras")
    print(f"    - Conjunto Test:  {X_test_scaled.shape[0]} muestras")
    print(f"    - Nº Características: {X_train_scaled.shape[1]}")

    return PreprocessResult(
        X_train=X_train_scaled,
        X_test=X_test_scaled,
        y_train=y_train,
        y_test=y_test,
        scaler=scaler,
        selected_features=selected_features,
        encoders=encoders,
        le_y=le_y,
    )


if __name__ == "__main__":
    try:
        data = preprocess_insdn(DATA_RAW_PATH)
    except Exception as e:
        print(f"[ERROR] Fallo en el preprocesamiento: {e}")
        sys.exit(1)

    print("\n[+] Guardando artefactos de producción en 'models/'...")
    save_artifact(data.scaler, "scaler.pkl")
    save_artifact(data.selected_features, "selected_features.pkl")
    save_artifact(data.le_y, "le_y.pkl")
    save_artifact(data.encoders, "encoders.pkl")

    print("\n[+] Guardando datos procesados en 'data/processed/'...")
    save_processed_data(data.X_train, data.X_test, data.y_train, data.y_test)

    print("\n[✔] Preprocesamiento completado y guardado en disco con éxito")