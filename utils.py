# utils.py
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from dateutil import tz

TZ = tz.gettz("Asia/Taipei")

def init_state():
    if "cfg" not in st.session_state:
        st.session_state.cfg = {"blood_pressure": default_cfg_bp()}

def export_csv(df: pd.DataFrame) -> bytes:
    buf = df.copy()
    if "datetime" in buf.columns:
        buf["datetime"] = pd.to_datetime(buf["datetime"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
    return buf.to_csv(index=False).encode("utf-8")

def parse_local_datetime(date_val, time_val) -> datetime:
    return datetime.combine(date_val, time_val).replace(tzinfo=TZ)

def default_cfg_bp():
    return dict(
        normal_sys=120, normal_dia=80,
        elevated_sys_low=120, elevated_sys_high=129,
        stage1_sys_low=130, stage1_sys_high=139,
        stage1_dia_low=80,  stage1_dia_high=89,
        stage2_sys=140, stage2_dia=90,
        crisis_sys=180, crisis_dia=120,
        target_sys=130, target_dia=80,
    )

def pulse_pressure(sys, dia):
    if pd.isna(sys) or pd.isna(dia): return np.nan
    return float(sys) - float(dia)

def mean_arterial_pressure(sys, dia):
    if pd.isna(sys) or pd.isna(dia): return np.nan
    return (float(sys) + 2 * float(dia)) / 3.0

def bp_category(sys, dia, cfg):
    if np.isnan(sys) or np.isnan(dia): return ("未知", 0)
    if sys >= cfg["crisis_sys"] or dia >= cfg["crisis_dia"]: return ("⚠️ 高血壓危急", 4)
    if sys < cfg["normal_sys"] and dia < cfg["normal_dia"]:  return ("正常", 1)
    if cfg["elevated_sys_low"] <= sys <= cfg["elevated_sys_high"] and dia < cfg["normal_dia"]: return ("升高", 2)
    if (cfg["stage1_sys_low"] <= sys <= cfg["stage1_sys_high"]) or (cfg["stage1_dia_low"] <= dia <= cfg["stage1_dia_high"]): return ("第 1 期", 3)
    if sys >= cfg["stage2_sys"] or dia >= cfg["stage2_dia"]: return ("第 2 期", 4)
    return ("第 1 期", 3)

def enrich_bp(df: pd.DataFrame) -> pd.DataFrame:
    """
    穩健版：
    1) 無論 datetime 是 naive 或 tz-aware，都會先轉成 tz-aware UTC
    2) 計算衍生欄位：脈壓(pp)、平均動脈壓(map)、分類(category/cat_level)
    3) 不做本地時區顯示（顯示時再在頁面上 tz_convert(TZ)）
    """
    out = df.copy()

    # ---- 1) 轉成 tz-aware UTC ----
    # 先 parse 成 timestamp；如果已 tz-aware -> 直接轉 UTC；如果是 naive -> 當成 UTC 再加 tz
    out["datetime"] = pd.to_datetime(out["datetime"], errors="coerce")

    # 兩段處理：tz-aware 與 naive 分開
    mask_tzaware = out["datetime"].dt.tz.notna()
    if mask_tzaware.any():
        out.loc[mask_tzaware, "datetime"] = out.loc[mask_tzaware, "datetime"].dt.tz_convert("UTC")

    mask_naive = out["datetime"].dt.tz.isna()
    if mask_naive.any():
        # 將 naive 視為 UTC 時間再補上 tz（若你舊資料其實是本地時間，改成 tz_localize(TZ).dt.tz_convert("UTC")）
        out.loc[mask_naive, "datetime"] = (
            out.loc[mask_naive, "datetime"].dt.tz_localize(TZ).dt.tz_convert("UTC")
        )

    # ---- 2) 衍生欄位 ----
    # 脈壓（Pulse Pressure）與平均動脈壓（Mean Arterial Pressure）
    # 確保數值欄位為數字
    for col in ["systolic", "diastolic", "pulse"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    out["pp"] = out["systolic"] - out["diastolic"]
    out["map"] = out["diastolic"] + (out["pp"] / 3.0)

    # 分類（可以依你的門檻調整）
    def _cat(row):
        s, d = row["systolic"], row["diastolic"]
        if pd.isna(s) or pd.isna(d):
            return "Unknown", 99
        # 這裡示範一組常見分級（可依需求調整）
        if s < 120 and d < 80:
            return "Normal", 0
        if 120 <= s < 130 and d < 80:
            return "Elevated", 1
        if (130 <= s < 140) or (80 <= d < 90):
            return "Hypertension Stage 1", 2
        if (140 <= s) or (90 <= d):
            return "Hypertension Stage 2", 3
        return "Unknown", 99

    cats = out.apply(_cat, axis=1, result_type="expand")
    out["category"] = cats[0]
    out["cat_level"] = cats[1]

    # 確保依時間排序
    out = out.sort_values("datetime").reset_index(drop=True)
    return out
