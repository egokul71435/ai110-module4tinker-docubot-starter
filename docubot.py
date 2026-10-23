"""
Core DocuBot class responsible for:
- Loading documents from the docs/ folder
- Building a simple retrieval index (Phase 1)
- Retrieving relevant snippets (Phase 1)
- Supporting retrieval only answers
- Supporting RAG answers when paired with Gemini (Phase 2)
"""

import os
import glob
import re

STOP_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "do", "does", "did",
    "i", "we", "you", "it", "of", "to", "in", "on", "for", "and", "or",
    "how", "what", "where", "which", "when", "why", "there", "any", "this", "that",
}


def stem(token):
    """Very light suffix stripping so 'generated' matches 'generate'."""
    for suffix in ("ing", "ed", "es", "e", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 4:
            return token[: -len(suffix)]
    return token


def tokenize(text):
    """Lowercase, split on non-alphanumerics (so snake_case splits), and stem."""
    return [stem(t) for t in re.findall(r"[a-z0-9]+", text.lower())]


def query_terms(query):
    """Tokenize a query and drop stop words."""
    return [t for t in tokenize(query) if t not in STOP_WORDS]


class DocuBot:
    def __init__(self, docs_folder="docs", llm_client=None):
        """
        docs_folder: directory containing project documentation files
        llm_client: optional Gemini client for LLM based answers
        """
        self.docs_folder = docs_folder
        self.llm_client = llm_client

        # Load documents into memory
        self.documents = self.load_documents()  # List of (filename, text)

        # Build chunks for better retrieval (split documents into paragraphs)
        self.chunks = self.build_chunks(self.documents)

        # Build a retrieval index (implemented in Phase 1)
        self.index = self.build_index(self.documents)

    # -----------------------------------------------------------
    # Document Loading
    # -----------------------------------------------------------

    def load_documents(self):
        """
        Loads all .md and .txt files inside docs_folder.
        Returns a list of tuples: (filename, text)
        """
        docs = []
        pattern = os.path.join(self.docs_folder, "*.*")
        for path in glob.glob(pattern):
            if path.endswith(".md") or path.endswith(".txt"):
                with open(path, "r", encoding="utf8") as f:
                    text = f.read()
                filename = os.path.basename(path)
                docs.append((filename, text))
        return docs

    def chunk_text(self, text, min_length=50):
        """
        Split text into paragraphs (chunks separated by double newlines).
        Useful for granular retrieval.
        Returns a list of non-empty text chunks.
        """
        # Split by double newlines (blank lines)
        paragraphs = text.split("\n\n")

        # Filter out empty or very short chunks
        chunks = [p.strip() for p in paragraphs if p.strip() and len(p.strip()) >= min_length]

        # If no chunks after filtering, fall back to splitting by single newlines
        if not chunks:
            chunks = [p.strip() for p in text.split("\n") if p.strip() and len(p.strip()) >= min_length]

        # If still no chunks, return the whole text as one chunk
        if not chunks:
            chunks = [text.strip()]

        return chunks

    def build_chunks(self, documents):
        """
        Convert documents into smaller chunks for retrieval.
        Returns a list of tuples: (filename, chunk_text)
        """
        all_chunks = []
        for filename, text in documents:
            chunks = self.chunk_text(text)
            for chunk in chunks:
                all_chunks.append((filename, chunk))
        return all_chunks

    # -----------------------------------------------------------
    # Index Construction (Phase 1)
    # -----------------------------------------------------------

    def build_index(self, documents):
        """
        Build a tiny inverted index mapping lowercase words to the documents
        they appear in.

        Example structure:
        {
            "token": ["AUTH.md", "API_REFERENCE.md"],
            "database": ["DATABASE.md"]
        }

        Keep this simple: split on whitespace, lowercase tokens,
        ignore punctuation if needed.
        """
        index = {}

        for filename, text in documents:
            # Split text into words, lowercase them, and add to index
            for token in tokenize(text):
                files = index.setdefault(token, [])
                if filename not in files:
                    files.append(filename)
        return index

    # -----------------------------------------------------------
    # Scoring and Retrieval (Phase 1)
    # -----------------------------------------------------------

    def score_document(self, query, text):
        """
        Return a simple relevance score for how well the text matches the query.

        Suggested baseline:
        - Convert query into lowercase words
        - Count how many appear in the text
        - Return the count as the score
        """

        # Count whole-word matches of each (non-stop-word) query term
        counts = {}
        for token in tokenize(text):
            counts[token] = counts.get(token, 0) + 1

        score = sum(counts.get(word, 0) for word in query_terms(query))

        return score

    def retrieve(self, query, top_k=3):
        """
        Use the index and scoring function to select top_k relevant document snippets.

        Return a list of (filename, text) sorted by score descending.
        """

        # Score each chunk using the query
        # Only consider files the index says contain at least one query term
        candidate_files = set()
        for term in query_terms(query):
            candidate_files.update(self.index.get(term, []))

        scored_chunks = []
        for filename, chunk_text in self.chunks:
            if filename not in candidate_files:
                continue
            score = self.score_document(query, chunk_text)
            # Only include chunks with non-zero score
            if score > 0:
                scored_chunks.append((score, filename, chunk_text))

        # Sort by score in descending order
        scored_chunks.sort(key=lambda x: x[0], reverse=True)

        # Return top-k chunks as (filename, text) tuples
        results = [(filename, chunk_text) for score, filename, chunk_text in scored_chunks]
        return results[:top_k]

    def has_sufficient_evidence(self, query, top_k=3, min_score=1):
        """
        Guardrail: Check if retrieved results contain meaningful evidence.

        A score below min_score indicates no relevant match at all.
        This prevents answering with completely unrelated context.

        Args:
            query: User query string
            top_k: Number of chunks to consider
            min_score: Minimum relevance score required (default=1)
                     A score of 1 means at least one query word matched,
                     indicating some relevance to the question.

        Returns:
            (bool, int): (has_sufficient_evidence, top_chunk_score)
        """
        scored_chunks = []
        for filename, chunk_text in self.chunks:
            score = self.score_document(query, chunk_text)
            if score > 0:
                scored_chunks.append((score, filename, chunk_text))

        # If no chunks scored, we have no evidence
        if not scored_chunks:
            return False, 0

        # Sort by score to get the highest-scoring chunk
        scored_chunks.sort(key=lambda x: x[0], reverse=True)

        # Only consider the top_k chunks, matching what retrieve() returns
        top_chunks = scored_chunks[:top_k]
        if not top_chunks:
            return False, 0

        # Check if the highest-scoring chunk meets the threshold
        top_score = top_chunks[0][0]
        has_evidence = top_score >= min_score

        return has_evidence, top_score

    # -----------------------------------------------------------
    # Answering Modes
    # -----------------------------------------------------------

    def answer_retrieval_only(self, query, top_k=3, min_score=1):
        """
        Phase 1 retrieval only mode.
        Returns raw snippets and filenames with no LLM involved.

        Includes guardrail: refuses to answer if no relevant docs found.
        """
        # Check for sufficient evidence before answering
        has_evidence, top_score = self.has_sufficient_evidence(query, top_k=top_k, min_score=min_score)

        if not has_evidence:
            return "I don't have relevant information in the documentation to answer this question."

        snippets = self.retrieve(query, top_k=top_k)

        formatted = []
        for filename, text in snippets:
            formatted.append(f"[{filename}]\n{text}\n")

        return "\n---\n".join(formatted)

    def answer_rag(self, query, top_k=3, min_score=1):
        """
        Phase 2 RAG mode.
        Uses student retrieval to select snippets, then asks Gemini
        to generate an answer using only those snippets.

        Includes guardrail: refuses to answer if no relevant docs found.
        """
        if self.llm_client is None:
            raise RuntimeError(
                "RAG mode requires an LLM client. Provide a GeminiClient instance."
            )

        # Check for sufficient evidence before asking LLM
        has_evidence, top_score = self.has_sufficient_evidence(query, top_k=top_k, min_score=min_score)

        if not has_evidence:
            return "I don't have relevant information in the documentation to answer this question."

        snippets = self.retrieve(query, top_k=top_k)
        return self.llm_client.answer_from_snippets(query, snippets)

    # -----------------------------------------------------------
    # Bonus Helper: concatenated docs for naive generation mode
    # -----------------------------------------------------------

    def full_corpus_text(self):
        """
        Returns all documents concatenated into a single string.
        This is used in Phase 0 for naive 'generation only' baselines.
        """
        return "\n\n".join(text for _, text in self.documents)