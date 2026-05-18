"""
cnn.py  —  Mode-2 feedforward CNN for the active boring bar
============================================================

Inputs  : sliding window of [x_sensor, u_hinf]
            x_sensor  = armature displacement x [m]  (Modes 1 & 3 only,
                        out.X from Simscape; fiber-optic sensor sits at
                        the Mode-2 nodal point so Mode 2 is absent here)
            u_hinf    = H-inf controller output current [A]  (out.I_sim)

Target  : u_cnn  [A]  — Mode-2 feedforward correction
            Computed in MATLAB before exporting:
                m2   = 0.147;          % modal mass Mode 2  [kg]
                KI2  = 4.41;           % actuator gain Mode 2  [N/A]
                u_cnn = -(m2 / KI2) * gradient(gradient(q2, Ts), Ts);
            where q2 is the Simscape internal modal coordinate of Mode 2.

Signal flow in the hybrid controller
--------------------------------------
    x_sensor  ──►  H-inf  ──►  u_hinf  ──┐
                                          ├─► (+) ──► clamp ±4 A ──► actuator
    [x_sensor, u_hinf] ──► CNN ──► u_cnn ─┘

MATLAB export snippet (paste at end of your Simscape sim script)
----------------------------------------------------------------
    Ts    = 1e-4;                          % 10 kHz
    t     = out.tout;
    x_s   = out.X.Data;                    % sensor displacement  [m]
    u_h   = out.I_sim.Data;                % H-inf current        [A]

    % q2 is the position output of the MODE 2 Simscape subsystem
    q2    = out.q2_pos.Data;
    m2    = 0.147;  KI2 = 4.41;
    q2dd  = gradient(gradient(q2, Ts), Ts);
    u_c   = -(m2 / KI2) * q2dd;           % Mode-2 cancellation  [A]

    T = table(t, x_s, u_h, u_c, ...
              'VariableNames', {'timestamp','x_sensor','u_hinf','u_cnn'});
    writetable(T, 'simscape_export.csv');

Usage
-----
    Train  : python cnn.py --data simscape_export.csv
    Predict: python cnn.py --predict --data simscape_export.csv
    Smoke  : python cnn.py --smoke
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Iterable, TYPE_CHECKING, Tuple, Optional, List, Any

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler

# Provide type hints to static checkers without importing heavy TF at type-check time
if TYPE_CHECKING:
    from tensorflow import keras  # type: ignore
    from tensorflow.keras import layers  # type: ignore

USE_TF = True
try:
    import tensorflow as tf
    keras = tf.keras
    layers = tf.keras.layers
except Exception:  # pragma: no cover - fallback for environments without TF
    USE_TF = False
    keras = None
    layers = None
    from sklearn.neural_network import MLPRegressor

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION  (all tunable constants in one place)
# ═══════════════════════════════════════════════════════════════════════════════

# Signals — must match the column names in the exported CSV
FEATURE_COLUMNS: List[str] = ["x_sensor", "u_hinf"]
TARGET_COLUMN:   str        = "u_cnn"

# Physical bound on the CNN output.
# Mode 2: m2=0.147 kg, KI2=4.41 N/A, max modal stiffness → |u_cnn| ≤ ~1.5 A
CNN_CLAMP_A: float = 1.5

# Artifact paths
MODEL_DIR   = Path(__file__).resolve().parent / "model_artifacts"
MODEL_FILE  = "cnn_mode2.keras"
SKLEARN_MODEL_FILE = "cnn_mode2.joblib"
SCALER_FILE = "scaler.joblib"
META_FILE   = "metadata.json"

# Training hyper-parameters
# Window = 32 steps × 100 µs = 3.2 ms ≈ 2 full Mode-2 cycles (T2 = 1.63 ms)
WINDOW_SIZE      = 32
EPOCHS           = 50
BATCH_SIZE       = 64
VALIDATION_SPLIT = 0.20
RANDOM_SEED      = 42

# Modal parameters (Table I, Chen et al. 2015) — used only for synthetic smoke data
_MODAL = {
    "fn":  [174,    614,    1130  ],
    "z":   [0.0120, 0.0063, 0.0018],
    "m2":  0.147,
    "KI2": 4.41,
    "Ts":  1e-4,
}


# ═══════════════════════════════════════════════════════════════════════════════
# EXCEPTIONS
# ═══════════════════════════════════════════════════════════════════════════════

class CnnInputError(ValueError):
    """Raised when sensor data does not satisfy the input contract."""


# ═══════════════════════════════════════════════════════════════════════════════
# DATA HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def load_csv(path: str | Path, need_target: bool = True) -> pd.DataFrame:
    """
    Load and validate a Simscape-exported CSV.

    Required columns  : x_sensor, u_hinf  (always)
                        u_cnn             (only when need_target=True)
    Optional columns  : timestamp
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"CSV not found: {p}")

    df = pd.read_csv(p)

    needed = list(FEATURE_COLUMNS) + ([TARGET_COLUMN] if need_target else [])
    missing = [c for c in needed if c not in df.columns]
    if missing:
        raise CnnInputError(
            f"Missing column(s): {missing}\n"
            "Export x_sensor (out.X), u_hinf (out.I_sim), and u_cnn "
            "from your Simscape closed-loop simulation."
        )

    bad = [c for c in needed if not pd.api.types.is_numeric_dtype(df[c])]
    if bad:
        raise CnnInputError(f"Non-numeric column(s): {bad}")

    if df[needed].isna().any().any():
        raise CnnInputError("NaN values found in required columns.")

    if "timestamp" in df.columns:
        df = df.sort_values("timestamp").reset_index(drop=True)

    return df


