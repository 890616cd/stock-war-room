"""
module_storage.py
使用者資料持久化模組（Supabase + Fernet 加密）

職責：
  - 將每位登入使用者的自選股、模型偏好存入 Supabase
  - 登入後從 Supabase 載入資料到 session state
  - API Key 使用 PIN 衍生的 Fernet 加密（零知識）；
    未設 PIN 時仍以 ENCRYPTION_KEY Fernet 加密（向後相容）
"""

import base64
import hashlib
import json
import os as _os
import streamlit as st


# ══════════════════════════════════════════════
#  伺服器端 Fernet（ENCRYPTION_KEY）— 向後相容用
# ══════════════════════════════════════════════

def _get_fernet():
    """取得以 ENCRYPTION_KEY 建立的 Fernet 實例"""
    from cryptography.fernet import Fernet
    secret = ""
    try:
        secret = str(st.secrets.get("ENCRYPTION_KEY", ""))
    except Exception:
        pass
    if not secret:
        raise RuntimeError(
            "ENCRYPTION_KEY 未設定。請在 Streamlit Secrets 加入一組隨機字串。"
        )
    key_bytes = hashlib.sha256(secret.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key_bytes))


def encrypt_value(plaintext: str) -> str:
    """伺服器端加密（向後相容）；ENCRYPTION_KEY 未設定時回傳空字串"""
    if not plaintext:
        return ""
    try:
        return _get_fernet().encrypt(plaintext.encode()).decode()
    except Exception:
        return ""


def decrypt_value(ciphertext: str) -> str:
    """伺服器端解密（向後相容）；解密失敗時回傳空字串"""
    if not ciphertext:
        return ""
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except Exception:
        return ""


# ══════════════════════════════════════════════
#  PIN 碼零知識加密
# ══════════════════════════════════════════════

def _pin_to_fernet(pin: str, salt: bytes):
    """PBKDF2-HMAC-SHA256 從 PIN 衍生 Fernet 金鑰（260,000 次迭代）"""
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    from cryptography.fernet import Fernet
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=260_000)
    key = base64.urlsafe_b64encode(kdf.derive(pin.encode("utf-8")))
    return Fernet(key)


def _hash_pin(pin: str) -> str:
    """SHA-256 雜湊 PIN（用於快速驗證，PIN 本身永不儲存）"""
    return hashlib.sha256(pin.encode("utf-8")).hexdigest()


def has_pin(user_id: str) -> bool:
    """檢查使用者是否已設定 PIN"""
    try:
        sb = _supabase()
        res = sb.table("user_profiles").select("pin_hash").eq("user_id", user_id).execute()
        if res.data:
            return bool(res.data[0].get("pin_hash"))
        return False
    except Exception:
        return False


def verify_pin(user_id: str, pin: str):
    """
    驗證 PIN 碼。
    返回 (True, fernet) 若正確；返回 (False, None) 若錯誤。
    """
    try:
        sb = _supabase()
        res = sb.table("user_profiles").select("pin_hash,pin_salt").eq("user_id", user_id).execute()
        if not res.data:
            return False, None
        row = res.data[0]
        stored_hash = row.get("pin_hash", "")
        salt_hex = row.get("pin_salt", "")
        if not stored_hash or not salt_hex:
            return False, None
        if _hash_pin(pin) != stored_hash:
            return False, None
        fernet = _pin_to_fernet(pin, bytes.fromhex(salt_hex))
        return True, fernet
    except Exception:
        return False, None


def set_pin_code(user_id: str, pin: str) -> bool:
    """
    設定 PIN：
      1. 產生隨機 salt
      2. 以 PIN + salt 衍生 Fernet，加密目前 session 中所有 API Key
      3. 儲存 pin_hash、pin_salt、api_keys_pin_encrypted 至 Supabase
      4. 清空舊的 encrypted_keys（伺服器端加密）
      5. 更新 session state
    """
    try:
        salt = _os.urandom(16)
        pin_hash = _hash_pin(pin)
        fernet = _pin_to_fernet(pin, salt)

        session_keys = st.session_state.get("session_keys", {})
        encrypted = {}
        for k in _KEY_VARS:
            v = session_keys.get(k, "")
            if v:
                encrypted[k] = fernet.encrypt(v.encode()).decode()

        sb = _supabase()
        sb.table("user_profiles").upsert({
            "user_id":                 user_id,
            "pin_hash":                pin_hash,
            "pin_salt":                salt.hex(),
            "api_keys_pin_encrypted":  json.dumps(encrypted),
            "encrypted_keys":          {},
        }).execute()

        st.session_state["_pin_fernet"]   = fernet
        st.session_state["_pin_unlocked"] = True
        st.session_state["_user_has_pin"] = True
        return True
    except Exception:
        import logging as _log
        _log.error("set_pin_code failed", exc_info=True)
        return False


