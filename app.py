import hashlib

import streamlit as st

from local_assistant import (
    MAX_CONTEXT_CHARS,
    MAX_QUESTION_CHARS,
    MODEL_ID,
    LocalModelError,
    LocalModelNotFoundError,
    LocalModelUnavailableError,
    stream_local_response,
)
from database.db import (
    delete_document,
    find_library_matches,
    get_document,
    get_documents,
    initialize_database,
    save_document,
)
from study_tools import (
    FlashcardSession,
    extract_pdf_text,
    find_matches,
    generate_flashcards,
    generate_quiz,
    summarize_text,
)


def _navigate_to(page_name: str) -> None:
    st.session_state["navigation"] = page_name


def _open_study_document(document_id: int) -> None:
    st.session_state["study-document-select"] = document_id
    _navigate_to("Study tools")


st.set_page_config(
    page_title="Study Desk",
    page_icon="📚",
    layout="wide",
)

st.markdown(
    """
    <style>
    :root {
        --ink: #1d2b40;
        --muted-ink: #5b6675;
        --paper: #f4f1e9;
        --card: #fffdf8;
        --line: #ded9ce;
        --navy: #1c3150;
        --blue: #365b83;
        --gold: #b9853f;
    }

    .stApp {
        background: var(--paper);
        color: var(--ink);
        font-family: "Segoe UI", sans-serif;
    }
    .block-container { max-width: 1180px; padding-top: 2.4rem; }
    h1, h2, h3, h4 {
        color: var(--ink);
        font-family: Georgia, "Times New Roman", serif;
        letter-spacing: -0.025em;
    }
    h1 { font-size: 2.35rem; }
    [data-testid="stCaptionContainer"] { color: var(--muted-ink); }

    [data-testid="stSidebar"] {
        background: var(--navy);
        border-right: 1px solid #31445f;
    }
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] [data-testid="stMetricLabel"],
    [data-testid="stSidebar"] [data-testid="stMetricValue"] {
        color: #f4f1e9;
    }
    [data-testid="stSidebar"] [data-testid="stMetric"] {
        background: #263b5b;
        border-color: #43536b;
        box-shadow: none;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] label {
        border-radius: 6px;
    }
    [data-testid="stSidebar"] hr { border-color: #43536b; }

    [data-testid="stMetric"] {
        background: var(--card);
        border: 1px solid var(--line);
        border-top: 3px solid var(--gold);
        padding: 1rem 1.15rem;
        border-radius: 5px;
        box-shadow: 0 3px 12px rgba(29, 43, 64, 0.04);
    }
    [data-testid="stVerticalBlockBorderWrapper"] {
        border-color: var(--line);
        border-radius: 6px;
        background: rgba(255, 253, 248, 0.7);
    }
    .stButton > button {
        border-radius: 6px;
        font-weight: 600;
        transition: background-color 140ms ease, border-color 140ms ease;
    }
    .stButton > button[kind="primary"] {
        background: var(--navy);
        border-color: var(--navy);
    }
    .stButton > button[kind="primary"]:hover {
        background: var(--blue);
        border-color: var(--blue);
    }
    [data-testid="stTabs"] button[aria-selected="true"] {
        color: var(--navy);
        border-bottom-color: var(--gold);
    }
    [data-testid="stTextInput"] input,
    [data-testid="stTextArea"] textarea,
    [data-testid="stSelectbox"] [role="combobox"] {
        background: var(--card);
        border-color: var(--line);
    }

    @media (max-width: 640px) {
        .block-container {
            padding: 1.25rem 1rem 2rem;
        }
        h1 { font-size: 1.9rem; }
        h2 { font-size: 1.55rem; }
        [data-testid="stMetric"] {
            padding: 0.8rem;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

initialize_database()
documents = get_documents()

with st.sidebar:
    st.title("📚 Study Desk")
    st.caption("A quiet place to turn notes into practice.")
    page = st.radio(
        "Workspace",
        [
            "Overview",
            "Upload notes",
            "My library",
            "Study tools",
            "AI assistant",
        ],
        label_visibility="collapsed",
        key="navigation",
    )
    st.divider()
    st.metric("Saved documents", len(documents))
    st.caption(
        "No accounts are configured. On a shared deployment, everyone can "
        "access the same library. Don't upload private documents. Hosted "
        "SQLite data can reset during redeploys."
    )

st.title("📚 Study Desk")
st.caption(
    "Search, review, and practise from your own PDFs. Local tools need no AI "
    "API key; Ollama chat works only when this app runs beside Ollama."
)

if page == "Overview":
    total_characters = sum(
        int(document["char_count"] or 0) for document in documents
    )
    st.markdown("## Your next study session starts here")
    st.write(
        "Pick up where you left off, or add a new set of notes to your library."
    )
    primary_action, secondary_action = st.columns([1, 1])
    with primary_action:
        st.button(
            "＋ Upload study notes",
            type="primary",
            width="stretch",
            on_click=_navigate_to,
            args=("Upload notes",),
        )
    with secondary_action:
        st.button(
            "✦ Explore study tools",
            width="stretch",
            disabled=not documents,
            on_click=_navigate_to,
            args=("Study tools",),
        )

    st.markdown("")
    metric_columns = st.columns(3)
    metric_columns[0].metric("📚 Study documents", len(documents))
    metric_columns[1].metric("✍️ Characters in notes", f"{total_characters:,}")
    metric_columns[2].metric(
        "🗂️ Latest addition",
        "Ready to study" if documents else "Add your first PDF",
    )

    if documents:
        st.subheader("Pick up your learning")
        for start in range(0, min(len(documents), 6), 3):
            row = documents[start : start + 3]
            columns = st.columns(3)
            for column, document in zip(columns, row):
                with column:
                    with st.container(border=True):
                        st.markdown("#### 📄")
                        st.markdown(f"**{document['filename']}**")
                        st.caption(
                            f"Added {document['created_at']} · "
                            f"{int(document['char_count'] or 0):,} characters"
                        )
                        if document["summary"]:
                            st.write(
                                str(document["summary"]).splitlines()[0][:150]
                            )
                        st.button(
                            "Study this document",
                            key=f"dashboard-study-{document['id']}",
                            width="stretch",
                            on_click=_open_study_document,
                            args=(int(document["id"]),),
                        )
    else:
        empty_left, empty_right = st.columns([1.2, 1])
        with empty_left:
            st.info(
                "Upload your first PDF to create a library, search your notes, "
                "and practise with quizzes and flashcards."
            )
        with empty_right:
            st.markdown(
                """
                **Your study space includes**
                - Searchable notes library
                - Quick summaries and quizzes
                - Interactive flashcard practice
                - Optional local-only Ollama chat
                """
            )

    with st.expander("About the study tools"):
        st.markdown(
            """
            Summaries and practice questions are generated from your document
            text using local rules; they are not AI-generated. Flashcards show
            terms from your notes and reveal their source context, rather than
            generating definitions. Use AI assistant for local Ollama chat.
            """
        )
        st.warning(
            "No sign-in or per-user access is configured. Anyone who can open "
            "a shared deployment can browse its library."
        )

elif page == "Upload notes":
    st.subheader("Add a PDF to your library")
    st.write("Upload a PDF with selectable text. Scanned PDFs can use OCR.")
    uploaded_file = st.file_uploader(
        "Choose a PDF file",
        type=["pdf"],
        help="Maximum file size: 20 MB.",
        key="pdf_upload",
    )
    try_ocr = st.checkbox(
        "Try OCR if the PDF has no selectable text",
        help=(
            "OCR requires Tesseract. Streamlit Cloud installs it from "
            "packages.txt; install Tesseract locally to use OCR on Windows."
        ),
    )

    upload_bytes = uploaded_file.getvalue() if uploaded_file else None
    upload_digest = (
        hashlib.sha256(upload_bytes).hexdigest() if upload_bytes is not None else None
    )
    if (
        st.session_state.get("upload_draft")
        and st.session_state["upload_draft"]["digest"] != upload_digest
    ):
        st.session_state["upload_draft"] = None

    if st.button(
        "Extract text",
        type="primary",
        disabled=uploaded_file is None,
    ):
        if upload_bytes is None:
            st.error("Choose a PDF file before extracting text.")
        elif len(upload_bytes) > 20 * 1024 * 1024:
            st.error("This PDF is larger than 20 MB. Choose a smaller file.")
        else:
            try:
                extracted_text = extract_pdf_text(upload_bytes, run_ocr=try_ocr)
                if extracted_text.strip():
                    st.session_state["upload_draft"] = {
                        "digest": upload_digest,
                        "filename": uploaded_file.name,
                        "text": extracted_text,
                    }
                    st.success("Text extracted. Review it, then save it to your library.")
                else:
                    st.warning(
                        "No selectable text was found. If this is a scanned PDF, "
                        "enable OCR and try again."
                    )
            except Exception as exc:
                st.error(f"Could not process this PDF: {exc}")

    draft = st.session_state.get("upload_draft")
    if draft:
        st.markdown(f"#### Preview: {draft['filename']}")
        st.text_area(
            "Extracted text",
            value=draft["text"],
            height=260,
            disabled=True,
            key=f"extracted-preview-{draft['digest']}",
        )
        if st.button("Save to library", type="primary"):
            try:
                summary = summarize_text(draft["text"])
                save_document(
                    filename=draft["filename"],
                    content=draft["text"],
                    summary=summary,
                )
            except Exception as exc:
                st.error(f"Could not save the document: {exc}")
            else:
                st.session_state["upload_draft"] = None
                st.success(f"Saved {draft['filename']} to your library.")
                st.rerun()

elif page == "My library":
    st.subheader("Your saved notes")
    if not documents:
        st.info("No documents saved yet. Upload a PDF to build your library.")
    else:
        query = st.text_input(
            "Search across saved notes",
            placeholder="Type a word or phrase",
        )
        if query.strip():
            matches = find_library_matches(query.strip())
            st.markdown(f"**{len(matches)} matching document(s)**")
            for match in matches:
                snippets = find_matches(match["content"], query.strip(), limit=3)
                with st.expander(match["filename"]):
                    for snippet in snippets:
                        st.markdown(f"> {snippet}")
        else:
            st.caption("Search checks the text extracted from every saved PDF.")

        labels = {
            document["id"]: (
                f"{document['filename']} · {document['created_at']}"
            )
            for document in documents
        }
        selected_id = st.selectbox(
            "Open a document",
            options=list(labels),
            format_func=labels.get,
        )
        selected_document = get_document(selected_id)
        if selected_document:
            st.markdown(f"### {selected_document['filename']}")
            st.caption(f"Added {selected_document['created_at']}")
            if selected_document["summary"]:
                st.markdown("**Quick summary**")
                st.write(selected_document["summary"])
            st.download_button(
                "Download extracted text",
                data=selected_document["content"],
                file_name=f"{selected_document['filename']}.txt",
                mime="text/plain",
            )
            with st.expander("Read extracted text"):
                st.text_area(
                    "Document text",
                    value=selected_document["content"],
                    height=320,
                    disabled=True,
                    key=f"library-document-{selected_id}",
                )
            confirm_delete = st.checkbox(
                "I understand this permanently deletes the saved document",
                key=f"confirm-delete-{selected_id}",
            )
            if st.button(
                "Delete document",
                disabled=not confirm_delete,
                key=f"delete-document-{selected_id}",
            ):
                try:
                    delete_document(selected_id)
                except Exception as exc:
                    st.error(f"Could not delete the document: {exc}")
                else:
                    st.success("Document deleted.")
                    st.rerun()

elif page == "Study tools":
    st.subheader("Practise with your notes")
    if not documents:
        st.info("Upload and save a PDF first to use the study tools.")
    else:
        labels = {
            document["id"]: document["filename"] for document in documents
        }
        selected_id = st.selectbox(
            "Choose study material",
            options=list(labels),
            format_func=labels.get,
            key="study-document-select",
        )
        selected_document = get_document(selected_id)

        if selected_document:
            summary_tab, quiz_tab, cards_tab = st.tabs(
                ["Quick summary", "Quiz", "Flashcards"]
            )
            with summary_tab:
                sentence_count = st.slider(
                    "Summary length",
                    min_value=2,
                    max_value=6,
                    value=3,
                    key=f"summary-length-{selected_id}",
                )
                summary = summarize_text(
                    selected_document["content"],
                    max_sentences=sentence_count,
                )
                if summary:
                    for sentence in summary.splitlines():
                        st.markdown(f"- {sentence}")
                else:
                    st.warning("There isn't enough text to create a summary.")
                st.caption(
                    "This is an extractive summary: it selects important "
                    "sentences from the source rather than writing new ones."
                )

            with quiz_tab:
                questions = generate_quiz(selected_document["content"])
                if not questions:
                    st.warning(
                        "There isn't enough sentence-based text to make a quiz."
                    )
                else:
                    result_key = f"quiz-result-{selected_id}"
                    with st.form(f"quiz-form-{selected_id}"):
                        for index, question in enumerate(questions):
                            st.radio(
                                f"{index + 1}. {question['prompt']}",
                                options=["Choose an answer...", *question["options"]],
                                key=f"quiz-answer-{selected_id}-{index}",
                            )
                        submitted = st.form_submit_button("Check answers")

                    if submitted:
                        answers = [
                            st.session_state.get(
                                f"quiz-answer-{selected_id}-{index}",
                                "Choose an answer...",
                            )
                            for index in range(len(questions))
                        ]
                        correct = sum(
                            answer == question["answer"]
                            for answer, question in zip(answers, questions)
                        )
                        st.session_state[result_key] = (correct, len(questions))

                    if result_key in st.session_state:
                        correct, total = st.session_state[result_key]
                        st.success(f"Your score: {correct} / {total}")
                        with st.expander("Review answers"):
                            for index, question in enumerate(questions):
                                st.markdown(
                                    f"{index + 1}. **{question['answer']}** — "
                                    f"{question['prompt']}"
                                )

            with cards_tab:
                cards = generate_flashcards(selected_document["content"])
                if not cards:
                    st.warning(
                        "There isn't enough text to create vocabulary flashcards."
                    )
                else:
                    session = st.session_state.get("flashcard-session")
                    if (
                        not isinstance(session, FlashcardSession)
                        or session.document_id != selected_id
                        or session.cards != cards
                    ):
                        session = FlashcardSession(selected_id, cards)
                        st.session_state["flashcard-session"] = session

                    st.caption(
                        "Recall the idea from the term, then reveal a sentence "
                        "from your notes. These cards don't generate definitions."
                    )

                    if session.complete:
                        st.success(
                            f"Session complete — you marked "
                            f"{len(session.mastered)} of {len(session.cards)} "
                            "cards as known."
                        )
                        if session.retry_queued:
                            st.caption(
                                f"{len(session.retry_queued)} card(s) were added "
                                "to a second pass."
                            )
                        if st.button(
                            "Practise again",
                            type="primary",
                            key=f"restart-cards-{selected_id}",
                        ):
                            st.session_state["flashcard-session"] = (
                                FlashcardSession(selected_id, cards)
                            )
                            st.rerun()
                    else:
                        st.progress(session.progress)
                        st.caption(
                            f"Card {min(len(session.seen) + 1, len(cards))} "
                            f"of {len(cards)} · "
                            f"{len(session.mastered)} marked as known"
                        )
                        card = session.current_card
                        if card is None:
                            st.error("Could not load the current flashcard.")
                        else:
                            with st.container(border=True):
                                st.caption("TERM")
                                st.markdown(f"## {card['term'].title()}")
                                st.write(
                                    "Try to recall what this means in the context "
                                    "of your notes."
                                )
                                reveal = st.toggle(
                                    "Reveal source sentence",
                                    key=(
                                        f"reveal-card-{selected_id}-"
                                        f"{session.cursor}"
                                    ),
                                )
                                if reveal:
                                    st.info(card["context"])

                            again_column, got_it_column = st.columns(2)
                            with again_column:
                                if st.button(
                                    "↻ Again",
                                    key=f"again-card-{selected_id}",
                                    width="stretch",
                                ):
                                    session.answer_current(got_it=False)
                                    st.rerun()
                            with got_it_column:
                                if st.button(
                                    "✓ Got it",
                                    type="primary",
                                    key=f"got-card-{selected_id}",
                                    width="stretch",
                                ):
                                    session.answer_current(got_it=True)
                                    st.rerun()

elif page == "AI assistant":
    st.subheader("Local AI study assistant")
    st.write(
        f"Ask questions, request explanations, or make a study plan with {MODEL_ID}."
    )
    st.info(
        "Ollama runs the model on the same computer as this app. There is no "
        "API key or provider usage bill."
    )
    st.warning(
        "This only works when Streamlit and Ollama run on the same computer. "
        "The public Streamlit Cloud app cannot access Ollama on your PC."
    )
    st.markdown("[Install Ollama for Windows](https://ollama.com/download/windows)")
    st.code("ollama pull gemma3:1b", language="powershell")

    document_labels = {
        int(document["id"]): str(document["filename"])
        for document in documents
    }
    selected_document_id = st.selectbox(
        "Study notes (optional)",
        options=[None, *document_labels],
        format_func=lambda document_id: (
            "No document"
            if document_id is None
            else document_labels[document_id]
        ),
        key="local-model-context-document",
    )
    selected_document = (
        get_document(selected_document_id)
        if selected_document_id is not None
        else None
    )
    include_notes = st.checkbox(
        "Include this document's text in local model requests",
        disabled=selected_document is None,
        key=f"local-model-include-notes-{selected_document_id}",
    )
    study_notes = None
    if include_notes and selected_document is not None:
        study_notes = str(selected_document["content"])
        st.caption(
            "The first "
            f"{MAX_CONTEXT_CHARS:,} characters will be sent to Ollama on "
            "this computer with each question."
        )

    chat_scope = (
        f"document-{selected_document_id}"
        if study_notes is not None
        else "general"
    )
    history_key = f"local-model-messages-{chat_scope}"
    if history_key not in st.session_state:
        st.session_state[history_key] = []
    messages = st.session_state[history_key]

    for message in messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = st.chat_input(
        "Ask the local study assistant",
        key=f"local-model-input-{chat_scope}",
    )
    if prompt:
        question = prompt.strip()
        if not question:
            st.warning("Enter a question before sending.")
        elif len(question) > MAX_QUESTION_CHARS:
            st.error(
                f"Keep questions under {MAX_QUESTION_CHARS:,} characters."
            )
        else:
            with st.chat_message("user"):
                st.markdown(question)
            try:
                with st.chat_message("assistant"):
                    answer = st.write_stream(
                        stream_local_response(
                            history=messages,
                            question=question,
                            study_notes=study_notes,
                        )
                    )
            except LocalModelNotFoundError:
                st.error(
                    f"Model {MODEL_ID} isn't downloaded. Run "
                    f"`ollama pull {MODEL_ID}` in PowerShell, then try again."
                )
            except LocalModelUnavailableError:
                st.error(
                    "Couldn't connect to Ollama. Start Ollama on the same "
                    "computer that runs Streamlit. The Streamlit Cloud "
                    "deployment can't reach Ollama on your PC."
                )
            except LocalModelError as exc:
                st.error(str(exc))
            else:
                messages.extend(
                    [
                        {"role": "user", "content": question},
                        {"role": "assistant", "content": answer},
                    ]
                )
                st.session_state[history_key] = messages[-16:]