def make_windows(
    df: pd.DataFrame,
    window_size: int = WINDOW_SIZE,
    need_target: bool = True,
) -> Tuple[np.ndarray, Optional[np.ndarray]]:
    """
    Slice time-series into overlapping windows.

    X shape : (n_windows, window_size, 2)   — [x_sensor, u_hinf]
    y shape : (n_windows,)                  — u_cnn at last step of each window
    """
    if window_size < 4:
        raise CnnInputError("window_size must be >= 4.")
    if len(df) < window_size:
        raise CnnInputError(
            f"Need >= {window_size} rows; got {len(df)}. "
            "Run a longer Simscape simulation."
        )

    F = df[FEATURE_COLUMNS].to_numpy(dtype=np.float32)
    Y = df[TARGET_COLUMN].to_numpy(dtype=np.float32) if need_target else None

    X_wins, y_vals = [], []
    for s in range(len(df) - window_size + 1):
        X_wins.append(F[s : s + window_size])
        if Y is not None:
            y_vals.append(Y[s + window_size - 1])

    X = np.array(X_wins, dtype=np.float32)
    y = np.array(y_vals, dtype=np.float32) if Y is not None else None
    return X, y


def _fit_scaler(X_train: np.ndarray) -> StandardScaler:
    sc = StandardScaler()
    sc.fit(X_train.reshape(-1, X_train.shape[-1]))
    return sc


def _scale(X: np.ndarray, sc: StandardScaler) -> np.ndarray:
    s = X.shape
    return sc.transform(X.reshape(-1, s[-1])).reshape(s).astype(np.float32)


# ═══════════════════════════════════════════════════════════════════════════════
# MODEL ARCHITECTURE
# ═══════════════════════════════════════════════════════════════════════════════

def build_model(window_size: int = WINDOW_SIZE):
    """
    3-block 1D CNN with no MaxPooling in blocks 1 & 2.

    At 10 kHz, window = 32 steps = 3.2 ms ~ 2 full Mode-2 cycles (T2 = 1.63 ms).
    Halving the time axis with MaxPooling would destroy the 614 Hz phase
    information the network needs to reconstruct q2(t).

      Block 1  Conv1D(32, k=5)  wide kernel — catches low-freq ring-down envelope
      Block 2  Conv1D(64, k=3)  refines 614 Hz oscillation pattern
      Block 3  Conv1D(64, k=3) + GlobalAvgPool — collapses temporal dimension
      Head     Dense(64) -> Dense(1)
    """
    # If TF is not available, we'll return an sklearn MLPRegressor later in train().
    if not USE_TF:
        return None

    inp = keras.Input(shape=(window_size, len(FEATURE_COLUMNS)), name="sensor_window")

    # Block 1
    x = layers.Conv1D(32, kernel_size=5, padding="same", use_bias=False)(inp)
    x = layers.BatchNormalization()(x)
    x = layers.Activation("relu")(x)

    # Block 2
    x = layers.Conv1D(64, kernel_size=3, padding="same", use_bias=False)(x)
    x = layers.BatchNormalization()(x)
    x = layers.Activation("relu")(x)

    # Block 3 + temporal collapse
    x = layers.Conv1D(64, kernel_size=3, padding="same", use_bias=False)(x)
    x = layers.BatchNormalization()(x)
    x = layers.Activation("relu")(x)
    x = layers.GlobalAveragePooling1D()(x)

    # Regression head
    x = layers.Dense(64, activation="relu")(x)
    x = layers.Dropout(0.2)(x)
    out = layers.Dense(1, name="u_cnn")(x)

    model = keras.Model(inp, out, name="mode2_ff_cnn")
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=1e-3),
        loss="mse",
        metrics=["mae"],
    )
    return model


