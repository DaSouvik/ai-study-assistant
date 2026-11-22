# Study Desk

A Streamlit study app for private PDF libraries, summaries, quizzes,
flashcards, and searchable notes. Google OIDC identifies each account; Supabase
PostgreSQL stores documents with an owner ID so one account cannot browse,
search, or delete another account's records.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .streamlit\secrets.toml.example .streamlit\secrets.toml
python -m streamlit run app.py
```

Before running, replace the example values in `.streamlit/secrets.toml` with
your Google OAuth credentials and Supabase PostgreSQL session-pooler URL. Never
commit or share this file. For local sign-in, register
`http://localhost:8501/oauth2callback` as an authorized Google redirect URI.

OCR for scanned PDFs requires Tesseract. On Streamlit Community Cloud, the
`packages.txt` file installs Tesseract during deployment. Locally on Windows,
install Tesseract and ensure `tesseract.exe` is available on `PATH`.

## Configure private sign-in and storage

1. Create a Google OAuth client. For local development, add
   `http://localhost:8501/oauth2callback` as a redirect URI.
2. Create a Supabase project and copy its **session pooler** PostgreSQL
   connection string from **Connect**. Use SSL; the app enables `sslmode=require`.
3. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and set
   the real credentials. Generate a unique, long `cookie_secret`.
4. For Streamlit Community Cloud, add the same settings to the app's Secrets
   panel. Change `redirect_uri` to
   `https://dasouvik-ai-study-assistant-app-ho0the.streamlit.app/oauth2callback`
   and register that exact URI in the Google OAuth client.
5. Keep the Supabase database URL and Google client secret only in the local
   secrets file or Streamlit Cloud Secrets. Never put them in Git, chat, or
   client-side code.

The app stops with a setup message if authentication or PostgreSQL settings are
missing. It does not fall back to shared SQLite on a deployed app. Google OAuth
consent-screen testing mode only permits configured test users; broader use may
require completing Google's verification steps.

Any Google account with the app URL can sign in; the app currently has no
invite-only allowlist or cross-account library sharing. The existing local
SQLite database is not imported into Supabase. If a database contains legacy
rows without an owner, migrations leave them unassigned and hidden; they are
never assigned to the first person who signs in.

## Deployment and mobile app status

Deploy `app.py` to Streamlit Community Cloud after the Google and Supabase
secrets are configured. The current live app remains the older shared version
until that deployment updates.

The old `pwa/` wrapper embeds Streamlit in an iframe. Streamlit authentication
is not supported in embedded apps, so do not deploy that wrapper for private
libraries. The PWA and Play Store packaging are deferred until the front end is
changed to an architecture that supports sign-in.
