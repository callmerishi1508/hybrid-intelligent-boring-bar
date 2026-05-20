import time
import logging
from typing import Dict, Iterator, Optional
import pandas as pd
from pathlib import Path

log = logging.getLogger(__name__)

class TelemetryReader:
    """
    Reads one or more CSV timeseries and yields mapped telemetry rows.
    """
    def __init__(
        self,
        csv_paths: str | list[str],
        mapping: Dict[str, str],
        time_column: str = "timestamp",
        tolerance: float = 1e-4,
    ):
        paths = [csv_paths] if isinstance(csv_paths, str) else list(csv_paths)
        self.paths = [Path(p) for p in paths]
        self.mapping = mapping.copy()
        self.time_column = time_column
        self.tolerance = tolerance
        for path in self.paths:
            if not path.exists():
                raise FileNotFoundError(f"CSV not found: {path}")
        self._df = None

    def _load(self):
        dfs = []
        for path in self.paths:
            df = pd.read_csv(path)
            if self.time_column not in df.columns:
                raise KeyError(
                    f"Time column '{self.time_column}' not in CSV columns: {df.columns.tolist()}"
                )
            df[self.time_column] = pd.to_numeric(df[self.time_column], errors="coerce")
            df = df.dropna(subset=[self.time_column]).sort_values(self.time_column).reset_index(drop=True)
            dfs.append(df)

        if len(dfs) == 1:
            self._df = dfs[0]
        else:
            self._df = self._merge_sources(dfs)
            if len(self.paths) > 1:
                mask = self._df[[col for col in ["u_cnn", "u_act", "cnnOutput"] if col in self._df.columns]].notna().any(axis=1)
                if mask.any():
                    first_valid = mask.idxmax()
                    self._df = self._df.iloc[first_valid:].reset_index(drop=True)

    def _merge_sources(self, dfs: list[pd.DataFrame]) -> pd.DataFrame:
        merged = dfs[0].copy()
        for df in dfs[1:]:
            merged = pd.merge_asof(
                merged,
                df,
                on=self.time_column,
                direction="nearest",
                tolerance=self.tolerance,
                suffixes=("", "_y"),
            )
            duplicate_columns = [
                col for col in merged.columns if col.endswith("_y") and col[:-2] in merged.columns
            ]
            if duplicate_columns:
                merged = merged.drop(columns=duplicate_columns)
        return merged

    def iter_rows(self) -> Iterator[Dict]:
        if self._df is None:
            self._load()
        for _, row in self._df.iterrows():
            yield row.to_dict()

    def stream(self, simulate_real_time: bool = True, speed: float = 1.0, max_rows: Optional[int] = None):
        if self._df is None:
            self._load()

        prev_ts = None
        yielded = 0
        normalized = [
            "timestamp",
            "vibrationAmplitude",
            "spindleSpeed",
            "cnnOutput",
            "actuatorForce",
            "u_hinf",
            "u_cnn",
            "u_act",
        ]
        candidates = {
            "vibrationAmplitude": ["x_sensor", "x", "displacement", "vibrationAmplitude"],
            "spindleSpeed": ["spindleSpeed", "spindle_speed", "rpm", "spindle_rpm"],
            "cnnOutput": ["u_cnn", "u_c", "cnnOutput", "u_cnn_output"],
            "actuatorForce": ["u_act", "actuatorForce", "force"],
            "u_hinf": ["u_hinf", "u_h", "I_sim"],
            "u_cnn": ["u_cnn", "u_c"],
            "u_act": ["u_act", "actuator_force"],
            "timestamp": [self.time_column],
        }

        skip_empty = len(self.paths) > 1
        for idx in range(len(self._df)):
            ts = float(self._df.iloc[idx][self.time_column])
            mapped = {}

            for key in normalized:
                if key in self.mapping:
                    col = self.mapping[key]
                    mapped[key] = self._df.iloc[idx][col] if col in self._df.columns else None
                else:
                    val = None
                    for cand in candidates.get(key, []):
                        if cand in self._df.columns:
                            val = self._df.iloc[idx][cand]
                            break
                    mapped[key] = val

            mapped["__source_row_index"] = idx
            try:
                mapped["timestamp"] = float(mapped.get("timestamp", ts))
            except Exception:
                mapped["timestamp"] = ts

            if skip_empty and mapped.get("u_cnn") is None and mapped.get("u_act") is None and mapped.get("cnnOutput") is None:
                continue

            if simulate_real_time and prev_ts is not None:
                delta = mapped["timestamp"] - prev_ts
                if delta < 0:
                    delta = 0
                sleep_time = max(0.0, delta / max(1.0, speed))
                if sleep_time > 0:
                    try:
                        time.sleep(sleep_time)
                    except KeyboardInterrupt:
                        log.info("Interrupted during sleep; stopping stream")
                        break
            prev_ts = mapped["timestamp"]

            yield mapped
            yielded += 1
            if max_rows and yielded >= max_rows:
                break
