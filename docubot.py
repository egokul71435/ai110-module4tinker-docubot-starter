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
        TODO (Phase 1):
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

        # new
        
        for filename, text in documents:
            # Split text into words, lowercase them, and add to index
            tokens = text.lower().split()
            for token in tokens:
                # Remove common punctuation from the end of tokens
                token = token.rstrip('.,!?;:')
                if token:  # Skip empty tokens
                    if token not in index:
                        index[token] = []
                    # Add filename if not already in the list
                    if filename not in index[token]:
                        index[token].append(filename)
        return index

    # -----------------------------------------------------------
    # Scoring and Retrieval (Phase 1)
    # -----------------------------------------------------------

    def score_document(self, query, text):
        """
        TODO (Phase 1):
        Return a simple relevance score for how well the text matches the query.

        Suggested baseline:
        - Convert query into lowercase words
        - Count how many appear in the text
        - Return the count as the score
        """

        # new

        # Convert query to lowercase words
        query_words = query.lower().split()
        text_lower = text.lower()
        
        # Count how many query words appear in the text
        score = 0
        for word in query_words:
            # Count occurrences of the word in the text
            score += text_lower.count(word)
        
        return score

    def retrieve(self, query, top_k=3):
        """
        Retrieve top_k relevant chunks using scoring.
        Returns a list of (filename, chunk_text) sorted by relevance score.
        """
        # Score each chunk using the query
        scored_chunks = []
        for filename, chunk_text in self.chunks:
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
        
        # Check if the highest-scoring chunk meets the threshold
        top_score = scored_chunks[0][0]
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
