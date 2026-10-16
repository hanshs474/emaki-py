"""Official Python SDK for emaki (https://emaki.ai), the Japanese-language AI
video generator for Seedance 2.5 and Seedance 2.0.

    from emaki import generate_video, generate_image
    clip = generate_video("a paper boat drifting down a rain gutter, low angle")
    pic = generate_image("a paper-cut layered mountain range at dusk")

Create a key at https://emaki.ai/settings/apikeys and pass it as
``api_key=`` or set ``EMAKI_API_KEY``. Runs cost credits on your emaki
account, the same price as on the website.

Standard library only.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, Optional, Tuple

__version__ = "0.1.0"
__all__ = [
    "generate_video",
    "generate_image",
    "submit",
    "status",
    "wait",
    "credits",
    "EmakiError",
    "AuthError",
    "QuotaError",
    "PlanError",
    "BusyError",
    "RejectedError",
    "GenerationFailed",
    "VIDEO_MODELS",
    "IMAGE_MODELS",
    "BASE",
]

BASE = "https://emaki.ai"
KEYS_URL = BASE + "/settings/apikeys"

#: Video model ids. ``seedance_2_5`` is the default.
VIDEO_MODELS = (
    "seedance_2_5",
    "seedance_2",
    "seedance_2_fast",
    "seedance_2_mini",
    "minimax_h3",
    "veo_3_1",
)
#: Image model ids. ``nano_banana_2_lite`` is the default and the cheapest.
IMAGE_MODELS = (
    "nano_banana_2_lite",
    "nano_banana_2",
    "seedream_5_lite",
    "gpt_image_2",
)

DEFAULT_VIDEO_MODEL = "seedance_2_5"
DEFAULT_IMAGE_MODEL = "nano_banana_2_lite"


class EmakiError(RuntimeError):
    """Base class. Catch a subclass to decide what to do next."""

    def __init__(self, message: str, status: Optional[int] = None, code: Optional[str] = None):
        super().__init__(message)
        self.status = status
        self.code = code


class AuthError(EmakiError):
    """No API key, or the key is invalid or deleted (HTTP 401)."""


class QuotaError(EmakiError):
    """The account is out of credits (HTTP 402)."""


class PlanError(EmakiError):
    """This model needs a purchase on the account first (HTTP 403)."""


class BusyError(EmakiError):
    """Another generation on this account is still running (HTTP 409)."""


class RejectedError(EmakiError):
    """The content filter refused the prompt, or a cooldown is active. Reword it."""


class GenerationFailed(EmakiError):
    """The run was accepted but ended as failed; ``code`` carries the failureCode."""


Transport = Callable[[str, str, Optional[dict], dict], Tuple[int, dict]]


def _http(method: str, url: str, body: Optional[dict], headers: dict) -> Tuple[int, dict]:
    headers = {**headers, "User-Agent": f"emaki-python/{__version__}"}
    data = json.dumps(body if body is not None else {}).encode()
    headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            code = r.status
    except urllib.error.HTTPError as e:
        raw = e.read() or b""
        code = e.code
    try:
        parsed = json.loads(raw) if raw else {}
    except ValueError:
        parsed = {"error": raw[:200].decode("utf-8", "replace")}
    return code, parsed if isinstance(parsed, dict) else {"data": parsed}


def _raise_for(status_code: int, env: dict) -> None:
    """Map an error response to the subclass that says what to do next."""
    msg = str(env.get("error") or env.get("message") or f"HTTP {status_code}")
    code = env.get("code") if isinstance(env.get("code"), str) else None
    if status_code == 401:
        raise AuthError(msg, status_code, code)
    if status_code == 402:
        raise QuotaError(msg, status_code, code)
    if status_code == 403:
        raise PlanError(msg, status_code, code)
    if status_code == 409:
        raise BusyError(msg, status_code, code)
    if code in ("content_cooldown", "content_blocked"):
        raise RejectedError(msg, status_code, code)
    raise EmakiError(msg, status_code, code)


def _key(api_key: Optional[str]) -> str:
    key = api_key or os.environ.get("EMAKI_API_KEY") or None
    if not key:
        raise AuthError(f"pass api_key= or set EMAKI_API_KEY; create a key at {KEYS_URL}")
    return key


def _call(path: str, body: Optional[dict], api_key: Optional[str], base_url: str, transport: Optional[Transport]) -> Tuple[int, dict]:
    http = transport or _http
    return http("POST", base_url + path, body, {"Authorization": f"Bearer {_key(api_key)}"})


def submit(
    prompt: str,
    model: str = DEFAULT_VIDEO_MODEL,
    *,
    api_key: Optional[str] = None,
    base_url: str = BASE,
    transport: Optional[Transport] = None,
    **parameters: Any,
) -> str:
    """Start one run and return its id without waiting.

    Extra keyword arguments go into ``parameters`` as they are, e.g.
    ``duration=5, resolution="720p", aspect_ratio="9:16", image="https://…"``.
    """
    if not str(prompt or "").strip():
        raise ValueError("prompt is required")
    params = {k: v for k, v in parameters.items() if v is not None}
    st, env = _call("/api/video/ai", {"prompt": prompt, "model": model, "parameters": params}, api_key, base_url, transport)
    if st != 200 or not env.get("success"):
        _raise_for(st, env)
    vid = (env.get("data") or {}).get("id")
    if not vid:
        raise EmakiError("the service returned no id", st)
    return str(vid)


def status(
    video_id: str,
    *,
    api_key: Optional[str] = None,
    base_url: str = BASE,
    transport: Optional[Transport] = None,
) -> Dict[str, Any]:
    """Return the run record: ``status`` is generating, completed or failed;
    ``videoUrl`` holds the result URL (images too)."""
    st, env = _call("/api/video/status", {"videoId": video_id}, api_key, base_url, transport)
    if st != 200 or not env.get("success"):
        _raise_for(st, env)
    return env.get("data") or {}


def wait(
    video_id: str,
    *,
    api_key: Optional[str] = None,
    timeout: float = 900.0,
    poll_every: float = 5.0,
    base_url: str = BASE,
    transport: Optional[Transport] = None,
) -> str:
    """Poll a run until it finishes and return the result URL."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            data = status(video_id, api_key=api_key, base_url=base_url, transport=transport)
        except (OSError, ValueError):
            data = {}  # a dropped poll is not a failed generation
        state = str(data.get("status") or "").lower()
        if state == "completed" and data.get("videoUrl"):
            return str(data["videoUrl"])
        if state == "failed":
            fc = data.get("failureCode")
            raise GenerationFailed(f"the run failed ({fc or 'no failure code'})", None, fc)
        if time.monotonic() >= deadline:
            raise EmakiError(f"deadline passed after {timeout:g}s; run {video_id} may still finish in your emaki library")
        time.sleep(poll_every)


