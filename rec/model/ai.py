"""Mô hình AI của Proposed: hồi quy phân vị 0,95 của sản lượng ngày theo đặc trưng vệ tinh (SPEC mục 6.2).

Trần = Q̂₀.₉₅(x) · (1 + τ_C). Đặc trưng chỉ lấy từ O4 và thông số tĩnh (configs/features.yaml).
Ablation: A1 thay bức xạ và nhiệt độ vệ tinh bằng của cảm biến tại chỗ (O3); A2 dùng hồi quy phân vị tuyến tính.
"""
from __future__ import annotations

import hashlib
import pickle

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import QuantileRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from rec import config

FEATURES = list(config.load("features")["features"])
A1_SWAP = {"poa_energy_nsrdb_whm2": "site_poa_whm2", "temp_mean_c": "site_temp_mean_c"}


def features(days: pd.DataFrame) -> pd.DataFrame:
    """Ma trận đặc trưng của Proposed; chặn mọi cột của O1–O3."""
    X = days[FEATURES].astype(float)
    config.assert_feature_columns(X.columns)
    return X


def features_a1(days: pd.DataFrame, site_poa_whm2: pd.Series | np.ndarray | None = None) -> pd.DataFrame:
    """Đặc trưng của ablation A1: bức xạ và nhiệt độ lấy từ cảm biến tại chỗ (thuộc chủ dự án)."""
    X = days[FEATURES].astype(float).rename(columns=A1_SWAP)
    X["site_poa_whm2"] = days["o3_whm2"].to_numpy(float) if site_poa_whm2 is None else np.asarray(site_poa_whm2, float)
    X["site_temp_mean_c"] = days["site_temp_mean_c"].fillna(days["temp_mean_c"]).to_numpy(float)
    return X


def train(X: pd.DataFrame, y: pd.Series, kind: str = "gbm", quantile: float = 0.95, random_state: int = 0):
    if kind == "gbm":
        model = HistGradientBoostingRegressor(loss="quantile", quantile=quantile, max_iter=300, learning_rate=0.05,
                                              min_samples_leaf=20, random_state=random_state)
    elif kind == "linear":
        model = make_pipeline(StandardScaler(), QuantileRegressor(quantile=quantile, alpha=0.0, solver="highs"))
    else:
        raise ValueError(kind)
    return model.fit(X.to_numpy(float), y.to_numpy(float))


def predict(model, X: pd.DataFrame) -> np.ndarray:
    return np.clip(model.predict(X.to_numpy(float)), 0, None)


def model_hash(model) -> str:
    return hashlib.sha256(pickle.dumps(model)).hexdigest()