# ═══════════════════════════════════════════════════════════════════════════════
# TRAINING
# ═══════════════════════════════════════════════════════════════════════════════

def train(
    csv_path: str | Path,
    window_size: int = WINDOW_SIZE,
    epochs: int = EPOCHS,
    batch_size: int = BATCH_SIZE,
    val_split: float = VALIDATION_SPLIT,
) -> dict:
    """
    Full training pipeline. Returns a metrics dict.

    Chronological split is enforced (no shuffle) because this is time-series.
    """
    # Seed RNGs
    if USE_TF:
        keras.utils.set_random_seed(RANDOM_SEED)

    df = load_csv(csv_path, need_target=True)
    X, y = make_windows(df, window_size=window_size, need_target=True)

    n_train = int(len(X) * (1 - val_split))
    if n_train <= 0 or n_train >= len(X):
        raise CnnInputError("Too few windows for train/val split. Use a longer simulation.")

    X_tr, X_va = X[:n_train], X[n_train:]
    y_tr, y_va = y[:n_train], y[n_train:]

    sc = _fit_scaler(X_tr)
    X_tr_s = _scale(X_tr, sc)
    X_va_s = _scale(X_va, sc)

    if USE_TF:
        model = build_model(window_size)
        model.summary()

        history = model.fit(
            X_tr_s, y_tr,
            validation_data=(X_va_s, y_va),
            epochs=epochs,
            batch_size=batch_size,
            callbacks=[
                keras.callbacks.EarlyStopping(
                    monitor="val_loss", patience=8, restore_best_weights=True
                ),
                keras.callbacks.ReduceLROnPlateau(
                    monitor="val_loss", factor=0.5, patience=4, min_lr=1e-5
                ),
            ],
            verbose=1,
        )

        preds = model.predict(X_va_s, verbose=0).ravel()
        metrics = {
            "mae_A":            float(mean_absolute_error(y_va, preds)),
            "rmse_A":           float(np.sqrt(mean_squared_error(y_va, preds))),
            "r2":               float(r2_score(y_va, preds)) if len(y_va) > 1 else None,
            "train_windows":    int(n_train),
            "val_windows":      int(len(X_va)),
            "final_train_loss": float(history.history["loss"][-1]),
            "final_val_loss":   float(history.history["val_loss"][-1]),
            "cnn_clamp_A":      CNN_CLAMP_A,
        }

        _save_artifacts(model, sc, window_size, metrics)
    else:
        # Fallback: use a small sklearn MLPRegressor on flattened windows
        X_tr_flat = X_tr_s.reshape(len(X_tr_s), -1)
        X_va_flat = X_va_s.reshape(len(X_va_s), -1)
        mlp = MLPRegressor(hidden_layer_sizes=(64,), activation='relu', max_iter=200, random_state=RANDOM_SEED)
        mlp.fit(X_tr_flat, y_tr)
        preds = mlp.predict(X_va_flat)
        metrics = {
            "mae_A":            float(mean_absolute_error(y_va, preds)),
            "rmse_A":           float(np.sqrt(mean_squared_error(y_va, preds))),
            "r2":               float(r2_score(y_va, preds)) if len(y_va) > 1 else None,
            "train_windows":    int(n_train),
            "val_windows":      int(len(X_va)),
            "final_train_loss": None,
            "final_val_loss":   None,
            "cnn_clamp_A":      CNN_CLAMP_A,
        }

        _save_artifacts(mlp, sc, window_size, metrics, sklearn_backend=True)
    print(json.dumps(metrics, indent=2))
    return metrics


# ═══════════════════════════════════════════════════════════════════════════════
# ARTIFACT SAVE / LOAD
# ═══════════════════════════════════════════════════════════════════════════════

