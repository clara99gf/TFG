import os
import sys
import time
from typing import Dict, Any

import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier

from config.config import (
    RESULTS_DIR,
    RANDOM_STATE,
    N_ESTIMATORS,
    MAX_ITER_LOGREG
)
from ml.utils import load_processed_data, save_model


def train_all_models() -> Dict[str, Any]:
    """
    Entrena los 3 modelos, mide el tiempo de entrenamiento y guarda
    los objetos entrenados en la carpeta models/.
    """
    print("[+] Cargando datos de entrenamiento desde 'data/processed/'...")
    X_train, _, y_train, _ = load_processed_data()

    models = {
        "Logistic_Regression": LogisticRegression(
            max_iter=MAX_ITER_LOGREG,
            random_state=RANDOM_STATE
        ),
        "Decision_Tree": DecisionTreeClassifier(
            random_state=RANDOM_STATE
        ),
        "Random_Forest": RandomForestClassifier(
            n_estimators=N_ESTIMATORS,
            random_state=RANDOM_STATE,
            class_weight="balanced"
        )
    }

    train_results = []
    trained_models = {}

    print("\n[+] Entrenando modelos y midiendo tiempo de entrenamiento...")
    for name, model in models.items():
        # Medir tiempo de entrenamiento
        start_train = time.time()
        model.fit(X_train, y_train)
        train_time = time.time() - start_train

        print(f"    - {name:<20}: Train = {train_time:.4f}s")

        train_results.append({
            "Model": name,
            "Train_Time_Sec": train_time
        })

        # Guardar modelo individualmente
        model_filename = f"{name.lower()}.pkl"
        save_model(model, model_filename)
        trained_models[name] = model

    # Guardar tabla de tiempo de entrenamiento
    metrics_dir = os.path.join(RESULTS_DIR, "metrics")
    os.makedirs(metrics_dir, exist_ok=True)
    train_df = pd.DataFrame(train_results)
    train_path = os.path.join(metrics_dir, "training_cost.csv")
    train_df.to_csv(train_path, index=False)

    print(f"\n[+] Tiempos de entrenamiento guardados en: {train_path}")
    return trained_models


if __name__ == "__main__":
    try:
        train_all_models()
        print("[✔] Todos los modelos han sido entrenados y guardados con éxito")
    except Exception as e:
        print(f"[ERROR] Fallo en el entrenamiento: {e}")
        sys.exit(1)