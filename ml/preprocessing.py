import os
import sys
from dataclasses import dataclass
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.ensemble import RandomForestClassifier

# Importar constantes desde config/config.py
from config.config import DATA_RAW_PATH, TEST_SIZE, RANDOM_STATE, N_FEATURES
from ml.utils import save_artifact, save_processed_data

@dataclass
class PreprocessResult:
    X_train: pd.DataFrame
    X_test: pd.DataFrame
    y_train: np.ndarray
    y_test: np.ndarray
    scaler: StandardScaler
    selected_features: list[str]
    encoders: dict[str, LabelEncoder]
    le_y: LabelEncoder


def preprocess_mininet(csv_path: str = DATA_RAW_PATH) -> PreprocessResult:
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"[ERROR] No se encontró '{csv_path}'. Ejecuta primero generate_traffic.py")

    print(f"[+] Cargando dataset con todas las características: {csv_path}")
    df = pd.read_csv(csv_path)

    df = df.drop_duplicates()
    df = df.replace([np.inf, -np.inf], np.nan).dropna()
    print(f"[+] Dataset limpio: {df.shape[0]} muestras")

    # 1. Separar etiquetas
    X_all = df.drop(columns=['Label'])
    y_raw = df['Label']

    # Excluir metadatos estáticos de reglas OpenFlow para evitar sesgos artificiales
    metadata_cols = ['priority', 'table_id', 'hard_timeout', 'idle_timeout', 'flags']
    traffic_cols = [col for col in X_all.columns if col not in metadata_cols]
    X_raw = X_all[traffic_cols]

    le_y = LabelEncoder()
    y_encoded = le_y.fit_transform(y_raw)

    print("\n[+] Clases multiclase detectadas en el dataset:")
    for idx, class_name in enumerate(le_y.classes_):
        print(f"    - [{idx}] {class_name}")

    # 2. SEPARAR TRAIN Y TEST PRIMERO (Evita Data Leakage)
    X_train_raw, X_test_raw, y_train, y_test = train_test_split(
        X_raw, y_encoded, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y_encoded
    )

    # 3. SELECCIÓN DE FEATURES ÚNICAMENTE SOBRE TRAIN
    print(f"\n[+] Analizando Feature Importance con Random Forest sobre X_train (Top {N_FEATURES})...")
    rf_selector = RandomForestClassifier(n_estimators=50, random_state=RANDOM_STATE)
    rf_selector.fit(X_train_raw, y_train)

    importances = pd.Series(rf_selector.feature_importances_, index=X_train_raw.columns)
    selected_features = importances.nlargest(N_FEATURES).index.tolist()

    print("[+] Features seleccionadas dinámicamente:")
    for feat in selected_features:
        print(f"    * {feat:<20} (Importancia: {importances[feat]:.4f})")

    # 4. FILTRAR COLUMNAS SELECCIONADAS
    X_train = X_train_raw[selected_features]
    X_test = X_test_raw[selected_features]

    # 5. ESCALADO (Fit solo en train, transform en train y test)
    scaler = StandardScaler()
    X_train_scaled = pd.DataFrame(scaler.fit_transform(X_train), columns=selected_features, index=X_train.index)
    X_test_scaled = pd.DataFrame(scaler.transform(X_test), columns=selected_features, index=X_test.index)

    return PreprocessResult(
        X_train=X_train_scaled,
        X_test=X_test_scaled,
        y_train=y_train,
        y_test=y_test,
        scaler=scaler,
        selected_features=selected_features,
        encoders={},
        le_y=le_y,
    )

if __name__ == "__main__":
    try:
        data = preprocess_mininet()
    except Exception as e:
        print(f"[ERROR] Fallo en el preprocesamiento: {e}")
        sys.exit(1)

    print("\n[+] Guardando artefactos en 'models/'...")
    save_artifact(data.scaler, "scaler.pkl")
    save_artifact(data.selected_features, "selected_features.pkl")
    save_artifact(data.le_y, "le_y.pkl")

    print("\n[+] Guardando datos procesados en 'data/processed/'...")
    save_processed_data(data.X_train, data.X_test, data.y_train, data.y_test)
    print("\n[✔] Preprocesamiento multiclase completado con éxito")