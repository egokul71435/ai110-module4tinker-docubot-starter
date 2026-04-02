"""
Gemini client wrapper used by DocuBot.

Handles:
- Configuring the Gemini client from the GEMINI_API_KEY environment variable
- Naive "generation only" answers over the full docs corpus (Phase 0)
- RAG style answers that use only retrieved snippets (Phase 2)

Experiment with:
- Prompt wording
- Refusal conditions
- How strictly the model is instructed to use only the provided context
"""

import os
import google.generativeai as genai

# Central place to update the model name if needed.
# You can swap this for a different Gemini model in the future.
GEMINI_MODEL_NAME = "gemini-2.5-flash"


class GeminiClient:
    """
    Simple wrapper around the Gemini model.

    Usage:
        client = GeminiClient()
        answer = client.naive_answer_over_full_docs(query, all_text)
        # or
        answer = client.answer_from_snippets(query, snippets)
    """

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Missing GEMINI_API_KEY environment variable. "
                "Set it in your shell or .env file to enable LLM features."
            )

        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(GEMINI_MODEL_NAME)

    # -----------------------------------------------------------
    # Phase 0: naive generation over full docs
    # -----------------------------------------------------------

    def naive_answer_over_full_docs(self, query, all_text):
        # We ignore all_text and send a generic prompt instead
        prompt = f"""
    You are a documentation assistant. 
    Answer this developer question: {query}
    """
        response = self.model.generate_content(prompt)
        return (response.text or "").strip()

    # -----------------------------------------------------------
    # Phase 2: RAG style generation over retrieved snippets
    # -----------------------------------------------------------

    def answer_from_snippets(self, query, snippets):
        """
        Phase 2:
        Generate an answer using only the retrieved snippets.

        snippets: list of (filename, text) tuples selected by DocuBot.retrieve

        The prompt:
        - Shows each snippet with its filename
        - Instructs the model to rely only on these snippets
        - Requires an explicit "I do not know" refusal when needed
        """

        if not snippets:
            return "I do not know based on the docs I have."

        context_blocks = []
        for filename, text in snippets:
            block = f"File: {filename}\n{text}\n"
            context_blocks.append(block)

        context = "\n\n".join(context_blocks)

        prompt = f"""
You are a helpful documentation assistant. A retrieval system has already found the most relevant snippets for the developer's question.

Your job:
- Answer the question using ONLY the snippets provided below.
- The snippets are pre-filtered and relevant to the query.
- Extract and explain information directly from these snippets.
- Reference which files the information comes from.
- Provide helpful answers even if the information is partial.

Snippets provided:
{context}

Developer question:
{query}

Rules:
- Use only the information in the snippets. Do not add information from your training data.
- Do not invent functions, endpoints, or configuration values not explicitly mentioned.
- If the snippets truly contain NO information relevant to the question, respond with:
  "I do not know based on the docs I have."
- Otherwise, provide a direct, helpful answer based on what's in the snippets.
- It's OK to give partial answers - developers find any relevant information helpful.
- Be specific about what the snippets do and do not say.
"""

        response = self.model.generate_content(prompt)
        return (response.text or "").strip()
