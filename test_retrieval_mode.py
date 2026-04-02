"""
Test retrieval-only mode to verify retrieve() works in main.py context
"""
from docubot import DocuBot

bot = DocuBot()

test_queries = [
    "Where is the auth token generated?",
    "Which endpoint returns all users?",
    "How do I connect to the database"
]

for query in test_queries:
    print("=" * 60)
    print(f"Question: {query}\n")
    answer = bot.answer_retrieval_only(query)
    print("Answer:")
    print(answer)
    print()
