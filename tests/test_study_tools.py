import re
import unittest
from unittest.mock import patch

import pymupdf
from study_tools import (
    FlashcardSession,
    extract_pdf_text,
    find_matches,
    generate_flashcards,
    generate_quiz,
    summarize_text,
)


class StudyToolsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = (
            "Photosynthesis helps plants convert sunlight into chemical energy. "
            "Chlorophyll absorbs sunlight inside plant cells. "
            "Evaporation changes liquid water into vapor. "
            "Gravity attracts objects toward Earth. "
            "Condensation forms droplets when vapor cools."
        )

    def test_summary_selects_source_sentences(self) -> None:
        summary = summarize_text(
            "Photosynthesis notes\n\n" + self.text,
            max_sentences=2,
        )
        self.assertEqual(len(summary.splitlines()), 2)
        self.assertTrue(
            all(sentence in self.text for sentence in summary.splitlines())
        )

    def test_quiz_answers_come_from_blanked_source_terms(self) -> None:
        questions = generate_quiz(self.text, limit=3)
        self.assertEqual(len(questions), 3)
        for question in questions:
            self.assertIsNone(
                re.search(
                    rf"\b{re.escape(question['answer'])}\b",
                    question["prompt"],
                    re.IGNORECASE,
                )
            )
            self.assertIn(question["answer"], question["options"])

    def test_flashcards_include_source_context(self) -> None:
        cards = generate_flashcards(self.text, limit=3)
        self.assertEqual(len(cards), 3)
        self.assertTrue(all(card["context"] in self.text for card in cards))

    def test_flashcard_session_retries_missed_card_once(self) -> None:
        cards = generate_flashcards(self.text, limit=2)
        session = FlashcardSession(document_id=7, cards=cards)

        first_card = session.current_card
        self.assertIsNotNone(first_card)
        session.answer_current(got_it=False)
        self.assertEqual(session.progress, 0.5)

        session.answer_current(got_it=True)
        self.assertEqual(session.progress, 1.0)
        self.assertFalse(session.complete)
        self.assertEqual(session.current_card, first_card)

        session.answer_current(got_it=True)
        self.assertTrue(session.complete)
        self.assertEqual(len(session.mastered), 2)

    def test_search_returns_matching_context(self) -> None:
        matches = find_matches(self.text, "chlorophyll")
        self.assertEqual(len(matches), 1)
        self.assertIn("Chlorophyll", matches[0])

    def test_empty_text_has_no_generated_content(self) -> None:
        self.assertEqual(summarize_text(""), "")
        self.assertEqual(generate_flashcards(""), [])
        self.assertEqual(generate_quiz(""), [])
        self.assertEqual(find_matches("notes", "missing"), [])

    def test_numeric_limits_reject_invalid_types(self) -> None:
        with self.assertRaises(TypeError):
            summarize_text("One. Two.", max_sentences=1.5)
        with self.assertRaises(TypeError):
            generate_quiz(self.text, limit=True)
        with self.assertRaises(TypeError):
            find_matches(self.text, "photosynthesis", limit="3")

    def test_quiz_does_not_create_single_option_questions(self) -> None:
        questions = generate_quiz(
            "Photosynthesis converts light energy into chemical energy.",
            limit=5,
        )
        self.assertTrue(
            all(len(question["options"]) >= 2 for question in questions)
        )

    def test_extracts_selectable_pdf_text(self) -> None:
        document = pymupdf.open()
        page = document.new_page()
        page.insert_textbox(
            pymupdf.Rect(72, 72, 180, 160),
            "Selectable PDF text continues on a second visual line.",
            fontsize=9,
        )
        pdf_bytes = document.tobytes()
        document.close()

        extracted = extract_pdf_text(pdf_bytes)
        self.assertIn("Selectable PDF text continues on a second visual line.", extracted)
        self.assertEqual(len(extracted.splitlines()), 1)

    def test_quiz_ignores_headings_and_common_words(self) -> None:
        questions = generate_quiz(self.text, limit=5)
        self.assertTrue(questions)
        self.assertTrue(
            all(
                question["answer"] not in {"the", "how"}
                for question in questions
            )
        )
        self.assertTrue(
            all(question["prompt"].endswith((".", "!", "?")) for question in questions)
        )

    def test_quiz_keeps_multiword_terms_together(self) -> None:
        text = (
            "Carbon dioxide enters leaves through small pores called stomata. "
            "Chlorophyll absorbs sunlight while carbon dioxide levels affect photosynthesis."
        )
        questions = generate_quiz(text, limit=2)
        self.assertEqual(questions[0]["answer"], "carbon dioxide")
        self.assertGreater(len(questions[0]["options"]), 1)
        self.assertNotIn("carbon", questions[0]["options"])
        self.assertNotIn("dioxide", questions[0]["options"])

    def test_scanned_pages_report_missing_tesseract(self) -> None:
        document = pymupdf.open()
        document.new_page()
        pdf_bytes = document.tobytes()
        document.close()

        with patch("study_tools.shutil.which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "Tesseract OCR is not installed"):
                extract_pdf_text(pdf_bytes, run_ocr=True)


if __name__ == "__main__":
    unittest.main()
