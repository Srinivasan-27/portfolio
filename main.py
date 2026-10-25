import html
import os
import secrets
from datetime import datetime
from typing import Any
import uuid

from dotenv import load_dotenv
from fastapi import ( FastAPI, File, Form, HTTPException, Request, UploadFile, status,)
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from itsdangerous import BadSignature, URLSafeSerializer
from pydantic import BaseModel, EmailStr
from pwdlib import PasswordHash
from starlette.middleware.sessions import SessionMiddleware

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = FastAPI(title="Srinivasan Portfolio", version="3.0.0")
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET", "development-only-change-this-secret"),
    same_site="lax",
    https_only=os.getenv("COOKIE_SECURE", "false").lower() == "true",
    max_age=60 * 60 * 8,
)
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

password_hash = PasswordHash.recommended()
csrf_signer = URLSafeSerializer(os.getenv("SESSION_SECRET", "development-only-change-this-secret"), salt="portfolio-csrf")


class ContactForm(BaseModel):
    fullname: str
    email: EmailStr
    message: str


def get_db():
    """Create a Supabase client lazily so missing configuration doesn't break app import."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise HTTPException(status_code=503, detail="Portfolio database is not configured.")
    from supabase import create_client
    return create_client(url, key)

    
async def upload_project_image(image_file: UploadFile) -> str:
    """Validate and upload a project image to Supabase Storage."""

    allowed_types = {
        "image/jpeg": ("jpg", b"\xff\xd8\xff"),
        "image/png": ("png", b"\x89PNG\r\n\x1a\n"),
        "image/gif": ("gif", b"GIF8"),
        "image/webp": ("webp", b"RIFF"),
    }

    content_type = (image_file.content_type or "").lower()

    if content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Only JPEG, PNG, GIF, and WebP images are allowed.",
        )

    # Read at most 5 MB plus one byte to detect oversized uploads.
    contents = await image_file.read(5 * 1024 * 1024 + 1)

    if not contents:
        raise HTTPException(
            status_code=400,
            detail="The selected image is empty.",
        )

    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail="Image must be 5 MB or smaller.",
        )

    extension, signature = allowed_types[content_type]

    if not contents.startswith(signature):
        raise HTTPException(
            status_code=400,
            detail="The file contents do not match the selected image type.",
        )

    # WebP files begin with RIFF and identify themselves as WEBP at bytes 8–11.
    if content_type == "image/webp" and contents[8:12] != b"WEBP":
        raise HTTPException(
            status_code=400,
            detail="Invalid WebP image.",
        )

    object_path = f"projects/{uuid.uuid4().hex}.{extension}"

    try:
        db = get_db()

        db.storage.from_("portfolio-images").upload(
            object_path,
            contents,
            file_options={
                "content-type": content_type,
                "upsert": "false",
            },
        )

        public_url = db.storage.from_(
            "portfolio-images"
        ).get_public_url(object_path)

        if not isinstance(public_url, str) or not public_url.startswith("https://"):
            raise RuntimeError("Could not obtain the public image URL.")

        return public_url

    except HTTPException:
        raise
    except Exception:
        # Avoid exposing database credentials or internal details.
        raise HTTPException(
            status_code=502,
            detail="Image upload failed. Check Supabase Storage configuration.",
        )



def is_admin(request: Request) -> bool:
    return bool(request.session.get("admin_authenticated") is True)


def require_admin(request: Request) -> None:
    if not is_admin(request):
        raise HTTPException(status_code=401, detail="Please log in to access the admin dashboard.")


def csrf_token_for(request: Request) -> str:
    token = request.session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token
    return token


def check_csrf(request: Request, submitted: str) -> None:
    expected = request.session.get("csrf_token", "")
    if not expected or not secrets.compare_digest(expected, submitted or ""):
        raise HTTPException(status_code=403, detail="Invalid form token. Refresh and try again.")


def read_items(item_type: str | None = None, published_only: bool = False) -> list[dict[str, Any]]:
    db = get_db()
    query = db.table("portfolio_items").select("*").order("sort_order")
    if item_type:
        query = query.eq("item_type", item_type)
    if published_only:
        query = query.eq("published", True)
    response = query.execute()
    return response.data or []


def clean_text(value: str, max_len: int = 12000) -> str:
    return value.strip()[:max_len]


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    # Keep the current public design as the fallback if the database has not yet been seeded.
    try:
        items = read_items(published_only=True)
    except Exception:
        items = []
    grouped: dict[str, list[dict[str, Any]]] = {}
    profile = {}
    for item in items:
        kind = item.get("item_type")
        data = item.get("data") or {}
        entry = {"id": item.get("id"), "title": item.get("title", ""), "data": data}
        grouped.setdefault(kind, []).append(entry)
        if kind == "profile":
            profile.update(data)
            profile.setdefault("name", item.get("title", "Srinivasan G"))
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"portfolio": grouped, "profile": profile},
    )


@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    if is_admin(request):
        return RedirectResponse("/admin", status_code=303)
    return templates.TemplateResponse(
        request=request, name="admin_login.html",
        context={"csrf_token": csrf_token_for(request), "error": None},
    )


@app.post("/admin/login", response_class=HTMLResponse)
async def admin_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
):
    check_csrf(request, csrf_token)
    expected_username = os.getenv("ADMIN_USERNAME", "")
    stored_hash = os.getenv("ADMIN_PASSWORD_HASH", "")
    valid = bool(expected_username and stored_hash and secrets.compare_digest(username, expected_username))
    if valid:
        try:
            valid = password_hash.verify(password, stored_hash)
        except Exception:
            valid = False
    if not valid:
        # Avoid revealing whether username or password was incorrect.
        return templates.TemplateResponse(
            request=request, name="admin_login.html", status_code=401,
            context={"csrf_token": csrf_token_for(request), "error": "Invalid username or password."},
        )
    request.session.clear()
    request.session["admin_authenticated"] = True
    request.session["csrf_token"] = secrets.token_urlsafe(32)
    return RedirectResponse("/admin", status_code=303)


@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request, kind: str = "project", message: str = ""):
    require_admin(request)
    allowed = {"project", "experience", "skill", "education", "certification", "profile"}
    if kind not in allowed:
        kind = "project"
    try:
        items = read_items(kind)
        counts = {k: len(read_items(k)) for k in sorted(allowed)}
        db_error = None
    except Exception as exc:
        items, counts, db_error = [], {}, str(exc)
    return templates.TemplateResponse(
        request=request, name="admin_dashboard.html",
        context={
            "csrf_token": csrf_token_for(request), "kind": kind, "items": items,
            "counts": counts, "message": message, "db_error": db_error,
            "allowed_kinds": ["project", "experience", "skill", "education", "certification", "profile"],
        },
    )


@app.post("/admin/items")
async def create_item(
    request: Request,
    csrf_token: str = Form(...),
    item_type: str = Form(...),
    title: str = Form(...),
    data_json: str = Form("{}"),
    sort_order: int = Form(0),
    published: str | None = Form(None),
    description: str | None = Form(None),
    category: str | None = Form(None),
    technologies: str | None = Form(None),
    image: str | None = Form(None),
    image_file: UploadFile | None = File(None),
    url: str | None = Form(None),
    github_url: str | None = Form(None),
):
    require_admin(request)
    check_csrf(request, csrf_token)

    import json

    allowed = {
        "project",
        "experience",
        "skill",
        "education",
        "certification",
        "profile",
    }

    if item_type not in allowed:
        raise HTTPException(
            status_code=400,
            detail="Unsupported content type.",
        )

    clean_title = clean_text(title, 200)

    if not clean_title:
        raise HTTPException(
            status_code=400,
            detail="A title is required.",
        )

    if item_type == "project":
        clean_description = clean_text(description or "")

        if not clean_description:
            raise HTTPException(
                status_code=400,
                detail="A project description is required.",
            )

        # Keep existing local paths or external image URLs when supplied.
        image_url = clean_text(image or "", 1000)

        if image_file and image_file.filename:
            image_url = await upload_project_image(image_file)

        technology_list = [
            clean_text(value, 100)
            for value in (technologies or "").split(",")
            if value.strip()
        ]

        data = {
            "description": clean_description,
            "category": clean_text(category or "", 100),
            "technologies": technology_list,
            "image": image_url,
            "url": clean_text(url or "", 1000),
            "github_url": clean_text(github_url or "", 1000),
        }

    else:
        try:
            data = json.loads(data_json or "{}")

            if not isinstance(data, dict):
                raise ValueError(
                    "Content data must be a JSON object."
                )

        except (ValueError, json.JSONDecodeError):
            raise HTTPException(
                status_code=400,
                detail="Content details must be valid JSON.",
            )

    get_db().table("portfolio_items").insert({
        "item_type": item_type,
        "title": clean_title,
        "data": data,
        "sort_order": sort_order,
        "published": published == "on",
    }).execute()

    return RedirectResponse(
        f"/admin?kind={item_type}&message=Content+added",
        status_code=303,
    )



@app.post("/admin/items/{item_id}/update")
async def update_item(
    request: Request,
    item_id: int,
    csrf_token: str = Form(...),
    item_type: str = Form(...),
    title: str = Form(...),
    data_json: str = Form("{}"),
    sort_order: int = Form(0),
    published: str | None = Form(None),
    description: str | None = Form(None),
    category: str | None = Form(None),
    technologies: str | None = Form(None),
    image: str | None = Form(None),
    image_file: UploadFile | None = File(None),
    url: str | None = Form(None),
    github_url: str | None = Form(None),
):
    require_admin(request)
    check_csrf(request, csrf_token)

    import json

    allowed = {"project", "experience", "skill", "education", "certification", "profile"}
    if item_type not in allowed:
        raise HTTPException(status_code=400, detail="Unsupported content type.")

    clean_title = clean_text(title, 200)
    if not clean_title:
        raise HTTPException(status_code=400, detail="A title is required.")

    db = get_db()
    existing_response = (
        db.table("portfolio_items")
        .select("*")
        .eq("id", item_id)
        .limit(1)
        .execute()
    )
    existing_rows = existing_response.data or []
    if not existing_rows:
        raise HTTPException(status_code=404, detail="Portfolio item not found.")

    existing = existing_rows[0]
    if existing.get("item_type") != item_type:
        raise HTTPException(status_code=400, detail="Item type does not match the selected record.")

    if item_type == "project":
        clean_description = clean_text(description or "")
        if not clean_description:
            raise HTTPException(status_code=400, detail="A project description is required.")

        # Keep the existing image unless a replacement URL or new upload is supplied.
        existing_data = existing.get("data") or {}
        image_url = clean_text(image or existing_data.get("image", ""), 1000)
        if image_file and image_file.filename:
            image_url = await upload_project_image(image_file)

        technology_list = [
            clean_text(value, 100)
            for value in (technologies or "").split(",")
            if value.strip()
        ]
        data = {
            **existing_data,
            "description": clean_description,
            "category": clean_text(category or "", 100),
            "technologies": technology_list,
            "image": image_url,
            "url": clean_text(url or "", 1000),
            "github_url": clean_text(github_url or "", 1000),
        }
    else:
        try:
            data = json.loads(data_json or "{}")
            if not isinstance(data, dict):
                raise ValueError("Content data must be a JSON object.")
        except (ValueError, json.JSONDecodeError):
            raise HTTPException(status_code=400, detail="Content details must be valid JSON.")

    db.table("portfolio_items").update({
        "item_type": item_type,
        "title": clean_title,
        "data": data,
        "sort_order": sort_order,
        "published": published == "on",
        "updated_at": datetime.utcnow().isoformat(),
    }).eq("id", item_id).execute()

    return RedirectResponse(
        f"/admin?kind={item_type}&message=Content+updated",
        status_code=303,
    )



@app.post("/admin/items/{item_id}/delete")
async def delete_item(request: Request, item_id: int, csrf_token: str = Form(...), item_type: str = Form("project")):
    require_admin(request)
    check_csrf(request, csrf_token)
    get_db().table("portfolio_items").delete().eq("id", item_id).execute()
    return RedirectResponse(f"/admin?kind={item_type}&message=Content+deleted", status_code=303)


@app.post("/admin/logout")
async def admin_logout(request: Request, csrf_token: str = Form(...)):
    require_admin(request)
    check_csrf(request, csrf_token)
    request.session.clear()
    return RedirectResponse("/admin/login", status_code=303)


@app.post("/api/contact", status_code=status.HTTP_200_OK)
async def submit_contact_form(contact: ContactForm):
    """Existing public contact endpoint retained; HTML content is escaped before email."""
    required_mail_vars = ["MAIL_USERNAME", "MAIL_PASSWORD", "MAIL_FROM", "MAIL_SERVER"]
    if not all(os.getenv(name) for name in required_mail_vars):
        raise HTTPException(status_code=503, detail="Contact email is not configured.")
    html_body = f"""
    <h3>New Portfolio Contact Submission</h3>
    <p><b>Name:</b> {html.escape(contact.fullname)}</p>
    <p><b>Email:</b> {html.escape(str(contact.email))}</p>
    <p><b>Message:</b></p><p>{html.escape(contact.message).replace(chr(10), '<br>')}</p>
    """
    conf = ConnectionConfig(
        MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
        MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
        MAIL_FROM=os.getenv("MAIL_FROM"),
        MAIL_PORT=int(os.getenv("MAIL_PORT", "587")),
        MAIL_SERVER=os.getenv("MAIL_SERVER"),
        MAIL_STARTTLS=os.getenv("MAIL_STARTTLS", "true").lower() in ("true", "1", "t"),
        MAIL_SSL_TLS=os.getenv("MAIL_SSL_TLS", "false").lower() in ("true", "1", "t"),
        USE_CREDENTIALS=True,
        VALIDATE_CERTS=True,
    )
    message = MessageSchema(
        subject=f"New Portfolio Contact: {contact.fullname}",
        recipients=[os.getenv("MAIL_FROM")],
        body=html_body,
        subtype=MessageType.html,
    )
    try:
        await FastMail(conf).send_message(message)
        return {"status": "success", "message": "Contact form submitted successfully."}
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to send email. Please try again later.")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=True)
