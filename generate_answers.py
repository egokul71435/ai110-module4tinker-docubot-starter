"""
Generate answers for all three modes and save as JSON.
Robust version with error handling.
"""
import json
from dotenv import load_dotenv
load_dotenv()

from docubot import DocuBot
from llm_client import GeminiClient

# Test queries
QUERIES = [
    "Where is the auth token generated?",
    "Which endpoint returns all users?",
    "How do I connect to the database?"
]

# Initialize DocuBot with LLM client
try:
    llm_client = GeminiClient()
    has_llm = True
    print("✓ LLM client initialized\n")
except RuntimeError as e:
    print(f"✗ LLM features disabled: {e}\n")
    llm_client = None
    has_llm = False

bot = DocuBot(llm_client=llm_client)

# Dictionary to store all answers
results = {
    "mode_1_naive_llm": {},
    "mode_2_retrieval_only": {},
    "mode_3_rag": {}
}

print("Generating answers...\n")

# Mode 1: Naive LLM (if available)
if has_llm:
    print("=" * 60)
    print("Mode 1: Naive LLM over full docs")
    print("=" * 60)
    all_text = bot.full_corpus_text()
    for query in QUERIES:
        try:
            print(f"  {query}...")
            answer = bot.llm_client.naive_answer_over_full_docs(query, all_text)
            results["mode_1_naive_llm"][query] = answer
            print(f"  ✓ Received answer\n")
        except Exception as e:
            print(f"  ✗ Error: {type(e).__name__}\n")
            results["mode_1_naive_llm"][query] = f"Error: {str(e)[:200]}"
else:
    print("Mode 1: Naive LLM - SKIPPED (no GEMINI_API_KEY)\n")
    for query in QUERIES:
        results["mode_1_naive_llm"][query] = "LLM not available"

# Mode 2: Retrieval Only
print("=" * 60)
print("Mode 2: Retrieval Only")
print("=" * 60)
for query in QUERIES:
    try:
        print(f"  {query}...")
        answer = bot.answer_retrieval_only(query)
        results["mode_2_retrieval_only"][query] = answer
        print(f"  ✓ Received answer\n")
    except Exception as e:
        print(f"  ✗ Error: {type(e).__name__}\n")
        results["mode_2_retrieval_only"][query] = f"Error: {str(e)[:200]}"

# Mode 3: RAG (if available)
if has_llm:
    print("=" * 60)
    print("Mode 3: RAG (Retrieval + LLM)")
    print("=" * 60)
    for query in QUERIES:
        try:
            print(f"  {query}...")
            answer = bot.answer_rag(query)
            results["mode_3_rag"][query] = answer
            print(f"  ✓ Received answer\n")
        except Exception as e:
            print(f"  ✗ Error: {type(e).__name__}\n")
            results["mode_3_rag"][query] = f"Error: {str(e)[:200]}"
else:
    print("Mode 3: RAG - SKIPPED (no GEMINI_API_KEY)\n")
    for query in QUERIES:
        results["mode_3_rag"][query] = "LLM not available"

# Save to JSON file
output_file = "answers.json"
try:
    with open(output_file, "w", encoding="utf8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("=" * 60)
    print(f"✓ Answers saved to {output_file}")
    print("=" * 60)
except Exception as e:
    print(f"✗ Error saving file: {e}")
