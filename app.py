import streamlit as st
import pymupdf

st.set_page_config(
    page_title="AI Study Assistant",
    page_icon="📚"
)

st.title("📚 AI Study Assistant")
st.write("Upload your study notes to get started.")

uploaded_file = st.file_uploader(
    "Upload a PDF file",
    type=["pdf"]
)

if uploaded_file:
    try:
        pdf_bytes = uploaded_file.getvalue()

        with pymupdf.open(
            stream=pdf_bytes,
            filetype="pdf"
        ) as document:
            text = "\n".join(
                page.get_text()
                for page in document
            )

        if text.strip():
            st.success("PDF processed successfully!")
            st.text_area(
                "Extracted study material",
                text,
                height=300
            )
        else:
            st.warning(
                "No selectable text found. "
                "This may be a scanned PDF."
            )

    except Exception:
        st.error(
            "Unable to read this PDF. "
            "Please try another file."
        )