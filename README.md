# AI Study Assistant

A Streamlit web app for uploading PDF study notes and generating summaries,
quizzes, flashcards, and searchable library entries locally.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

OCR for scanned PDFs requires Tesseract. On Streamlit Community Cloud, the
`packages.txt` file installs Tesseract during deployment. Locally on Windows,
install Tesseract and ensure `tesseract.exe` is available on `PATH`.

## Deploy to Streamlit Community Cloud

1. Push this repository to GitHub.
2. Open https://share.streamlit.io.
3. Sign in with GitHub.
4. Select this repository and the `main` branch.
5. Set the main file path to `app.py`.
6. Deploy the app.

The app uses local SQLite storage. Streamlit Cloud storage can reset whenever
the app restarts or redeploys, and all users on a public deployment share the
same library. Do not upload private documents.

## Install on a phone

The `pwa/` directory contains a small installable web-app shell that opens the
Streamlit app. Deploy it as a separate static site on Netlify:

1. Sign in to Netlify with GitHub and import this repository.
2. Keep the build settings from `netlify.toml` (`pwa` is the publish directory;
   no build command is needed).
3. Open the assigned HTTPS `*.netlify.app` URL on Android in Chrome, then choose
   **Install app** or **Add to Home screen** from the browser menu.
4. On iPhone, open the URL in Safari, use **Share**, then **Add to Home Screen**.

The shell can show an offline message, but the study app and its documents still
require an internet connection.

## Google Play

The PWA can be installed from a browser without Play Store publication. To
publish it on Google Play, package the hosted PWA as an Android Trusted Web
Activity (for example with PWABuilder), then publish the signed package through
Google Play Console. The final package's signing-certificate fingerprint must
be added to `pwa/.well-known/assetlinks.json` and deployed at the PWA host's
root before the Android app can be verified. Do not create that file with a
placeholder fingerprint.

Play Store release also requires a Play Console developer account and store
materials such as a privacy policy. The wrapper does not add authentication or
per-user document storage; visitors still share the same Streamlit library.
