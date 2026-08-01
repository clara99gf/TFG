import time
import os
import sys
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier

# Añadir la raíz del proyecto al path de Python
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import load_processed_data, save_model
from config.config import (
    RESULTS_DIR,
    RANDOM_STATE,
    N_ESTIMATORS,
    MAX_ITER_LOGREG
)


def train_and_compare_models():
    print("[+] Cargando datos procesados desde 'data/processed/'...")
    X_train, X_test, y_train, y_test = load_processed_data()

    # Definir los tres algoritmos a comparar
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

    results = []
    best_score = 0.0
    best_model_name = ""
    best_model_obj = None

    print("\n[+] Entrenando modelos y evaluando tiempos de cómputo...")
    for name, model in models.items():
        # Medir tiempo de entrenamiento
        start_train = time.time()
        model.fit(X_train, y_train)
        train_time = time.time() - start_train

        # Medir tiempo de inferencia sobre el conjunto de prueba
        start_inf = time.time()
        preds = model.predict(X_test)
        inf_time = time.time() - start_inf

        # Calcular exactitud básica
        accuracy = np.mean(preds == y_test)

        print(f"    - {name}: Train = {train_time:.4f}s | Inferencia = {inf_time:.4f}s | Accuracy = {accuracy:.4f}")

        results.append({
            "Model": name,
            "Train_Time_Sec": train_time,
            "Inference_Time_Sec": inf_time,
            "Accuracy": accuracy
        })

        # Guardar la referencia del modelo con mejor rendimiento
        if accuracy > best_score:
            best_score = accuracy
            best_model_name = name
            best_model_obj = model

    # Guardar métricas de tiempo en results/metrics/
    metrics_dir = os.path.join(RESULTS_DIR, "metrics")
    os.makedirs(metrics_dir, exist_ok=True)
    df_results = pd.DataFrame(results)
    df_results.to_csv(os.path.join(metrics_dir, "computational_cost.csv"), index=False)
    print("\n[+] Métricas guardadas en 'results/metrics/computational_cost.csv'")

    # Exportar el modelo ganador como el oficial para Ryu
    print(f"[★] Modelo ganador: {best_model_name} (Accuracy: {best_score:.4f})")
    save_model(best_model_obj, "modelo_final.pkl")


if __name__ == "__main__":
    train_and_compare_models()