def generate_video(
    prompt: str,
    model: str = DEFAULT_VIDEO_MODEL,
    *,
    api_key: Optional[str] = None,
    timeout: float = 900.0,
    poll_every: float = 5.0,
    base_url: str = BASE,
    transport: Optional[Transport] = None,
    **parameters: Any,
) -> str:
    """Generate one clip and return its URL. Pass ``image=`` (an https URL) to
    use it as the first frame."""
    vid = submit(prompt, model, api_key=api_key, base_url=base_url, transport=transport, **parameters)
    return wait(vid, api_key=api_key, timeout=timeout, poll_every=poll_every, base_url=base_url, transport=transport)


def generate_image(
    prompt: str,
    model: str = DEFAULT_IMAGE_MODEL,
    *,
    api_key: Optional[str] = None,
    timeout: float = 900.0,
    poll_every: float = 5.0,
    base_url: str = BASE,
    transport: Optional[Transport] = None,
    **parameters: Any,
) -> str:
    """Generate one image and return its URL."""
    return generate_video(
        prompt, model, api_key=api_key, timeout=timeout, poll_every=poll_every,
        base_url=base_url, transport=transport, **parameters,
    )


def credits(
    *,
    api_key: Optional[str] = None,
    base_url: str = BASE,
    transport: Optional[Transport] = None,
) -> int:
    """Return the remaining credits on the account. Free to call."""
    st, env = _call("/api/user/get-user-credits", None, api_key, base_url, transport)
    if st == 200 and env.get("code") == 0:
        return int((env.get("data") or {}).get("remainingCredits") or 0)
    # This endpoint answers refusals with HTTP 200 and code -1.
    msg = str(env.get("message") or env.get("error") or f"HTTP {st}")
    if st == 401 or any(w in msg.lower() for w in ("api key", "no auth", "unauthorized", "sign in")):
        raise AuthError(msg, st)
    if st != 200:
        _raise_for(st, env)
    raise EmakiError(msg, st)
