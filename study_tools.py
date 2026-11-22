from dataclasses import dataclass, field
import random
import re
import shutil
from collections import Counter

import pymupdf


@dataclass
class FlashcardSession:
    document_id: int
    cards: list[dict[str, str]]
    order: list[int] = field(init=False)
    cursor: int = 0
    seen: set[int] = field(default_factory=set)
    mastered: set[int] = field(default_factory=set)
    retry_queued: set[int] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.order = list(range(len(self.cards)))

    @property
    def complete(self) -> bool:
        return self.cursor >= len(self.order)

    @property
    def current_index(self) -> int | None:
        if self.complete:
            return None
        return self.order[self.cursor]

    @property
    def current_card(self) -> dict[str, str] | None:
        index = self.current_index
        return self.cards[index] if index is not None else None

    @property
    def progress(self) -> float:
        if not self.cards:
            return 1.0
        return len(self.seen) / len(self.cards)

    def answer_current(self, *, got_it: bool) -> None:
        index = self.current_index
        if index is None:
            raise RuntimeError("The flashcard session is already complete.")

        self.seen.add(index)
        if got_it:
            self.mastered.add(index)
        elif index not in self.retry_queued:
            self.retry_queued.add(index)
            self.order.append(index)
        self.cursor += 1


_WORD_PATTERN = re.compile(r"[A-Za-z][A-Za-z'-]{2,}")
_SENTENCE_PATTERN = re.compile(r"(?<=[.!?])\s+|\n+")
_STOP_WORDS = {
    "about", "above", "after", "again", "against", "all", "also", "am",
    "an", "and", "any", "are", "as", "at", "back", "because", "been",
    "before", "being", "below", "between", "both", "but", "by", "can",
    "cannot", "could", "did", "do", "does", "doing", "down", "during",
    "each", "either", "few", "for", "from", "further", "had", "has",
    "have", "having", "he", "her", "here", "hers", "herself", "him",
    "himself", "his", "how", "i", "if", "in", "into", "is", "it",
    "its", "itself", "just", "me", "more", "most", "must", "my",
    "myself", "no", "nor", "not", "now", "of", "off", "on", "once",
    "only", "or", "other", "our", "ours", "ourselves", "out", "over",
    "own", "same", "she", "should", "so", "some", "such", "than",
    "that", "the", "their", "theirs", "them", "themselves", "then",
    "there", "these", "they", "this", "those", "through", "to", "too",
    "under", "until", "up", "very", "was", "we", "were", "what",
    "when", "where", "which", "while", "who", "whom", "why", "will",
    "with", "would", "you", "your", "yours", "yourself", "yourselves",
    "especially", "mainly", "overall", "simplified",
}