def reset_pin_code(user_id: str, old_pin: str, new_pin: str):
    """
    用舊 PIN 驗證後重設新 PIN，並重新加密所有金鑰。
    返回 (True, "") 成功；(False, 錯誤訊息) 失敗。
    """
    valid, old_fernet = verify_pin(user_id, old_pin)
    if not valid:
        return False, "舊 PIN 碼錯誤"
    try:
        sb = _supabase()
        res = sb.table("user_profiles").select("api_keys_pin_encrypted").eq("user_id", user_id).execute()
        old_enc_json = (res.data[0].get("api_keys_pin_encrypted") or "{}") if res.data else "{}"
        old_enc = json.loads(old_enc_json) if old_enc_json else {}

        new_salt = _os.urandom(16)
        new_fernet = _pin_to_fernet(new_pin, new_salt)
        new_enc = {}
        for k, enc_v in old_enc.items():
            try:
                plain = old_fernet.decrypt(enc_v.encode()).decode()
                new_enc[k] = new_fernet.encrypt(plain.encode()).decode()
            except Exception:
                pass

        sb.table("user_profiles").upsert({
            "user_id":                user_id,
            "pin_hash":               _hash_pin(new_pin),
            "pin_salt":               new_salt.hex(),
            "api_keys_pin_encrypted": json.dumps(new_enc),
        }).execute()

        st.session_state["_pin_fernet"]   = new_fernet
        st.session_state["_pin_unlocked"] = True
        return True, ""
    except Exception as e:
        return False, f"重設失敗：{e}"


def save_api_keys_pin(user_id: str) -> bool:
    """
    以 PIN Fernet 加密目前 session 的 API Key，儲存至 api_keys_pin_encrypted。
    同時確保 encrypted_keys 欄位清空（防止伺服器端可讀舊資料殘留）。
    """
    fernet = st.session_state.get("_pin_fernet")
    if not fernet:
        return False
    try:
        session_keys = st.session_state.get("session_keys", {})
        encrypted = {}
        for k in _KEY_VARS:
            v = session_keys.get(k, "")
            if v:
                encrypted[k] = fernet.encrypt(v.encode()).decode()

        sb = _supabase()
        sb.table("user_profiles").upsert({
            "user_id":                user_id,
            "api_keys_pin_encrypted": json.dumps(encrypted),
            "encrypted_keys":         {},
        }).execute()
        return True
    except Exception:
        return False


def load_api_keys_pin(user_id: str, fernet) -> bool:
    """
    從 api_keys_pin_encrypted 讀取並以 PIN Fernet 解密，寫入 session_keys。
    """
    try:
        sb = _supabase()
        res = sb.table("user_profiles").select("api_keys_pin_encrypted").eq("user_id", user_id).execute()
        if not res.data:
            return False
        enc_json = res.data[0].get("api_keys_pin_encrypted") or "{}"
        enc = json.loads(enc_json) if enc_json else {}

        if "session_keys" not in st.session_state:
            st.session_state["session_keys"] = {k: "" for k in _KEY_VARS}
        for k, enc_v in enc.items():
            if enc_v:
                try:
                    plain = fernet.decrypt(enc_v.encode()).decode()
                    st.session_state["session_keys"][k] = plain
                except Exception:
                    pass
        return True
    except Exception:
        return False


# ══════════════════════════════════════════════
#  Supabase 連線
# ══════════════════════════════════════════════

def _supabase():
    """取得 Supabase 客戶端"""
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
    - 若已設定 PIN：不自動載入 API Key（需使用者輸入 PIN 後呼叫 load_api_keys_pin）
    - 若未設定 PIN：從 encrypted_keys 以伺服器金鑰解密載入（向後相容）
    新使用者自動建立空白記錄。
    返回 True 表示成功，False 表示失敗。
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

            # ── PIN 狀態 ─────────────────────────────
            pin_hash = row.get("pin_hash", "")
            st.session_state["_user_has_pin"] = bool(pin_hash)

            # ── API Keys ─────────────────────────────
            if not pin_hash:
                # 未設 PIN：以伺服器金鑰解密（向後相容）
                enc_keys = row.get("encrypted_keys") or {}
                if "session_keys" not in st.session_state:
                    st.session_state["session_keys"] = {k: "" for k in _KEY_VARS}
                for env_var, enc_val in enc_keys.items():
                    if enc_val:
                        plain = decrypt_value(enc_val)
                        if plain:
                            st.session_state["session_keys"][env_var] = plain
            # 已設 PIN：不自動載入，等使用者輸入 PIN 後呼叫 load_api_keys_pin

        else:
            # 新使用者：建立空白記錄
            sb.table("user_profiles").insert({"user_id": user_id}).execute()
            st.session_state["_user_has_pin"] = False

        st.session_state["user_data_loaded"] = True
        return True

    except Exception as e:
        st.session_state["user_data_loaded"] = True
        st.session_state["_user_has_pin"] = False
        st.session_state.setdefault("_storage_error", str(e))
        return False


def save_user_data(user_id: str) -> bool:
    """
    將 session state 的資料存回 Supabase（upsert）。
    - 若已設 PIN：不儲存 API Key（改由 save_api_keys_pin 處理）
    - 若未設 PIN：以伺服器金鑰加密後存入 encrypted_keys（向後相容）
    """
    try:
        sb = _supabase()

        payload = {
            "user_id":          user_id,
            "watchlist":        st.session_state.get("_wl_data", {}),
            "selected_models":  st.session_state.get("selected_models", []),
            "custom_model_ids": st.session_state.get("custom_model_ids", []),
            "custom_prompt":    st.session_state.get("custom_prompt", ""),
        }

        # 未設 PIN 時才存入伺服器加密金鑰（向後相容）
        if not st.session_state.get("_user_has_pin", False):
            session_keys = st.session_state.get("session_keys", {})
            encrypted_keys = {}
            for env_var in _KEY_VARS:
                val = session_keys.get(env_var, "")
                if val:
                    encrypted_keys[env_var] = encrypt_value(val)
            payload["encrypted_keys"] = encrypted_keys

        sb.table("user_profiles").upsert(payload).execute()
        return True

    except Exception as e:
        import logging as _log
        _log.error("save_user_data failed", exc_info=True)
        st.warning("⚠️ 雲端同步失敗，請稍後重試")
        return False
