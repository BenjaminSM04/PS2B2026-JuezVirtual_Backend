import os
import re
import smtplib
import datetime
import random
from base64 import b64encode
from io import BytesIO

from django.core.exceptions import ImproperlyConfigured
from django.utils.crypto import get_random_string
from envelopes import Envelope


def rand_str(length=32, type="lower_hex"):
    """
    生成指定长度的随机字符串或者数字, 可以用于密钥等安全场景
    :param length: 字符串或者数字的长度
    :param type: str 代表随机字符串，num 代表随机数字
    :return: 字符串
    """
    if type == "str":
        return get_random_string(length, allowed_chars="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789")
    elif type == "lower_str":
        return get_random_string(length, allowed_chars="abcdefghijklmnopqrstuvwxyz0123456789")
    elif type == "lower_hex":
        return random.choice("123456789abcdef") + get_random_string(length - 1, allowed_chars="0123456789abcdef")
    else:
        return random.choice("123456789") + get_random_string(length - 1, allowed_chars="0123456789")


def build_query_string(kv_data, ignore_none=True):
    # {"a": 1, "b": "test"} -> "?a=1&b=test"
    query_string = ""
    for k, v in kv_data.items():
        if ignore_none is True and kv_data[k] is None:
            continue
        if query_string != "":
            query_string += "&"
        else:
            query_string = "?"
        query_string += (k + "=" + str(v))
    return query_string


def img2base64(img):
    with BytesIO() as buf:
        img.save(buf, "gif")
        buf_str = buf.getvalue()
    img_prefix = "data:image/png;base64,"
    b64_str = img_prefix + b64encode(buf_str).decode("utf-8")
    return b64_str


def datetime2str(value, format="iso-8601"):
    if format.lower() == "iso-8601":
        value = value.isoformat()
        if value.endswith("+00:00"):
            value = value[:-6] + "Z"
        return value
    return value.strftime(format)


def timestamp2utcstr(value):
    return datetime.datetime.utcfromtimestamp(value).isoformat()


def natural_sort_key(s, _nsre=re.compile(r"(\d+)")):
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(_nsre, s)]


def send_email(smtp_config, from_name, to_email, to_name, subject, content):
    required_keys = ("email", "server", "port", "password", "tls")
    missing = [k for k in required_keys if k not in smtp_config or smtp_config[k] in (None, "")]
    if missing:
        raise ValueError(f"SMTP config is incomplete; missing keys: {', '.join(missing)}")

    envelope = Envelope(from_addr=(smtp_config["email"], from_name),
                        to_addr=(to_email, to_name),
                        subject=subject,
                        html_body=content)
    try:
        return envelope.send(smtp_config["server"],
                             login=smtp_config["email"],
                             password=smtp_config["password"],
                             port=smtp_config["port"],
                             tls=smtp_config["tls"])
    except smtplib.SMTPResponseException as e:
        # qq mail can return gbk-encoded error bodies
        try:
            detail = e.smtp_error.decode("gbk") if isinstance(e.smtp_error, bytes) else str(e.smtp_error)
        except Exception:
            detail = str(e.smtp_error)
        raise RuntimeError(f"SMTP error {e.smtp_code}: {detail}") from e
    except smtplib.SMTPException as e:
        raise RuntimeError(f"SMTP failure: {e}") from e


def get_env(name, default=""):
    return os.environ.get(name, default)


_ENV_VERDADERO = {"1", "true", "yes", "on", "si", "sí"}
_ENV_FALSO = {"0", "false", "no", "off", ""}


def get_env_bool(name, default=False):
    """Lee un booleano de configuración del entorno; falla cerrado si es ambiguo.

    Acepta 1/true/yes/on/si/sí y 0/false/no/off/vacío, sin distinguir
    mayúsculas. Un valor desconocido (p. ej. "tru") lanza ImproperlyConfigured
    en lugar de degradar en silencio una opción de seguridad. Ausente -> default.
    """
    raw = os.environ.get(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in _ENV_VERDADERO:
        return True
    if value in _ENV_FALSO:
        return False
    raise ImproperlyConfigured(
        f"Valor no válido para {name}: {raw!r}. Use 1/true/yes/on/si o 0/false/no/off.")


def _split_env_list(raw):
    return [item.strip() for item in raw.split(",") if item.strip()]


def env_list(primary, alias, default=""):
    """Lista separada por comas desde `primary`, o `alias`, o `default`.

    Una variable vacía cuenta como no definida (compose pasa así las opcionales).
    Si ambas tienen listas distintas se lanza ImproperlyConfigured: no se elige
    una en silencio.
    """
    raw_primary = os.environ.get(primary, "").strip() or None
    raw_alias = os.environ.get(alias, "").strip() or None
    if raw_primary is None and raw_alias is None:
        return _split_env_list(default)
    if raw_primary is None:
        return _split_env_list(raw_alias)
    if raw_alias is not None and _split_env_list(raw_alias) != _split_env_list(raw_primary):
        raise ImproperlyConfigured(
            f"{primary} y {alias} están definidas con valores distintos; defina solo una o use el mismo valor.")
    return _split_env_list(raw_primary)


def DRAMATIQ_WORKER_ARGS(time_limit=3600_000, max_retries=0, max_age=7200_000):
    return {"max_retries": max_retries, "time_limit": time_limit, "max_age": max_age}


def dramatiq_worker_alive():
    """True si Redis es accesible y hay al menos un worker rundramatiq vivo.

    Dramatiq publica una clave de heartbeat por worker activo. Si no hay
    heartbeats, encolar una tarea async la dejaría sin procesar (envío
    silencioso). Cualquier fallo (Redis caído, broker mal configurado) -> False.
    """
    try:
        import dramatiq
        broker = dramatiq.get_broker()
        client = getattr(broker, "client", None)
        if client is None:
            return False
        client.ping()
        return bool(client.keys("dramatiq:__heartbeats__*"))
    except Exception:
        return False


def check_is_id(value):
    try:
        return int(value) > 0
    except Exception:
        return False
