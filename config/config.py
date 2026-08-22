import os

# Rutas principales del proyecto
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_RAW_PATH = os.path.join(BASE_DIR, "data", "raw_mininet.csv")
DATA_PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
MODELS_DIR = os.path.join(BASE_DIR, "models")
RESULTS_DIR = os.path.join(BASE_DIR, "results")

# Hiperparámetros generales
N_FEATURES = 10
TEST_SIZE = 0.20
RANDOM_STATE = 42

# Hiperparámetros de modelos
N_ESTIMATORS = 100     
MAX_ITER_LOGREG = 1000