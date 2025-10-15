# utils.py
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from dateutil import tz

TZ = tz.gettz("Asia/Taipei")

def init_state():
    if "metrics" not in st.session_state:
        st.session_state.metrics = {}
    if "cfg" not in st.session_state:
        st.session_state.cfg = {
            "blood_pressure": default_cfg_bp()
        }

def metric_exists(name: str) -> bool:
    return name in st.session_state.metrics and not st.session_state.metrics[name].empty

def export_csv(df: pd.DataFrame) -> bytes:
    buf = df.copy()
    if "datetime" in buf.columns and pd.api.types.is_datetime64_any_dtype(buf["datetime"]):
        try:
            if pd.api.types.is_datetime64tz_dtype(buf["datetime"]):
                buf["datetime"] = buf["datetime"].dt.tz_convert(TZ)
            buf["datetime"] = pd.to_datetime(buf["datetime"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass
    return buf.to_csv(index=False).encode("utf-8")

def parse_local_datetime(date_val, time_val):
    return datetime.combine(date_val, time_val).replace(tzinfo=TZ)

# ---- BP helpers ----
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
    if np.isnan(sys) or np.isnan(dia):
        return ("未知", 0)
    if sys >= cfg["crisis_sys"] or dia >= cfg["crisis_dia"]:
        return ("⚠️ 高血壓危急", 4)
    if sys < cfg["normal_sys"] and dia < cfg["normal_dia"]:
        return ("正常", 1)
    if cfg["elevated_sys_low"] <= sys <= cfg["elevated_sys_high"] and dia < cfg["normal_dia"]:
        return ("升高", 2)
    if (cfg["stage1_sys_low"] <= sys <= cfg["stage1_sys_high"]) or (cfg["stage1_dia_low"] <= dia <= cfg["stage1_dia_high"]):
        return ("第 1 期", 3)
    if sys >= cfg["stage2_sys"] or dia >= cfg["stage2_dia"]:
        return ("第 2 期", 4)
    return ("第 1 期", 3)

def normalize_bp_df(df: pd.DataFrame) -> pd.DataFrame:
    """標準血壓 schema：datetime, systolic, diastolic, pulse, meds, note, pp, map, category, cat_level"""
    df = df.copy()
    mapping = {
        "datetime":"datetime","日期時間":"datetime",
        "date":"date","日期":"date",
        "time":"time","時間":"time",
        "systolic":"systolic","收縮壓":"systolic","SYS":"systolic",
        "diastolic":"diastolic","舒張壓":"diastolic","DIA":"diastolic",
        "pulse":"pulse","心跳":"pulse","HR":"pulse","脈搏":"pulse",
        "meds":"meds","服藥":"meds",
        "note":"note","備註":"note",
    }
    df.columns = [str(c).strip() for c in df.columns]
    lower = {c.lower(): c for c in df.columns}
    out = pd.DataFrame()

    # datetime
    if "datetime" in lower:
        out["datetime"] = pd.to_datetime(df[lower["datetime"]], errors="coerce")
        try:
            if out["datetime"].dt.tz is None:
                out["datetime"] = out["datetime"].dt.tz_localize(TZ, nonexistent="NaT", ambiguous="NaT")
            else:
                out["datetime"] = out["datetime"].dt.tz_convert(TZ)
        except Exception:
            out["datetime"] = pd.to_datetime(out["datetime"], errors="coerce")
    else:
        dcol, tcol = lower.get("date"), lower.get("time")
        d = pd.to_datetime(df[dcol], errors="coerce").dt.date if dcol else pd.NaT
        t = pd.to_datetime(df[tcol], errors="coerce").dt.strftime("%H:%M:%S") if tcol else None
        out["datetime"] = [
            datetime.combine(di, pd.to_datetime(ti).time()).replace(tzinfo=TZ)
            if (not pd.isna(di) and ti is not None) else pd.NaT
            for di, ti in zip(d, t if tcol else [None]*len(df))
        ]

    # 其他欄
    for k, std in mapping.items():
        if k in ("datetime","date","time"): continue
        src = lower.get(k)
        if src:
            out[std] = df[src]

    # 補齊
    for c in ["systolic","diastolic","pulse","meds","note"]:
        if c not in out.columns:
            out[c] = np.nan if c in ["systolic","diastolic","pulse"] else ""

    # 數值化
    for c in ["systolic","diastolic","pulse"]:
        out[c] = pd.to_numeric(out[c], errors="coerce")

    # 衍生
    out["pp"]  = out.apply(lambda r: pulse_pressure(r["systolic"], r["diastolic"]), axis=1)
    out["map"] = out.apply(lambda r: mean_arterial_pressure(r["systolic"], r["diastolic"]), axis=1)

    # 分類
    cfg = st.session_state.cfg["blood_pressure"]
    labels, levels = [], []
    for s, d in zip(out["systolic"], out["diastolic"]):
        label, lvl = bp_category(s, d, cfg)
        labels.append(label); levels.append(lvl)
    out["category"] = labels
    out["cat_level"] = levels

    out = out.sort_values("datetime").reset_index(drop=True)
    return out

def page_link(path: str, label: str):
    try:
        st.page_link(path, label=label, use_container_width=True)
    except Exception:
        st.link_button(label, path, use_container_width=True)
