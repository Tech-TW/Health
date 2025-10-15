# utils.py
from __future__ import annotations
from typing import Dict, Any, Tuple
from io import BytesIO
from datetime import datetime
import pandas as pd

# Streamlit 僅在需要時導入（避免某些離線工具調用時報錯）
try:
    import streamlit as st
except Exception:  # pragma: no cover
    st = None  # 允許在無 Streamlit 情境下匯入 utils

# ----------------------------
# 時區設定
# ----------------------------
try:
    from zoneinfo import ZoneInfo
except Exception:  # Python < 3.9 可改用 backports.zoneinfo
    from backports.zoneinfo import ZoneInfo  # type: ignore

def _get_local_tz() -> ZoneInfo:
    """
    取得顯示用本地時區：
    1) 優先讀 st.secrets["TZ"]
    2) 其次讀環境變數 TZ
    3) 最後預設 Asia/Taipei
    """
    default_name = "Asia/Taipei"
    tz_name = None
    if st and getattr(st, "secrets", None):
        tz_name = st.secrets.get("TZ", None)
    if not tz_name:
        import os
        tz_name = os.environ.get("TZ", None)
    tz_name = tz_name or default_name
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo("UTC")

TZ: ZoneInfo = _get_local_tz()
UTC: ZoneInfo = ZoneInfo("UTC")


# ----------------------------
# App 狀態初始化
# ----------------------------
def init_state() -> None:
    """
    統一初始化 session_state 所需的 key。
    - cfg: 放各模組設定（含血壓目標值）
    - lang: 語系（交給 i18n 控制，這裡只設初值）
    """
    if st is None:
        return
    ss = st.session_state
    if "cfg" not in ss:
        ss["cfg"] = {}
    # 預設語系（若 i18n 已設定會覆蓋）
    if "lang" not in ss:
        ss["lang"] = "zh-TW"
    # 初始化血壓設定（若不存在）
    bp_cfg = ss["cfg"].get("blood_pressure")
    if not bp_cfg:
        ss["cfg"]["blood_pressure"] = default_cfg_bp()


# ----------------------------
# 檔案輸出工具
# ----------------------------
def export_csv(df: pd.DataFrame, filename_prefix: str = "export") -> Tuple[bytes, str]:
    """
    將 DataFrame 匯出為 UTF-8 CSV bytes 與建議檔名。
    儲存時一律加入 UTC 時間戳，避免覆蓋與混淆。
    """
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    name = f"{filename_prefix}_{ts}.csv"
    data = df.to_csv(index=False).encode("utf-8")
    return data, name


# ----------------------------
# 模組預設設定
# ----------------------------
def default_cfg_bp() -> Dict[str, Any]:
    """
    血壓模組預設設定。
    - target_sys: 建議 130（可在 UI 自行調整）
    - target_dia: 建議 80
    """
    return {
        "target_sys": 130,
        "target_dia": 80,
    }


# ----------------------------
# 資料增豐：血壓衍生欄位
# ----------------------------
def enrich_bp(df: pd.DataFrame) -> pd.DataFrame:
    """
    穩健版 enrich：
    1) 將 datetime 欄位統一轉為 tz-aware 的 UTC（無論原本是 naive 或 tz-aware）
       - pd.to_datetime(series, utc=True) 會：
         * 將 naive 視為本地時間？→ 官方行為：直接標記為 UTC（不做位移）
         * 將 tz-aware 自動轉為 UTC
       若你的舊資料「其實是本地時間（TZ）」但寫成 naive，建議先在匯入前轉換，
       或在此函式自訂行為。為維持泛用性，此處採「一律標記/轉成 UTC」的策略。
    2) 轉型數值欄位，計算：
       - pp（脈壓）= systolic - diastolic
       - map（平均動脈壓）= diastolic + pp / 3
    3) 依常見門檻建立分類 category / cat_level（可自行調整門檻）
    4) 依 datetime 排序，回傳新 DataFrame
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=[
            "id", "datetime", "systolic", "diastolic", "pulse", "pp", "map", "category", "cat_level", "meds", "note"
        ])

    out = df.copy()

    # --- 1) 統一時間成 tz-aware 的 UTC ---
    # 對混雜（naive + tz-aware）也能一次處理
    out["datetime"] = pd.to_datetime(out["datetime"], utc=True, errors="coerce")

    # --- 2) 數值欄位轉型 ---
    for col in ("systolic", "diastolic", "pulse"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    # 衍生欄位
    out["pp"] = out["systolic"] - out["diastolic"]
    out["map"] = out["diastolic"] + (out["pp"] / 3.0)

    # --- 3) 分類 ---
    def _bp_category(s: float, d: float) -> tuple[str, int]:
        if pd.isna(s) or pd.isna(d):
            return ("Unknown", 99)
        # 常見分級（可依需求微調）
        if s < 120 and d < 80:
            return ("Normal", 0)
        if 120 <= s < 130 and d < 80:
            return ("Elevated", 1)
        if (130 <= s < 140) or (80 <= d < 90):
            return ("Hypertension Stage 1", 2)
        if (s >= 140) or (d >= 90):
            return ("Hypertension Stage 2", 3)
        return ("Unknown", 99)

    cats = out.apply(lambda r: _bp_category(r.get("systolic"), r.get("diastolic")), axis=1, result_type="expand")
    out["category"] = cats[0]
    out["cat_level"] = pd.to_numeric(cats[1], errors="coerce")

    # 若缺必要欄位，補齊空欄，避免後續 UI 報 KeyError
    for col in ("meds", "note"):
        if col not in out.columns:
            out[col] = ""

    # --- 4) 依時間排序 ---
    out = out.sort_values("datetime", kind="mergesort").reset_index(drop=True)
    return out
