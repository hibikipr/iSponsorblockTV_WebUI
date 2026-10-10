"""Config form: GET /, GET /devices/blank-row, POST /save, POST /restart."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app import settings
from app.services import config_io, service_status
from app.services import restart as restart_service

router = APIRouter()

OFFSET_CHOICES = list(range(-2000, 2001, 250))
MIN_SKIP_CHOICES = [0, 1, 2, 3, 5, 10, 30, 60]


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    cfg = config_io.load()
    return request.app.state.templates.TemplateResponse(
        request,
        "config.html",
        {
            "cfg": cfg,
            "config_path": str(settings.config_path()),
            "skip_category_choices": sorted(
                config_io.SKIP_CATEGORY_LABELS.items(),
                key=lambda kv: kv[1],
            ),
            "offset_choices": OFFSET_CHOICES,
            "min_skip_choices": MIN_SKIP_CHOICES,
            "st": service_status.status(),
            "active": "config",
        },
    )


@router.post("/save", response_class=HTMLResponse)
async def save(request: Request) -> HTMLResponse:
    form = await request.form()
    existing = config_io.load()
    new_cfg = _form_to_config(form, existing)
    try:
        config_io.save(new_cfg)
    except OSError as e:
        return _toast(request, ok=False, message=f"Save failed: {e}")
    result = restart_service.restart()
    return _toast(request, ok=result.ok, message=f"Saved. {result.message()}")


@router.post("/restart", response_class=HTMLResponse)
async def restart_only(request: Request) -> HTMLResponse:
    """Restart without touching config.json.

    For flows that change config.json without going through this page's own
    form (e.g. /pair/save adding a device) - the config page's Save button
    is dirty-gated (disabled until *this* form is edited), so a config
    change made elsewhere leaves no client-side way to trigger the restart
    that's actually needed to apply it. This exists so those flows have
    something to link/POST to directly instead of routing the user through
    a button that's disabled for exactly the reason they're there.
    """
    result = restart_service.restart()
    return _toast(request, ok=result.ok, message=result.message())


def _form_to_config(form: Any, existing: dict[str, Any]) -> dict[str, Any]:
    names = form.getlist("device_name")
    screen_ids = form.getlist("device_screen_id")
    offsets = form.getlist("device_offset")
    devices = []
    for n, s, o in zip(names, screen_ids, offsets):
        if str(s).strip():
            devices.append({"name": n, "screen_id": s, "offset": o or 0})
    return {
        "devices": devices,
        "skip_categories": form.getlist("skip_categories"),
        "minimum_skip_length": form.get("minimum_skip_length") or 0,
        "skip_count_tracking": form.get("skip_count_tracking") == "on",
        "mute_ads": form.get("mute_ads") == "on",
        "skip_ads": form.get("skip_ads") == "on",
        "auto_play": form.get("auto_play") == "on",
        "join_name": form.get("join_name") or "iSponsorBlockTV",
        # Preserved from disk — managed via /channels (apikey, use_proxy)
        # and the /channels page itself (channel_whitelist).
        "apikey": existing.get("apikey", ""),
        "use_proxy": existing.get("use_proxy", False),
        "channel_whitelist": existing.get("channel_whitelist", []),
    }


def _toast(request: Request, ok: bool, message: str) -> HTMLResponse:
    return request.app.state.templates.TemplateResponse(
        request, "partials/toast.html", {"ok": ok, "message": message}
    )
