import urllib.request
import json
import urllib.error
import logging

SUPABASE_URL = "https://ajqcibpkafteyckevkbu.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFqcWNpYnBrYWZ0ZXlja2V2a2J1Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4MTcwOTUyOCwiZXhwIjoyMDk3Mjg1NTI4fQ.eJpUsudaoJwRADKHSKpoV1G2-qNt9HzLpHSA-W8OnHo"

logger = logging.getLogger("supabase_sync")

def _send_request(url: str, method: str, data: dict = None) -> dict:
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    encoded_data = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=encoded_data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as response:
            res_data = response.read().decode("utf-8")
            return json.loads(res_data) if res_data else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        logger.error(f"Supabase HTTP Error {e.code}: {err_body}")
        raise Exception(f"Error de Supabase ({e.code}): {err_body}")
    except Exception as e:
        logger.error(f"Supabase request failed: {e}")
        raise e

def create_supabase_user(email: str, password: str, name: str = None, school_id: int = 1, role: str = "alumno", dni: str = None) -> str:
    """
    Creates a user in Supabase Auth and inserts their profile in perfiles_escuela_{school_id} or alumnos.
    Returns the Supabase Auth UUID.
    """
    auth_url = f"{SUPABASE_URL}/auth/v1/admin/users"
    auth_data = {
        "email": email,
        "password": password,
        "email_confirm": True
    }
    
    supabase_uid = None
    try:
        auth_res = _send_request(auth_url, "POST", auth_data)
        supabase_uid = auth_res.get("id")
    except Exception as e:
        logger.info(f"Supabase auth user creation failed, searching for existing user: {e}")
        try:
            users_list = _send_request(auth_url, "GET")
            found_user = next((u for u in users_list.get("users", []) if u.get("email") == email), None)
            if found_user:
                supabase_uid = found_user.get("id")
                # Update password for the existing user
                _send_request(f"{auth_url}/{supabase_uid}", "PUT", {"password": password})
            else:
                raise e
        except Exception as search_err:
            logger.error(f"Search for existing Supabase user failed: {search_err}")
            raise e

    if not supabase_uid:
        raise Exception("No se pudo obtener el UUID del usuario en Supabase Auth")

    # 2. Insert or update profile in perfiles_escuela_{school_id} (or alumnos)
    import urllib.parse
    role_clean = (role or "alumno").lower().strip()
    if role_clean == "alumno":
        target_table = "alumnos"
        profile_data = {
            "nombre_completo": name or email.split("@")[0],
            "correo_electronico": email,
            "contrasena": password,
            "escuela_id": school_id,
            "dni": dni or ""
        }
        filter_query = f"correo_electronico=eq.{urllib.parse.quote(email)}"
    else:
        target_table = f"perfiles_escuela_{school_id}"
        profile_data = {
            "nombre_completo": name or email.split("@")[0],
            "correo_electronico": email,
            "contrasena": password,
            "rol": role,
            "dni": dni or ""
        }
        filter_query = f"correo_electronico=eq.{urllib.parse.quote(email)}"

    profile_url = f"{SUPABASE_URL}/rest/v1/{target_table}"
    try:
        _send_request(profile_url, "POST", profile_data)
    except Exception as e:
        if "already exists" in str(e) or "409" in str(e):
            logger.info(f"Record already exists in Supabase {target_table}, updating instead...")
            try:
                _send_request(f"{profile_url}?{filter_query}", "PATCH", profile_data)
            except Exception as patch_err:
                logger.error(f"Failed to patch existing profile in {target_table}: {patch_err}")
        else:
            logger.error(f"Error al crear perfil en Supabase ({target_table}): {e}")

    return supabase_uid

def update_supabase_user(supabase_uid: str, email: str = None, password: str = None) -> None:
    """
    Updates a user in Supabase Auth.
    """
    if not supabase_uid:
        return
    auth_url = f"{SUPABASE_URL}/auth/v1/admin/users/{supabase_uid}"
    auth_data = {}
    if email is not None:
        auth_data["email"] = email
    if password is not None:
        auth_data["password"] = password

    if auth_data:
        _send_request(auth_url, "PUT", auth_data)

def delete_supabase_user(supabase_uid: str) -> None:
    """
    Deletes a user from Supabase Auth and their profile is cascade-deleted.
    """
    if not supabase_uid:
        return
    auth_url = f"{SUPABASE_URL}/auth/v1/admin/users/{supabase_uid}"
    try:
        _send_request(auth_url, "DELETE")
    except Exception as e:
        logger.error(f"Error al eliminar usuario en Supabase: {e}")
