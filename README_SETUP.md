# Portfolio CMS implementation

## What is included
- Existing public portfolio design retained in `templates/index.html`.
- Supabase-backed records for projects, experience, skills, education, certifications, and profile.
- Admin login at `/admin/login`; dashboard at `/admin`.
- Existing `/api/contact` endpoint retained.
- Admin CRUD forms with CSRF tokens and signed session cookies.

## Before deploying
1. Run `sql/supabase_setup.sql` in Supabase SQL Editor.
2. Install dependencies: `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env`, then fill in secrets.
4. Generate a password hash:
   `python -c "from pwdlib import PasswordHash; print(PasswordHash.recommended().hash(input('Admin password: ')))"`
5. Generate a session secret:
   `python -c "import secrets; print(secrets.token_urlsafe(48))"`
6. Add all environment variables in Vercel Project Settings. Set `COOKIE_SECURE=true` in production.
7. Deploy and visit `/admin/login`.

## Important notes
- Do not commit `.env` or expose the Supabase secret key to browser JavaScript.
- The Supabase secret key bypasses RLS, so it is only used by server-side Python. Protect Vercel project access.
- This initial dashboard uses a JSON details field to cover different content types without needing separate forms for every field. The dashboard displays suggested JSON schemas for each type.
- Public education, experience, skills, projects, About text, headline, and resume link read from published database rows. Certifications are manageable in the admin panel; a dedicated public certifications section can be added if desired.
- If Supabase is unavailable, the public page falls back to the original hardcoded content. Admin operations require a working database.
- This implementation expects the repository's static files at `static/css/style.css`, `static/js/script.js`, and `static/images/`. Keep your existing `static/images` directory when copying files.
- Your original `vercel.json` was not uploaded. Keep it for now; verify that it routes the app to `main.py` and does not block `/admin` paths.
