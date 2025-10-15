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
    """把 DB 撈出的欄位加上 pp/map/category/cat_level 與 timezone-aware datetime"""
    out = df.copy()
    out["datetime"] = pd.to_datetime(out["datetime"], errors="coerce")
    # 加時區僅用於顯示；資料庫內仍存 ISO 字串
    out["datetime"] = out["datetime"].dt.tz_localize(TZ, nonexistent="NaT", ambiguous="NaT")
    cfg = st.session_state.cfg["blood_pressure"]
    out["pp"]  = out.apply(lambda r: pulse_pressure(r["systolic"], r["diastolic"]), axis=1)
    out["map"] = out.apply(lambda r: mean_arterial_pressure(r["systolic"], r["diastolic"]), axis=1)
    labels, levels = [], []
    for s, d in zip(out["systolic"], out["diastolic"]):
        label, lvl = bp_category(s, d, cfg)
        labels.append(label); levels.append(lvl)
    out["category"] = labels
    out["cat_level"] = levels
    return out
