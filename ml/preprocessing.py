import pandas as pd
import numpy as np
import os
import sys
import joblib


from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.ensemble import RandomForestClassifier

# Añadir la raíz del proyecto al path de Python
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importar la configuración centralizada
from config.config import (
    DATA_RAW_PATH,
    DATA_PROCESSED_DIR,
    MODELS_DIR,
    TOP_N_FEATURES,
    TEST_SIZE,
    RANDOM_STATE,
    N_ESTIMATORS
)


def preprocess_insdn(csv_path: str = DATA_RAW_PATH, top_n_features: int = TOP_N_FEATURES):

    print(f"[+] Cargando dataset desde: {csv_path}")
    df = pd.read_csv(csv_path)

    # Eliminar identificadores fijos para evitar sobreajuste
    drop_cols = ['Flow ID', 'Src IP', 'Src Port', 'Dst IP', 'Dst Port', 'Timestamp']
    existing_drop_cols = [c for c in drop_cols if c in df.columns]
    df = df.drop(columns=existing_drop_cols)
    print(f"[+] Columnas eliminadas: {existing_drop_cols}")

    # Limpieza de duplicados y valores infinitos/nulos
    df = df.drop_duplicates()
    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.dropna()
    print(f"[+] Dataset limpio: {df.shape[0]} filas x {df.shape[1]} columnas")

    # Separar características (X) y variable objetivo (y)
    target_col = 'Label' if 'Label' in df.columns else df.columns[-1]
    X = df.drop(columns=[target_col])
    y = df[target_col]

    # Codificar variables categóricas de entrada (X)
    encoders = {}
    for col in X.select_dtypes(include=['object', 'category']).columns:
        le = LabelEncoder()
        X[col] = le.fit_transform(X[col])
        encoders[col] = le

    # Codificar clases de la etiqueta objetivo (y)
    le_y = LabelEncoder()
    y = le_y.fit_transform(y)

    print("\n[+] Clases detectadas y su codificación:")
    for idx, class_name in enumerate(le_y.classes_):
        print(f"    - [{idx}] {class_name}")

    # Division train/test (se hace antes del escalado para mantener test aislado)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
    )

    # Seleccionar las N características más importantes con Random Forest
    print("\n[+] Seleccionando características más importantes...")
    rf = RandomForestClassifier(
        n_estimators=N_ESTIMATORS,
        class_weight='balanced',
        random_state=RANDOM_STATE
    )
    rf.fit(X_train, y_train)

    importances = rf.feature_importances_
    indices = np.argsort(importances)[::-1]

    selected_features = X_train.columns[indices[:top_n_features]]

    X_train = X_train[selected_features]
    X_test = X_test[selected_features]

    print(f"[★] Top {top_n_features} características seleccionadas:")
    for i, col in enumerate(selected_features, 1):
        score = importances[indices[i-1]]
        print(f"    {i:2d}. {col:<30} (Importancia: {score:.4f})")

    # Escalado con StandardScaler (fit solo sobre train)
    scaler = StandardScaler()

    X_train_scaled = pd.DataFrame(
        scaler.fit_transform(X_train),
        columns=selected_features
    )

    X_test_scaled = pd.DataFrame(
        scaler.transform(X_test),
        columns=selected_features
    )

    print("\n[+] Resumen del procesado de datos:")
    print(f"    - Conjunto Train: {X_train_scaled.shape[0]} muestras")
    print(f"    - Conjunto Test:  {X_test_scaled.shape[0]} muestras")
    print(f"    - Nº Características: {X_train_scaled.shape[1]}")

    return (
        X_train_scaled,
        X_test_scaled,
        y_train,
        y_test,
        scaler,
        selected_features,
        encoders,
        le_y
    )


if __name__ == "__main__":
    # Procesar dataset
    try:
        X_train_scaled, X_test_scaled, y_train, y_test, scaler, selected_features, encoders, le_y = preprocess_insdn(DATA_RAW_PATH)
    except Exception as e:
        print(f"[ERROR] Fallo en el preprocesamiento: {e}")
        exit(1)

    # Crear carpetas para guardar resultados si no existen
    os.makedirs(MODELS_DIR, exist_ok=True)
    os.makedirs(os.path.join(DATA_PROCESSED_DIR), exist_ok=True)

    # Guardar objetos de transformación necesarios para el controlador Ryu  
    print("\n[+] Guardando artefactos de producción en 'models/'...")
    joblib.dump(scaler, os.path.join(MODELS_DIR, "scaler.pkl"))
    joblib.dump(selected_features, os.path.join(MODELS_DIR, "selected_features.pkl"))
    joblib.dump(le_y, os.path.join(MODELS_DIR, "le_y.pkl"))
    joblib.dump(encoders, os.path.join(MODELS_DIR, "encoders.pkl"))

    # Guardar conjuntos de datos listos para el entrenamiento   
    print("[+] Guardando datos procesados en 'data/processed/'...")
    X_train_scaled.to_csv(os.path.join(DATA_PROCESSED_DIR, "X_train.csv"), index=False)
    X_test_scaled.to_csv(os.path.join(DATA_PROCESSED_DIR, "X_test.csv"), index=False)
    np.save(os.path.join(DATA_PROCESSED_DIR, "y_train.npy"), y_train)
    np.save(os.path.join(DATA_PROCESSED_DIR, "y_test.npy"), y_test)

    print("[✔] Preprocesamiento completado y guardado en disco con éxito")