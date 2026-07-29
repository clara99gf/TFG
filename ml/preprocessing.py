import pandas as pd
import numpy as np
import os

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.ensemble import RandomForestClassifier


def preprocess_insdn(csv_path: str, top_n_features: int = 20):

    print(f"[+] Cargando dataset desde: {csv_path}")
    df = pd.read_csv(csv_path)

    # 1. Eliminar identificadores rígidos
    drop_cols = ['Src IP', 'Dst IP', 'Timestamp', 'Flow ID', 'Src Port', 'Dst Port']
    existing_drop_cols = [c for c in drop_cols if c in df.columns]
    df = df.drop(columns=existing_drop_cols)
    print(f"[+] Columnas eliminadas: {existing_drop_cols}")

    # 2. Limpieza
    df = df.drop_duplicates()
    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.dropna()
    print(f"[+] Dataset limpio: {df.shape[0]} filas")

    # 3. Separar X e y
    target_col = 'Label' if 'Label' in df.columns else df.columns[-1]
    X = df.drop(columns=[target_col])
    y = df[target_col]

    # 4. Codificación de variables categóricas (X)
    encoders = {}
    for col in X.select_dtypes(include=['object', 'category']).columns:
        le = LabelEncoder()
        X[col] = le.fit_transform(X[col])
        encoders[col] = le

    # 5. Codificación de etiquetas (y)
    le_y = LabelEncoder()
    y = le_y.fit_transform(y)

    # 6. Split (ANTES de escalar → evita data leakage)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    # 7. Selección de características (Random Forest)
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

    # 8. Escalado (solo con train)
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

    X_train, X_test, y_train, y_test, scaler, features, encoders, le_y = preprocess_insdn(DATA_PATH)