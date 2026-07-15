from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
import io
import json
import os
import qrcode

from . import database as db

app = FastAPI(title="DS Office Client Tracker")

BASE_DIR = os.path.dirname(__file__)
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
templates.env.filters["tojson"] = json.dumps
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

# ---------------------------------------------------------------------------
# Admin login
#
# Set ADMIN_USERNAME / ADMIN_PASSWORD / SESSION_SECRET as environment
# variables in production (e.g. on Render). The defaults below are only
# for local testing and are NOT secure — change them before deploying.
# ---------------------------------------------------------------------------
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "cnrnext")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "plds")
SESSION_SECRET = os.environ.get("SESSION_SECRET", "dev-only-secret-change-me")

app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)


def is_logged_in(request: Request) -> bool:
    return request.session.get("is_admin") is True


@app.middleware("http")
async def add_cache_control_header(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response


db.init_db()


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "active": "home"})


# ---------- Front desk entry ----------
@app.get("/entry")
def entry_form(request: Request):
    return templates.TemplateResponse(
        "entry.html",
        {"request": request, "sections": db.SECTIONS, "token": None, "active": "entry"},
    )


@app.post("/entry")
def entry_submit(
    request: Request,
    name: str = Form(...),
    phone: str = Form(""),
    nic: str = Form(""),
    gender: str = Form(""),
    address: str = Form(""),
    purpose: str = Form(...),
    remarks: str = Form(""),
    sections: list[str] = Form([]),
):
    sections = [s for s in db.SECTIONS if s in sections]
    if not sections:
        sections = db.SECTIONS[:1]
    _id, token = db.create_client(
        name, phone, purpose, sections,
        nic=nic, gender=gender, address=address, remarks=remarks,
    )
    return templates.TemplateResponse(
        "entry.html",
        {
            "request": request, "sections": db.SECTIONS, "token": token,
            "client_name": name, "active": "entry",
        },
    )


# ---------- Self-registration via QR code ----------
@app.get("/register")
def register_form(request: Request):
    return templates.TemplateResponse(
        "register.html",
        {"request": request, "sections": db.SECTIONS, "token": None, "active": "register"},
    )


@app.post("/register")
def register_submit(
    request: Request,
    name: str = Form(...),
    phone: str = Form(""),
    nic: str = Form(""),
    purpose: str = Form(...),
    sections: list[str] = Form([]),
):
    sections = [s for s in db.SECTIONS if s in sections]
    if not sections:
        sections = db.SECTIONS[:1]
    _id, token = db.create_client(name, phone, purpose, sections, nic=nic)
    return templates.TemplateResponse(
        "register.html",
        {
            "request": request, "sections": db.SECTIONS, "token": token,
            "client_name": name, "active": "register",
        },
    )


@app.get("/qr")
def qr_page(request: Request):
    register_url = str(request.base_url).rstrip("/") + "/register"
    return templates.TemplateResponse(
        "qr.html", {"request": request, "active": "qr", "register_url": register_url},
    )


@app.get("/qr-image")
def qr_image(request: Request):
    register_url = str(request.base_url).rstrip("/") + "/register"
    img = qrcode.make(register_url, box_size=10, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")


@app.get("/qr-feedback")
def qr_feedback_page(request: Request):
    feedback_url = str(request.base_url).rstrip("/") + "/feedback?client=1"
    return templates.TemplateResponse(
        "qr_feedback.html", {"request": request, "active": "qr_feedback", "feedback_url": feedback_url},
    )


@app.get("/qr-feedback-image")
def qr_feedback_image(request: Request):
    feedback_url = str(request.base_url).rstrip("/") + "/feedback?client=1"
    img = qrcode.make(feedback_url, box_size=10, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")


# ---------- Section officer ----------
@app.get("/section")
def section_view(request: Request, name: str = ""):
    return templates.TemplateResponse(
        "section.html",
        {"request": request, "sections": db.SECTIONS, "selected": name, "active": "section"},
    )


# ---------- Public display ----------
@app.get("/display")
def display_view(request: Request):
    return templates.TemplateResponse("display.html", {"request": request, "active": "display"})


# ---------- Feedback ----------
@app.get("/feedback")
def feedback_form(request: Request, client: int = 0):
    return templates.TemplateResponse(
        "feedback.html",
        {"request": request, "sections": db.SECTIONS, "active": "feedback", "submitted": False, "is_client": bool(client)},
    )


@app.post("/feedback")
def feedback_submit(
    request: Request,
    client: int = 0,
    name: str = Form(""),
    section: str = Form(...),
    reason: str = Form(...),
    rating: str = Form(...),
):
    if rating not in ("good", "average", "poor"):
        rating = "average"
    db.create_feedback(section=section, reason=reason, rating=rating, name=name)
    return templates.TemplateResponse(
        "feedback.html",
        {"request": request, "sections": db.SECTIONS, "active": "feedback", "submitted": True, "is_client": bool(client)},
    )


# ---------- Admin login ----------
@app.get("/admin/login")
def admin_login_form(request: Request, error: str = "", next: str = "/admin"):
    if is_logged_in(request):
        return RedirectResponse(url=next)
    return templates.TemplateResponse("login.html", {"request": request, "error": error, "next": next})


@app.post("/admin/login")
def admin_login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/admin"),
):
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        request.session["is_admin"] = True
        return RedirectResponse(url=next, status_code=303)
    return RedirectResponse(url=f"/admin/login?error=1&next={next}", status_code=303)


@app.get("/admin/logout")
def admin_logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/")


# ---------- Admin dashboard ----------
@app.get("/admin")
def admin_view(request: Request):
    if not is_logged_in(request):
        return RedirectResponse(url="/admin/login?next=/admin")
    return templates.TemplateResponse(
        "admin.html", {"request": request, "sections": db.SECTIONS, "active": "admin"}
    )


@app.get("/staff")
def staff_redirect():
    return RedirectResponse(url="/admin")


# ---------- JSON API ----------
@app.get("/api/clients")
def api_clients(active: bool = False, section: str = None):
    return JSONResponse(db.get_all_clients(active_only=active, section=section))


@app.get("/api/stats")
def api_stats():
    return JSONResponse(db.get_stats())


@app.get("/api/feedback")
def api_feedback(request: Request):
    if not is_logged_in(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return JSONResponse(db.get_all_feedback())


@app.get("/api/feedback-stats")
def api_feedback_stats(request: Request):
    if not is_logged_in(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return JSONResponse(db.get_feedback_stats())


@app.post("/api/clients/{client_id}/section/{section}")
def api_update_section(client_id: int, section: str, status: str = Form(...)):
    client = db.update_section_status(client_id, section, status)
    if client is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(client)
