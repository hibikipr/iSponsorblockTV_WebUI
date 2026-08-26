"""Device pairing routes: GET /pair, POST /pair/code, POST /pair/save."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.services import config_io
from app.services import pairing as pairing_service

router = APIRouter()


@router.get("", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return request.app.state.templates.TemplateResponse(request, "pair.html", {"active": "pair"})


@router.post("/code", response_class=HTMLResponse)
async def pair_code(request: Request, code: str = Form(...)) -> HTMLResponse:
    try:
        device = await pairing_service.pair_with_code(code)
    except pairing_service.PairingError as e:
        return HTMLResponse(f'<article class="toast err">{e}</article>')
    if device is None:
        return HTMLResponse('<article class="toast err">Pairing returned no device.</article>')
    return request.app.state.templates.TemplateResponse(
        request, "partials/paired_device.html", {"device": device}
    )


@router.post("/save", response_class=HTMLResponse)
async def pair_save(
    screen_id: str = Form(...),
    name: str = Form(...),
    display_name: str = Form(...),
    offset: int = Form(0),
) -> HTMLResponse:
    cfg = config_io.load()
    devices = cfg.get("devices", [])
    if any(d["screen_id"] == screen_id for d in devices):
        return HTMLResponse(
            '<article class="toast err">A device with this screen ID is already in config.</article>'
        )
    devices.append({"screen_id": screen_id, "name": display_name or name, "offset": offset})
    cfg["devices"] = devices
    config_io.save(cfg)
    # Not a link to the config page's own Save button: that button is
    # dirty-gated (disabled until its form is edited), so it stays disabled
    # here since nothing was edited *there* - this config.json change came
    # from this page instead. POSTs straight to the standalone /restart
    # endpoint so there's actually something clickable to apply it with.
    return HTMLResponse(
        '<article class="toast ok">'
        f"Device <strong>{display_name or name}</strong> added to config. "
        "Restart to apply it: "
        '<form hx-post="/restart" hx-swap="none" style="display:inline;">'
        '<button type="submit" class="secondary">Restart service</button>'
        "</form>"
        "</article>"
    )
