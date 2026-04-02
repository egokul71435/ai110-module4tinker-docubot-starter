"""
Test to trace exactly what answer_rag() does before calling the LLM
"""
from docubot import DocuBot

bot = DocuBot()

test_queries = [
    "Where is the auth token generated?",
    "Which endpoint returns all users?",
    "How do I connect to the database"
]

print("Testing RAG flow WITHOUT calling LLM:\n")

for query in test_queries:
    print("=" * 60)
    print(f"Query: {query}")
    
    # Simulate what answer_rag() does
    has_evidence, top_score = bot.has_sufficient_evidence(query, top_k=3, min_score=1)
    print(f"  has_sufficient_evidence: {has_evidence}, top_score: {top_score}")
    
    if has_evidence:
        snippets = bot.retrieve(query, top_k=3)
        print(f"  retrieve() returned: {len(snippets)} snippets")
        for i, (filename, text) in enumerate(snippets, 1):
            print(f"    Snippet {i}: {filename} ({len(text)} chars)")
            print(f"      Preview: {text[:60]}...")
        
        # This is what gets passed to llm_client.answer_from_snippets()
        print(f"\n  -> This would be passed to answer_from_snippets()")
        if not snippets:
            print(f"  -> PROBLEM: answer_from_snippets() would return fallback!")
        else:
            print(f"  -> OK: answer_from_snippets() would process {len(snippets)} snippets")
    else:
        print(f"  -> would return guardrail refusal")
    
    print()
