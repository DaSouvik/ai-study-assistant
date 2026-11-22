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
