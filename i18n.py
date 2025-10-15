# i18n.py
import streamlit as st
import yaml
from pathlib import Path

DEFAULT_LANG = "zh-TW"
SUPPORTED = ["zh-TW", "en"]

_cache = {}

def _load_lang(lang: str):
    lang = lang if lang in SUPPORTED else DEFAULT_LANG
    if lang in _cache:
        return _cache[lang]
    p = Path("locales") / f"{lang}.yaml"
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    _cache[lang] = data
    return data

def set_lang(lang: str):
    st.session_state["lang"] = lang if lang in SUPPORTED else DEFAULT_LANG

def get_lang() -> str:
    return st.session_state.get("lang", DEFAULT_LANG)

def t(key: str, **kwargs):
    """e.g. t('bp.page_title')；支援 format：t('common.import_success', n=3)"""
    data = _load_lang(get_lang())
    cur = data
    for part in key.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return key
    if isinstance(cur, list):
        return cur
    if isinstance(cur, str) and kwargs:
        try:
            return cur.format(**kwargs)
        except Exception:
            return cur
    return cur if isinstance(cur, str) else str(cur)