def _save_artifacts(
    model, sc: StandardScaler, window_size: int, metrics: dict, sklearn_backend: bool = False
) -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    if sklearn_backend or not USE_TF:
        # save sklearn model via joblib
        joblib.dump(model, MODEL_DIR / SKLEARN_MODEL_FILE)
        backend = "sklearn"
    else:
        model.save(MODEL_DIR / MODEL_FILE)
        backend = "tensorflow"

    joblib.dump(sc, MODEL_DIR / SCALER_FILE)
    meta = {
        "feature_columns": FEATURE_COLUMNS,
        "target_column":   TARGET_COLUMN,
        "window_size":     window_size,
        "cnn_clamp_A":     CNN_CLAMP_A,
        "metrics":         metrics,
        "backend":         backend,
        "inputs": {
            "x_sensor": "out.X — fiber-optic armature displacement [m] (Modes 1 & 3 only)",
            "u_hinf":   "out.I_sim — H-inf current command [A]",
        },
        "target": "u_cnn = -(m2/KI2)*q2_ddot [A]  Mode-2 cancellation current",
        "role":   "Additive feedforward. u_act = clamp(u_hinf + u_cnn, -4, +4) A",
    }
    (MODEL_DIR / META_FILE).write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"Artifacts saved -> {MODEL_DIR}")


def load_artifacts():
    """Load model, scaler, and metadata from MODEL_DIR."""
    if not (MODEL_DIR / META_FILE).exists() or not (MODEL_DIR / SCALER_FILE).exists():
        raise FileNotFoundError(
            f"Missing artifacts. Train first:  python cnn.py --data simscape_export.csv"
        )
    meta = json.loads((MODEL_DIR / META_FILE).read_text(encoding="utf-8"))
    sc   = joblib.load(MODEL_DIR / SCALER_FILE)

    backend = meta.get("backend", "tensorflow")
    if backend == "sklearn":
        if not (MODEL_DIR / SKLEARN_MODEL_FILE).exists():
            raise FileNotFoundError(f"Missing {SKLEARN_MODEL_FILE}. Train first.")
        model = joblib.load(MODEL_DIR / SKLEARN_MODEL_FILE)
    else:
        if not USE_TF:
            raise RuntimeError("Artifacts were saved for TensorFlow backend but TF is not available.")
        model = keras.models.load_model(MODEL_DIR / MODEL_FILE)

    return model, sc, meta


# ═══════════════════════════════════════════════════════════════════════════════
# INFERENCE
# ═══════════════════════════════════════════════════════════════════════════════

def predict_correction(
    rows: Iterable[dict],
    model: Any,
    sc: StandardScaler,
    meta: dict,
) -> float:
    """
    Predict u_cnn [A] from the most recent window of sensor rows.

    Parameters
    ----------
    rows : iterable of dicts, each with keys x_sensor and u_hinf.
           Must supply at least meta['window_size'] rows.

    Returns
    -------
    u_cnn : float [A], clamped to +/- CNN_CLAMP_A (1.5 A).

    Integration example
    -------------------
        u_hinf = hinf_controller(x_sensor)      # your H-inf block
        u_cnn  = predict_correction(buffer, model, sc, meta)
        u_act  = float(np.clip(u_hinf + u_cnn, -4.0, 4.0))
        send_to_amplifier(u_act)
    """
    df = pd.DataFrame(list(rows))
    ws = int(meta["window_size"])
    X, _ = make_windows(df, window_size=ws, need_target=False)

    latest = _scale(X[-1:], sc)
    backend = meta.get("backend", "tensorflow")
    if backend == "sklearn":
        # sklearn models expect 2D input: (n_samples, features)
        latest_flat = latest.reshape(1, -1)
        raw = float(model.predict(latest_flat).ravel()[0])
    else:
        raw = float(model.predict(latest, verbose=0).ravel()[0])
    clamp  = float(meta.get("cnn_clamp_A", CNN_CLAMP_A))
    return float(np.clip(raw, -clamp, clamp))


# ═══════════════════════════════════════════════════════════════════════════════
# SYNTHETIC DATA GENERATOR  (smoke test only — no real Simscape needed)
# ═══════════════════════════════════════════════════════════════════════════════

