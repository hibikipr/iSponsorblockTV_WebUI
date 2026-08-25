"""Device pairing routes: GET /pair, POST /pair/code, POST /pair/save,
POST /pair/lan-scan, GET /pair/lan-scan/poll."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.services import config_io, lan_discovery
from app.services import pairing as pairing_service

router = APIRouter()


def _pair_context(request: Request, **extra) -> dict:
    return {
        "active": "pair",
        "lan_state": lan_discovery.get_state(),
        "launch_pair_timeout": lan_discovery.LAUNCH_PAIR_TIMEOUT,
        **extra,
    }


@router.get("", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    # Full render of the current devices list — anything in it counts as
    # "delivered" so the next poll only appends what's actually new.
    lan_discovery.mark_all_delivered()
    return request.app.state.templates.TemplateResponse(
        request, "pair.html", _pair_context(request)
    )


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
    return HTMLResponse(
        '<article class="toast ok">'
        f"Device <strong>{display_name or name}</strong> added to config. "
        'Restart the service from the <a href="/">config page</a> to apply.'
        "</article>"
    )


@router.post("/lan-scan", response_class=HTMLResponse)
async def lan_scan_start(request: Request) -> HTMLResponse:
    # start_scan() resets devices to [] and rendered_count to 0, so this is
    # a full (empty) render — nothing to mark delivered yet.
    await lan_discovery.start_scan()
    return request.app.state.templates.TemplateResponse(
        request, "partials/lan_scan_results.html", _pair_context(request)
    )


@router.get("/lan-scan/poll", response_class=HTMLResponse)
async def lan_scan_poll(request: Request) -> HTMLResponse:
    # Only the status strip gets re-rendered; newly discovered devices are
    # appended via OOB swap so an in-progress edit on an already-rendered
    # device row is never touched by this endpoint (issue #3 follow-up —
    # two earlier attempts at guarding the old full-div poll swap with JS
    # didn't hold up under real-hardware testing).
    new_devices = lan_discovery.take_new_devices()
    return request.app.state.templates.TemplateResponse(
        request,
        "partials/lan_scan_poll.html",
        _pair_context(request, new_devices=new_devices),
    )