def _positive_int(value: int, *, name: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer.")
    if value < 1:
        raise ValueError(f"{name} must be at least 1.")
    return value


def _normalize_page_text(page: pymupdf.Page, text_page: object = None) -> str:
    if text_page is None:
        blocks = page.get_text("blocks", sort=True)
    else:
        blocks = page.get_text("blocks", textpage=text_page, sort=True)
    block_texts = [
        " ".join(block[4].split())
        for block in blocks
        if len(block) > 4 and block[4].strip()
    ]
    return "\n\n".join(block_texts)


def extract_pdf_text(pdf_bytes: bytes, *, run_ocr: bool = False) -> str:
    """Extract selectable PDF text, optionally OCRing scanned pages."""
    if not isinstance(pdf_bytes, bytes):
        raise TypeError("pdf_bytes must be bytes.")
    if type(run_ocr) is not bool:
        raise TypeError("run_ocr must be a boolean.")
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as document:
        if document.page_count > 250:
            raise ValueError("This PDF has more than 250 pages.")

        page_text = [_normalize_page_text(page) for page in document]
        pages_needing_ocr = [
            index for index, text in enumerate(page_text) if not text.strip()
        ]
        if not run_ocr or not pages_needing_ocr:
            return "\n".join(page_text).strip()

        if not shutil.which("tesseract"):
            raise RuntimeError(
                "Tesseract OCR is not installed. Install Tesseract and restart "
                "the app, or turn off OCR to process PDFs with selectable text."
            )

        for index in pages_needing_ocr:
            page = document[index]
            text_page = page.get_textpage_ocr(language="eng", dpi=200, full=True)
            page_text[index] = _normalize_page_text(page, text_page=text_page)
        return "\n".join(page_text).strip()


def _sentences(text: str) -> list[str]:
    return [
        sentence.strip()
        for sentence in _SENTENCE_PATTERN.split(text.strip())
        if sentence.strip()
    ]


def _keywords(text: str) -> list[str]:
    return [
        word.casefold()
        for word in _WORD_PATTERN.findall(text)
        if word.casefold() not in _STOP_WORDS
    ]


def _study_terms(text: str) -> list[str]:
    words = [word.casefold() for word in _WORD_PATTERN.findall(text)]
    content_words = [word for word in words if word not in _STOP_WORDS]
    phrases = [
        f"{left} {right}"
        for left, right in zip(words, words[1:])
        if left not in _STOP_WORDS and right not in _STOP_WORDS
    ]
    return [*content_words, *phrases]


def _term_pattern(term: str) -> re.Pattern[str]:
    parts = term.split()
    pattern = r"\b" + r"\s+".join(re.escape(part) for part in parts) + r"\b"
    return re.compile(pattern, re.IGNORECASE)


def summarize_text(text: str, *, max_sentences: int = 3) -> str:
    """Return a short extractive summary ranked by informative word frequency."""
    if not isinstance(text, str):
        raise TypeError("text must be a string.")
    max_sentences = _positive_int(max_sentences, name="max_sentences")

    sentences = [
        sentence
        for sentence in _sentences(text)
        if re.search(r"[.!?][\"')\]]?$", sentence)
    ]
    if not sentences:
        return ""

    frequencies = Counter(_keywords(text))
    ranked = []
    for index, sentence in enumerate(sentences):
        words = _keywords(sentence)
        if not words:
            continue
        score = sum(frequencies[word] for word in set(words)) / len(words) ** 0.5
        ranked.append((score, index, sentence))

    if not ranked:
        return "\n".join(sentences[:max_sentences])

    selected = sorted(ranked, key=lambda item: (-item[0], item[1]))[:max_sentences]
    return "\n".join(sentence for _, _, sentence in sorted(selected, key=lambda item: item[1]))


def generate_flashcards(text: str, *, limit: int = 8) -> list[dict[str, str]]:
    """Build vocabulary cards from frequent terms and their source sentences."""
    if not isinstance(text, str):
        raise TypeError("text must be a string.")
    limit = _positive_int(limit, name="limit")

    sentences = [
        sentence
        for sentence in _sentences(text)
        if re.search(r"[.!?][\"')\]]?$", sentence)
        and len(_WORD_PATTERN.findall(sentence)) >= 5
    ]
    words = _study_terms(text)
    frequencies = Counter(words)
    sentence_for_term = {}
    for sentence in sentences:
        if len(_WORD_PATTERN.findall(sentence)) >= 5:
            for term in set(_study_terms(sentence)):
                sentence_for_term.setdefault(term, sentence)

    repeated_phrases = {
        term
        for term in sentence_for_term
        if " " in term and frequencies[term] >= 2
    }
    candidate_terms = sorted(
        (
            term
            for term in sentence_for_term
            if (
                " " in term and frequencies[term] >= 2
                or " " not in term
                and not any(
                    re.search(rf"\b{re.escape(term)}\b", phrase)
                    for phrase in repeated_phrases
                )
            )
        ),
        key=lambda word: (
            -frequencies[word],
            -(" " in word),
            -len(word),
            word,
        ),
    )

    cards = []
    for term in candidate_terms:
        cards.append({"term": term, "context": sentence_for_term[term]})
        if len(cards) >= limit:
            break
    return cards


def generate_quiz(text: str, *, limit: int = 5) -> list[dict[str, object]]:
    """Create fill-in-the-blank questions with answers grounded in the text."""
    if not isinstance(text, str):
        raise TypeError("text must be a string.")
    limit = _positive_int(limit, name="limit")

    sentences = [
        sentence
        for sentence in _sentences(text)
        if re.search(r"[.!?][\"')\]]?$", sentence)
        and len(_WORD_PATTERN.findall(sentence)) >= 6
    ]
    frequencies = Counter(_study_terms(text))
    repeated_phrases = {
        term
        for term, frequency in frequencies.items()
        if " " in term and frequency >= 2
    }
    candidate_terms = sorted(
        (
            term
            for term, frequency in frequencies.items()
            if len(term.replace(" ", "")) >= 5
            and (
                " " in term and frequency >= 2
                or " " not in term
                and not any(
                    re.search(rf"\b{re.escape(term)}\b", phrase)
                    for phrase in repeated_phrases
                )
            )
        ),
        key=lambda word: (
            -frequencies[word],
            -(" " in word),
            -len(word),
            word,
        ),
    )

    rng = random.Random(text)
    questions = []
    used_answers = set()
    for sentence in sentences:
        sentence_terms = [
            term for term in set(_study_terms(sentence))
            if term in candidate_terms
            and term not in used_answers
            and len(_term_pattern(term).findall(sentence)) == 1
        ]
        if not sentence_terms:
            continue
        term = max(
            sentence_terms,
            key=lambda word: (
                " " in word,
                len(word),
                frequencies[word],
                word,
            ),
        )
        term_pattern = _term_pattern(term)
        prompt = term_pattern.sub(
            "_____",
            sentence,
        )
        used_answers.add(term)
        options = [term]
        options.extend(
            other
            for other in candidate_terms
            if other != term
            and other not in sentence_terms
            and other not in used_answers
            and not set(other.split()) & set(term.split())
        )
        options = options[:4]
        if len(options) < 2:
            continue
        rng.shuffle(options)
        questions.append(
            {"prompt": prompt, "answer": term, "options": options}
        )
        if len(questions) >= limit:
            break
    return questions


def find_matches(text: str, query: str, *, limit: int = 5) -> list[str]:
    """Return short, readable context snippets for case-insensitive matches."""
    if not isinstance(text, str):
        raise TypeError("text must be a string.")
    if not isinstance(query, str):
        raise TypeError("query must be a string.")
    limit = _positive_int(limit, name="limit")
    if not query.strip():
        return []

    snippets = []
    for match in re.finditer(re.escape(query.strip()), text, re.IGNORECASE):
        start = max(0, match.start() - 90)
        end = min(len(text), match.end() + 180)
        snippet = " ".join(text[start:end].split())
        if start:
            snippet = f"…{snippet}"
        if end < len(text):
            snippet = f"{snippet}…"
        snippets.append(snippet)
        if len(snippets) >= limit:
            break
    return snippets