def _make_synthetic(path: str, n: int = 600) -> None:
    """
    Physics-based synthetic dataset using exact Table I parameters.

    x_sensor  = Mode-1 + Mode-3 ring-down  (no Mode 2 — mimics fiber-optic blind spot)
    u_hinf    = simple proportional + derivative proxy of H-inf
    u_cnn     = Mode-2 cancellation  -(m2/KI2)*q2_ddot
    """
    p  = _MODAL
    Ts = p["Ts"]
    t  = np.arange(n) * Ts
    wn = [2 * np.pi * f for f in p["fn"]]

    # x_sensor: Modes 1 & 3 only (Mode 2 absent — fiber-optic nodal point)
    x_s = (
        4.5e-7 * np.exp(-p["z"][0] * wn[0] * t) * np.sin(wn[0] * t)
        + 1.0e-7 * np.exp(-p["z"][2] * wn[2] * t) * np.sin(wn[2] * t)
    )

    # u_hinf: proportional + derivative mock (sign from kxI convention Table I)
    u_h = np.clip(-2e6 * x_s - 30 * np.gradient(x_s, Ts), -4.0, 4.0)

    # Mode-2 free oscillation (independent of x_sensor)
    q2   = 3e-8 * np.exp(-p["z"][1] * wn[1] * t) * np.sin(wn[1] * t)
    q2dd = np.gradient(np.gradient(q2, Ts), Ts)
    u_c  = np.clip(-(p["m2"] / p["KI2"]) * q2dd, -CNN_CLAMP_A, CNN_CLAMP_A)

    pd.DataFrame({
        "timestamp": t,
        "x_sensor":  x_s,
        "u_hinf":    u_h,
        "u_cnn":     u_c,
    }).to_csv(path, index=False)
    print(f"Synthetic data -> {path}  ({n} rows, Ts={Ts*1e3:.2f} ms)")


# ═══════════════════════════════════════════════════════════════════════════════
# SMOKE TEST
# ═══════════════════════════════════════════════════════════════════════════════

def smoke_test(window_size: int = WINDOW_SIZE, epochs: int = 2) -> None:
    """Train on synthetic data and run one prediction — verifies pipeline end-to-end."""
    csv = "_smoke_data.csv"
    _make_synthetic(csv, n=600)
    try:
        metrics = train(csv, window_size=window_size, epochs=epochs,
                        batch_size=8, val_split=0.2)
        model, sc, meta = load_artifacts()
        df    = pd.read_csv(csv).tail(window_size)
        rows  = df[FEATURE_COLUMNS].to_dict("records")
        u_cnn = predict_correction(rows, model, sc, meta)
        print(f"\n  Smoke test PASSED")
        print(f"  sample u_cnn = {u_cnn:+.6f} A")
        print(f"  val MAE      = {metrics['mae_A']:.6f} A")
    finally:
        if os.path.exists(csv):
            os.remove(csv)


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Mode-2 feedforward CNN for active boring bar.\n"
                    "Train, predict, or smoke-test from one file.",
    )
    p.add_argument("--data",        default="simscape_export.csv",
                   help="Simscape CSV (columns: x_sensor, u_hinf, u_cnn)")
    p.add_argument("--window-size", type=int,   default=WINDOW_SIZE)
    p.add_argument("--epochs",      type=int,   default=EPOCHS)
    p.add_argument("--batch-size",  type=int,   default=BATCH_SIZE)
    p.add_argument("--val-split",   type=float, default=VALIDATION_SPLIT)
    p.add_argument("--predict",     action="store_true",
                   help="Load saved model and predict on tail of --data")
    p.add_argument("--smoke",       action="store_true",
                   help="End-to-end test on synthetic data (no CSV needed)")
    return p


def main() -> None:
    args = _parser().parse_args()

    if args.smoke:
        smoke_test(window_size=args.window_size, epochs=args.epochs)
        return

    if args.predict:
        model, sc, meta = load_artifacts()
        df    = load_csv(args.data, need_target=False).tail(meta["window_size"])
        rows  = df[FEATURE_COLUMNS].to_dict("records")
        u_cnn = predict_correction(rows, model, sc, meta)
        print(f"u_cnn = {u_cnn:+.6f} A")
        return

    # Default: train
    train(
        csv_path    = args.data,
        window_size = args.window_size,
        epochs      = args.epochs,
        batch_size  = args.batch_size,
        val_split   = args.val_split,
    )


if __name__ == "__main__":
    main()
