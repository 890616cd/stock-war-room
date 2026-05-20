"""
module_storage.py
使用者資料持久化模組（Supabase + Fernet 加密）

職責：
  - 將每位登入使用者的自選股、模型偏好、API Key（加密）存入 Supabase
  - 登入後從 Supabase 載入資料到 session state
  - API Key 使用 Fernet 對稱加密，金鑰來自 st.secrets["ENCRYPTION_KEY"]
"""

import base64
import hashlib
import streamlit as st


# ══════════════════════════════════════════════
#  Fernet 加密工具
# ══════════════════════════════════════════════

def _get_fernet():
    """取得 Fernet 實例（金鑰從 secrets 衍生）"""
    from cryptography.fernet import Fernet
    secret = ""
    try:
        secret = str(st.secrets.get("ENCRYPTION_KEY", ""))
    except Exception:
        pass
    if not secret:
        # fallback：不加密（不建議用於生產）
        secret = "war-room-default-enc-key-change-me"
    key_bytes = hashlib.sha256(secret.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key_bytes))


def encrypt_value(plaintext: str) -> str:
    """將明文字串加密，返回 base64 密文"""
    if not plaintext:
        return ""
    try:
        return _get_fernet().encrypt(plaintext.encode()).decode()
    except Exception:
        return ""


def decrypt_value(ciphertext: str) -> str:
    """解密 base64 密文，返回明文字串"""
    if not ciphertext:
        return ""
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except Exception:
        return ""


# ══════════════════════════════════════════════
#  Supabase 連線
# ══════════════════════════════════════════════

def _supabase():
    """取得 Supabase 客戶端（每次呼叫建立，輕量操作）"""
    try:
        from supabase import create_client
        url = str(st.secrets["SUPABASE_URL"])
        key = str(st.secrets["SUPABASE_KEY"])
        return create_client(url, key)
    except KeyError:
        raise RuntimeError("請在 Streamlit Secrets 設定 SUPABASE_URL 和 SUPABASE_KEY")
    except Exception as e:
        raise RuntimeError(f"Supabase 連線失敗：{e}")


# ══════════════════════════════════════════════
#  資料載入 / 儲存
# ══════════════════════════════════════════════

_KEY_VARS = (
    "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY",
    "MARKETAUX_API_KEY", "FINNHUB_KEY", "FMP_KEY", "ALPHA_VANTAGE_KEY",
)


def load_user_data(user_id: str) -> bool:
    """
    從 Supabase 載入使用者資料，寫入 session state。
    新使用者自動建立空白記錄。
    返回 True 表示成功，False 表示失敗（仍可繼續使用，只是無法持久化）。
    """
    try:
        sb = _supabase()
        res = sb.table("user_profiles").select("*").eq("user_id", user_id).execute()

        if res.data:
            row = res.data[0]

            # ── 自選股 ──────────────────────────────
            wl = row.get("watchlist") or {}
            st.session_state["_wl_data"] = wl

            # ── 模型設定 ─────────────────────────────
            sel = row.get("selected_models")
            if sel:
                st.session_state["selected_models"] = sel

            cids = row.get("custom_model_ids")
            if cids:
                st.session_state["custom_model_ids"] = cids

            # ── 投資偏好 ─────────────────────────────
            cp = row.get("custom_prompt") or ""
            st.session_state["custom_prompt"] = cp

            # ── API Keys（解密後寫入 session_keys）───
            enc_keys = row.get("encrypted_keys") or {}
            if "session_keys" not in st.session_state:
                st.session_state["session_keys"] = {k: "" for k in _KEY_VARS}
            for env_var, enc_val in enc_keys.items():
                if enc_val:
                    plain = decrypt_value(enc_val)
                    if plain:
                        st.session_state["session_keys"][env_var] = plain

        else:
            # 新使用者：建立空白記錄
            sb.table("user_profiles").insert({"user_id": user_id}).execute()

        st.session_state["user_data_loaded"] = True
        return True

    except Exception as e:
        # 載入失敗時繼續執行，只是無法持久化
        st.session_state["user_data_loaded"] = True
        st.session_state.setdefault("_storage_error", str(e))
        return False


def save_user_data(user_id: str) -> bool:
    """
    將 session state 的資料存回 Supabase（upsert）。
    API Key 在儲存前加密。
    """
    try:
        sb = _supabase()

        # 加密 API Keys
        session_keys = st.session_state.get("session_keys", {})
        encrypted_keys = {}
        for env_var in _KEY_VARS:
            val = session_keys.get(env_var, "")
            if val:
                encrypted_keys[env_var] = encrypt_value(val)

        payload = {
            "user_id":          user_id,
            "watchlist":        st.session_state.get("_wl_data", {}),
            "selected_models":  st.session_state.get("selected_models", ["claude-sonnet-4-6"]),
            "custom_model_ids": st.session_state.get("custom_model_ids", []),
            "custom_prompt":    st.session_state.get("custom_prompt", ""),
            "encrypted_keys":   encrypted_keys,
        }

        sb.table("user_profiles").upsert(payload).execute()
        return True

    except Exception as e:
        st.warning(f"⚠️ 雲端同步失敗：{e}")
        return False
