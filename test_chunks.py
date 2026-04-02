"""
Quick diagnostic script to verify chunks are being built and scoring works.
"""
from docubot import DocuBot

# Create bot without LLM
bot = DocuBot()

print(f"Documents loaded: {len(bot.documents)}")
print(f"Chunks built: {len(bot.chunks)}")
print()

if len(bot.chunks) == 0:
    print("ERROR: No chunks were built!")
else:
    print("Sample chunks:")
    for i, (filename, chunk) in enumerate(bot.chunks[:3]):
        print(f"\nChunk {i+1} from {filename}:")
        print(f"  Length: {len(chunk)} characters")
        print(f"  Preview: {chunk[:100]}...")
    print()

# Test queries
test_queries = [
    "Where is the auth token generated?",
    "Which endpoint returns all users?",
    "How do I connect to the database"
]

for query in test_queries:
    print(f"\nQuery: {query}")
    has_evidence, top_score = bot.has_sufficient_evidence(query, min_score=1)
    print(f"  Has evidence (min_score=1): {has_evidence}")
    print(f"  Top score: {top_score}")
    
    snippets = bot.retrieve(query, top_k=3)
    print(f"  Snippets retrieved: {len(snippets)}")
    if snippets:
        for filename, text in snippets:
            print(f"    - {filename}: {len(text)} chars")
