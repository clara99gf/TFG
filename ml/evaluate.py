import os
import sys
import time

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
    confusion_matrix
)

from config.config import RESULTS_DIR
from ml.utils import load_processed_data, load_model, save_model, load_artifact


def evaluate_models() -> None:
    """
    Evalúa los modelos guardados sobre el conjunto de test, calcula métricas
    de rendimiento e inferencia, genera matrices de confusión y selecciona 
    el modelo ganador guardándolo como modelo_final.pkl.
    """
    print("[+] Cargando datos de test y artefactos...")
    _, X_test, _, y_test = load_processed_data()
    le_y = load_artifact("le_y.pkl")
    class_names = [str(c) for c in le_y.classes_]

    model_names = ["Logistic_Regression", "Decision_Tree", "Random_Forest"]
    
    # Directorios de salida
    metrics_dir = os.path.join(RESULTS_DIR, "metrics")
    figures_dir = os.path.join(RESULTS_DIR, "figures")
    os.makedirs(metrics_dir, exist_ok=True)
    os.makedirs(figures_dir, exist_ok=True)

    metrics_list = []
    inference_list = []
    best_f1 = 0.0
    best_model_name = ""
    best_model_obj = None

    print("\n[+] Evaluando rendimiento e inferencia de los 3 modelos...")

    for name in model_names:
        filename = f"{name.lower()}.pkl"
        model = load_model(filename)

        # Medir tiempo de inferencia 
        start_inf = time.time()
        preds = model.predict(X_test)
        inf_time = time.time() - start_inf

        inference_list.append({
            "Model": name,
            "Inference_Time_Sec": inf_time,
        })

        # Cálculo de métricas
        acc = accuracy_score(y_test, preds)
        # zero_division=0 evita el warning cuando una clase no recibe ninguna predicción
        prec, rec, f1, _ = precision_recall_fscore_support(
            y_test, preds, average="weighted", zero_division=0
        )

        metrics_list.append({
            "Model": name,
            "Accuracy": acc,
            "Precision": prec,
            "Recall": rec,
            "F1-Score": f1
        })

        # Selección del mejor modelo según F1-Score
        if f1 > best_f1:
            best_f1 = f1
            best_model_name = name
            best_model_obj = model

        # -------------------------------------------------------------
        # MATRIZ DE CONFUSIÓN (1 por modelo)
        # -------------------------------------------------------------
        cm = confusion_matrix(y_test, preds)
        plt.figure(figsize=(8, 6))
        sns.heatmap(
            cm, 
            annot=True, 
            fmt="d", 
            cmap="Blues",
            xticklabels=class_names, 
            yticklabels=class_names
        )
        plt.title(f"Matriz de Confusión - {name}")
        plt.ylabel("Clase Real")
        plt.xlabel("Clase Predicha")
        plt.tight_layout()
        
        cm_path = os.path.join(figures_dir, f"confusion_matrix_{name.lower()}.png")
        plt.savefig(cm_path, dpi=300)
        plt.close()

    # Guardar y mostrar métricas de rendimiento
    metrics_path = os.path.join(metrics_dir, "model_performance_metrics.csv")
    df_metrics = pd.DataFrame(metrics_list)
    df_metrics.to_csv(metrics_path, index=False)
    
    print(f"\n[+] Resumen de métricas de rendimiento (guardado en: {metrics_path}):")
    print(df_metrics.to_string(index=False))

    # -------------------------------------------------------------
    # CONSOLIDACIÓN DE COSTES COMPUTACIONALES (Entrenamiento + Inferencia)
    # -------------------------------------------------------------
    df_inf = pd.DataFrame(inference_list)
    train_path = os.path.join(metrics_dir, "training_cost.csv")

    if os.path.exists(train_path):
        df_train = pd.read_csv(train_path)
        df_cost = pd.merge(df_train, df_inf, on="Model")
    else:
        df_cost = df_inf

    cost_path = os.path.join(metrics_dir, "computational_cost.csv")
    df_cost.to_csv(cost_path, index=False)
    
    print(f"\n[+] Resumen de costes computacionales (guardado en: {cost_path}):")
    print(df_cost.to_string(index=False))

    # -------------------------------------------------------------
    # GRÁFICA DE BARRAS COMPARATIVA DE MÉTRICAS
    # -------------------------------------------------------------
    df_melted = df_metrics.melt(id_vars="Model", var_name="Metric", value_name="Score")
    
    plt.figure(figsize=(10, 6))
    sns.barplot(data=df_melted, x="Metric", y="Score", hue="Model", palette="viridis")
    plt.title("Comparativa de Rendimiento entre Modelos ML")
    plt.ylim(0.85, 1.0)
    plt.ylabel("Puntuación (0 - 1)")
    plt.grid(axis="y", linestyle="--", alpha=0.7)
    plt.tight_layout()

    bar_plot_path = os.path.join(figures_dir, "metrics_comparison_bar_chart.png")
    plt.savefig(bar_plot_path, dpi=300)
    plt.close()

    # Único mensaje informativo para todas las figuras
    print(f"\n[+] Matrices de confusión y gráfica generadas y guardadas en: {figures_dir}")

    # -------------------------------------------------------------
    # EXPORTACIÓN DEL MODELO GANADOR
    # -------------------------------------------------------------
    print(f"\n[★] Modelo ganador por F1-Score: {best_model_name} (F1: {best_f1:.4f})")
    save_model(best_model_obj, "modelo_final.pkl")

if __name__ == "__main__":
    try:
        evaluate_models()
        print("\n[✔] Evaluación completada con éxito")
    except Exception as e:
        print(f"[ERROR] Fallo en la evaluación: {e}")
        sys.exit(1)