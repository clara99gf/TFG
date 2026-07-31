import pandas as pd
import numpy as np
import os

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.ensemble import RandomForestClassifier


def preprocess_insdn(csv_path: str, top_n_features: int = 20):

    print(f"[+] Cargando dataset desde: {csv_path}")
    df = pd.read_csv(csv_path)

    # Eliminar identificadores fijos para evitar sobreajuste
    drop_cols = ['Src IP', 'Dst IP', 'Timestamp', 'Flow ID', 'Src Port', 'Dst Port']
    existing_drop_cols = [c for c in drop_cols if c in df.columns]
    df = df.drop(columns=existing_drop_cols)
    print(f"[+] Columnas eliminadas: {existing_drop_cols}")

    # Limpieza de duplicados y valores infinitos/nulos    df = df.drop_duplicates()
    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.dropna()
    print(f"[+] Dataset limpio: {df.shape[0]} filas")

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

    # Division train/test (se hace antes del escalado para mantener test aislado)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    # Seleccionar las N características más importantes con Random Forest
    print("[+] Seleccionando características más importantes...")
    rf = RandomForestClassifier(
        n_estimators=100,
        class_weight='balanced',
        random_state=42
    )
    rf.fit(X_train, y_train)

    importances = rf.feature_importances_
    indices = np.argsort(importances)[::-1]

    selected_features = X_train.columns[indices[:top_n_features]]

    X_train = X_train[selected_features]
    X_test = X_test[selected_features]

    print(f"[+] Top {top_n_features} features seleccionadas")

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

    print("[+] Datos procesados correctamente:")
    print(f"    - Train: {X_train_scaled.shape}")
    print(f"    - Test:  {X_test_scaled.shape}")

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
    DATA_PATH = os.path.join("data", "InSDN_Normal_and_Attack_Combined.csv")

    # Procesar dataset
    X_train, X_test, y_train, y_test, scaler, selected_features, encoders, le_y = preprocess_insdn(DATA_PATH)

    # Crear carpetas para guardar resultados si no existen
    os.makedirs("models", exist_ok=True)
    os.makedirs(os.path.join("data", "processed"), exist_ok=True)

    # Guardar objetos de transformación necesarios para el controlador Ryu  
    print("[+] Guardando artefactos de producción en 'models/'...")
    joblib.dump(scaler, os.path.join("models", "scaler.pkl"))
    joblib.dump(selected_features, os.path.join("models", "selected_features.pkl"))
    joblib.dump(le_y, os.path.join("models", "le_y.pkl"))
    joblib.dump(encoders, os.path.join("models", "encoders.pkl"))

    # Guardar conjuntos de datos listos para el entrenamiento   
    print("[+] Guardando datos procesados en 'data/processed/'...")
    X_train.to_csv(os.path.join("data", "processed", "X_train.csv"), index=False)
    X_test.to_csv(os.path.join("data", "processed", "X_test.csv"), index=False)
    np.save(os.path.join("data", "processed", "y_train.npy"), y_train)
    np.save(os.path.join("data", "processed", "y_test.npy"), y_test)

    print("[✔] Preprocesamiento completado y guardado en disco con éxito.")