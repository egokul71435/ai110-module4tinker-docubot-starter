# DocuBot

DocuBot is a small documentation assistant that helps answer developer questions about a codebase.  
It can operate in three different modes:

1. **Naive LLM mode**  
   Sends the entire documentation corpus to a Gemini model and asks it to answer the question.

2. **Retrieval only mode**  
   Uses a simple indexing and scoring system to retrieve relevant snippets without calling an LLM.

3. **RAG mode (Retrieval Augmented Generation)**  
   Retrieves relevant snippets, then asks Gemini to answer using only those snippets.

The docs folder contains realistic developer documents (API reference, authentication notes, database notes), but these files are **just text**. They support retrieval experiments and do not require students to set up any backend systems.

---

## Setup

### 1. Install Python dependencies

    pip install -r requirements.txt

### 2. Configure environment variables

Copy the example file:

    cp .env.example .env

Then edit `.env` to include your Gemini API key:

    GEMINI_API_KEY=your_api_key_here

If you do not set a Gemini key, you can still run retrieval only mode.

---

## Running DocuBot

Start the program:

    python main.py

Choose a mode:

- **1**: Naive LLM (Gemini reads the full docs)  
- **2**: Retrieval only (no LLM)  
- **3**: RAG (retrieval + Gemini)

You can use built in sample queries or type your own.

---

## Running Retrieval Evaluation (optional)

    python evaluation.py

This prints simple retrieval hit rates for sample queries.

---

## Modifying the Project

You will primarily work in:

- `docubot.py`  
  Implement or improve the retrieval index, scoring, and snippet selection.

- `llm_client.py`  
  Adjust the prompts and behavior of LLM responses.

- `dataset.py`  
  Add or change sample queries for testing.

---

## Requirements

- Python 3.9+
- A Gemini API key for LLM features (only needed for modes 1 and 3)
- No database, no server setup, no external services besides LLM calls

---

## Testing

There is no unit test suite. Use these checks instead:

    python evaluation.py          # retrieval hit rates on sample queries (no API key needed)
    python main.py                # interactive; choose mode 2 for retrieval-only
    python generate_answers.py    # regenerates answers.json (needs GEMINI_API_KEY)

Retrieval hit rate in `evaluation.py` is 0.75 (was 0.62) after tokenization, light stemming and stop-word filtering in `docubot.py`; a few sample queries still miss. See `model_card.md` for analysis.

---

## Recent Maintenance Notes

- Added `.env.example` (the setup steps referenced it but it was missing).
- Removed stale `# new` markers and outdated `TODO` labels from `docubot.py`; no behavior change.
- `has_sufficient_evidence()` now slices to the top `top_k` chunks, matching `retrieve()`. The result is unchanged because the best score is always in the top window. See `model_card.md` Section 5.
- Improved retrieval in `docubot.py`: whole-word matching, punctuation/snake_case splitting, light stemming, stop words, and `retrieve()` now uses the index to pick candidate files.
