# DocuBot Model Card

This model card is a short reflection on your DocuBot system. Fill it out after you have implemented retrieval and experimented with all three modes:

1. Naive LLM over full docs  
2. Retrieval only  
3. RAG (retrieval plus LLM)

Use clear, honest descriptions. It is fine if your system is imperfect.

---

## 1. System Overview

**What is DocuBot trying to do?**  
Describe the overall goal in 2 to 3 sentences.

> DocuBot is a retrieval-augmented generation (RAG) system that answers developer questions using project documentation. It balances three modes: naive LLM generation, retrieval-only snippets, and RAG (combining retrieval with LLM reasoning). The goal is to provide accurate, grounded answers that cite the actual documentation rather than inventing information.

**What inputs does DocuBot take?**  
For example: user question, docs in folder, environment variables.

> - **User query**: A natural language question (e.g., "Where is the auth token generated?")
> - **Documentation files**: .md and .txt files loaded from the `docs/` folder
> - **Environment variables**: `GEMINI_API_KEY` (for LLM features), configuration for database and auth
> - **Mode selection**: User chooses between naive, retrieval-only, or RAG mode

**What outputs does DocuBot produce?**

> - **Naive mode**: Full LLM response using the complete documentation corpus (no retrieval filtering)
> - **Retrieval-only mode**: Raw formatted snippets from the top-k (default 3) most relevant document chunks
> - **RAG mode**: LLM-generated answer grounded in the retrieved snippets, with references to source files

---

## 2. Retrieval Design

**How does your retrieval system work?**  
Describe your choices for indexing and scoring.

- How do you turn documents into an index?
  > Documents are split into **paragraph-level chunks** by splitting on double newlines (`\n\n`). This creates semantic boundaries that preserve related content. Each chunk is stored as a (filename, text) tuple. Chunks smaller than 50 characters are filtered out; single-newline fallback handles documents without blank line separation.

- How do you score relevance for a query?
  > **Word frequency matching**: Query is split into lowercase words. For each chunk, we count total occurrences of all query words in the chunk text. Example: query "database connection" scoring 5 means those two words appeared 5 times total (could be 3x "database" + 2x "connection").

- How do you choose top snippets?
  > After scoring all chunks, we sort by relevance score (descending) and return the top-k chunks (default k=3). A **guardrail** checks if the highest-scoring chunk meets a minimum relevance threshold (min_score=1) before answering.

**What tradeoffs did you make?**  
For example: speed vs precision, simplicity vs accuracy.

> - **Simplicity over sophistication**: Word counting is fast and transparent but misses semantic relationships (e.g., "database" and "DB" are treated as different)
> - **Paragraph-level chunks over full documents**: Reduces irrelevant context bloat but may split important related content
> - **Low threshold (min_score=1)** over high threshold: Allows LLM to see any matching content and decide, rather than blocking weak matches
> - **No TF-IDF/weighting**: All words treated equally; common words like "the" count same as specific keywords like "database"

---

## 3. Use of the LLM (Gemini)

**When does DocuBot call the LLM and when does it not?**  
Briefly describe how each mode behaves.

- **Naive LLM mode**: Always calls LLM with the full concatenated documentation. No retrieval filtering. LLM uses its training knowledge plus the docs.
- **Retrieval only mode**: Never calls LLM. Returns raw retrieved snippets formatted with file citations. Stops at retrieval guardrail if min_score not met.
- **RAG mode**: Calls retrieval first, checks guardrail (min_score >= 1), then passes top-k snippets to LLM with specific instructions to ground answers in those snippets only.

**What instructions do you give the LLM to keep it grounded?**  
Summarize the rules from your prompt. For example: only use snippets, say "I do not know" when needed, cite files.

> Key rules in the RAG prompt:
> - "Answer the question using ONLY the snippets provided below"
> - "The snippets are pre-filtered and relevant to the query"
> - "Do not invent functions, endpoints, or configuration values not explicitly mentioned"
> - "It's OK to give partial answers - developers find any relevant information helpful"
> - "If the snippets truly contain NO information relevant to the question, respond with: 'I do not know based on the docs I have.'"
> - "Reference which files the information comes from"
> - "Do not add information from your training data"

---

## 4. Experiments and Comparisons

Run the **same set of queries** in all three modes. Fill in the table with short notes.

You can reuse or adapt the queries from `dataset.py`.

| Query | Naive LLM: helpful or harmful? | Retrieval only: helpful or harmful? | RAG: helpful or harmful? | Notes |
|------|---------------------------------|--------------------------------------|---------------------------|-------|
| **Where is the auth token generated?** | Helpful but hallucinating: Long, confident answer about OAuth, JWT, OpenID Connect, IdP services. Sounds authoritative but none of this is in the docs. Docs only mention `AUTH_SECRET_KEY` and token signing. | Helpful but hard to parse: Raw snippets show token validation checklist and signing mechanism. Accurate but reader must connect pieces. | **Best**: Explicitly states docs don't specify WHERE generation happens, only HOW it's signed. Honest about gaps. |
| **How do I connect to the database?** | Harmful hallucination: Provides code examples in Python, Node.js, Java with connection patterns. Zero of this is in the docs. Would mislead a developer. | Partially helpful but fragmented: Mentions `DATABASE_URL` verification from SETUP.md but includes unrelated auth error codes. No actual setup instructions. | **Best**: Clearly states that docs mention `DATABASE_URL` as config but don't provide connection steps. Honest refusal. |
| **Which endpoint returns all users?** | Helpful-sounding hallucination: Confident answer about `GET /users` with pagination, filtering, sorting examples. None in actual docs. Plausible but ungrounded. | Helpful and accurate: Shows `get_all_users()` function from DATABASE.md. But doesn't clearly state which API endpoint calls it. Mixes relevant and unrelated snippets. | **Best**: Distinguishes between the database function and the API endpoint. Notes that function exists but endpoint isn't documented. Honest about partial knowledge. |

**What patterns did you notice?**  

- **When does naive LLM look impressive but untrustworthy?**  
  > Whenever the question asks about implementation details or patterns ("how do I connect", "what endpoint"). The LLM generates confident, well-structured answers with examples, but they're confabulated from training data, not the actual docs. Developers would follow bad guidance.

- **When is retrieval only clearly better?**  
  > When documentation is sparse or incomplete. Snippets show exactly what exists (a function name, a config variable) without inventing details. Users see the raw evidence and can judge confidence themselves.

- **When is RAG clearly better than both?**  
  > When the docs have partial information (DATABASE.md mentions `get_all_users()` but API_REFERENCE.md doesn't list the endpoint). RAG synthesizes across snippets, acknowledges gaps explicitly, and provides partial useful information rather than either inventing (naive) or returning confusing fragment lists (retrieval-only).

- **Cases where RAG still fails:**
  > When the required information genuinely isn't in the docs at all, RAG still spends token budget retrieving and processing irrelevant snippets. For "How do I connect to the database?" it retrieves auth snippets because they mention DATABASE_URL-adjacent concepts, wasting context on unrelated content.

---

## 5. Failure Cases and Guardrails

**Concrete Failure Cases Observed**

**Failure Case 1: Hallucination in Naive Mode** ("How do I connect to the database?")
- **Question**: "How do I connect to the database?"
- **What the system did**: Naive LLM returned a long, confident answer with code examples in Python, Node.js, and Java showing typical database connection patterns (URI format, auth parameters, connection pooling, etc.).
- **What actually happened**: None of these code examples exist in the docs. The LLM invented plausible-sounding guidance from its training data.
- **Why it's a failure**: A developer implementing this code would fail because it doesn't match the actual API. For infrastructure setup tasks, this is particularly dangerous—bad setup can cause security issues or data loss.
- **Should have happened**: Naive mode either (a) should not be used for such questions, or (b) should include a large warning that it's generating from training data, not docs.

**Failure Case 2: Snippet noise in Retrieval Mode** ("Which endpoint returns all users?")
- **Question**: "Which endpoint returns all users?"
- **What the system did**: Retrieved and displayed the `get_all_users()` database function from DATABASE.md, which was correct and relevant. However, the results also included unrelated HTTP error code snippets from API_REFERENCE.md (e.g., "401 Unauthorized", "403 Forbidden") because they contained keyword matches.
- **Why it's a failure**: Users see a mix of relevant (the function name) and irrelevant (error codes) information, making it harder to extract the answer. The user must mentally filter noise.
- **Root cause**: Word-frequency scoring is naive and context-blind. Both the function definition and unrelated error codes matched query keywords (likely "endpoint", "users", "error").
- **Should have happened**: The `retrieve()` method should have ranked the function definition much higher than error codes, possibly using semantic similarity or snippet quality scoring.

**When DocuBot Should Say "I do not know"**

1. **Zero relevant content found** (score = 0): No chunks in any document contain any word from the query. Example: "How do I interface with a blockchain?" when the docs are about a REST API with no blockchain references. Current behavior: `has_sufficient_evidence()` returns False, guardrail triggers refusal message.

2. **Question asks for information genuinely not in docs**: Example: "Where is the auth token generated?" The docs explain how tokens are signed (using `AUTH_SECRET_KEY`) but don't explain where they're initially created (during user signup? as part of OAuth? etc.). Current behavior: RAG mode retrieves relevant snippets about signing but explicitly states "The docs explain HOW tokens are signed, but not WHERE they're generated."

3. **Orthogonal question (docs are incomplete)**: Example: "How do I deploy this to Kubernetes?" when the docs only cover local setup and database configuration. Current behavior: Top-scored chunks are about database setup (weak match), guardrail may trigger if score < threshold. If score >= threshold, RAG returns partial answer acknowledging that deployment docs don't exist.

**Guardrails Implemented**

1. **`has_sufficient_evidence(query, min_score=1)` method**
   - Checks if the top-scoring chunk from `retrieve()` has a relevance score >= `min_score` threshold (default: 1, meaning at least one query word must match).
   - Returns a tuple: `(bool, int)` indicating sufficiency and the actual top score.
   - Used before answering in both `answer_retrieval_only()` and `answer_rag()` modes.
   - Behavior: If score < threshold, immediately return refusal message instead of attempting an answer.
   - **Example**: Query "blockchain interface" with 0 matching chunks → score = 0 → guardrail blocks answer.

2. **Paragraph-based chunking** (via `chunk_text()`)
   - Documents are split on double newlines (`\n\n`) creating semantic boundaries, rather than returning entire documents.
   - Chunks smaller than 50 characters are filtered out to avoid noise.
   - If no valid chunks found, falls back to single-newline splitting; if still empty, returns entire document as last resort.
   - **Why it helps**: Smaller, tightly-scoped chunks reduce the chance of irrelevant details appearing in results.
   - **Trade-off**: Paragraph boundaries can split context. A function signature might be separated from its description.

3. **Top-K limiting** (via `retrieve(query, top_k=3)`)
   - Returns only the 3 most relevant chunks, not all chunks.
   - Forces a hard limit on context fed to the LLM (RAG mode) or displayed to the user (retrieval-only mode).
   - **Why it helps**: Limits hallucination risk; the LLM sees fewer distracting snippets.
   - **Trade-off**: May miss relevant information if it scores outside the top-3.

4. **LLM Prompt Guidelines** (in `llm_client.answer_from_snippets()`)
   - **Rule 1**: *"Only use information from the provided snippets. Do not make up details."*
   - **Rule 2**: *"If the snippets don't answer the question, explicitly say what the docs are missing: 'The docs explain X but not Y.'"*
   - **Rule 3**: *"Reference the source file (e.g., 'From AUTH.md: ...') for each claim."*
   - **Why they help**: Rule 1 & 2 bias the LLM toward grounding and honest refusal. Rule 3 adds traceability.
   - **Limitation**: LLMs can violate these rules, especially under adversarial prompting. Guardrails are advisory, not absolute enforcement.

**Gaps in Current Guardrails**

- **Naive mode has no guardrails by design.** It demonstrates raw LLM behavior without retrieval filtering. This mode is intentionally permissive to highlight the contrast with safer modes. Users should understand naive mode may hallucinate.
- **Semantic drift is not prevented.** Auth error codes can appear in "user endpoint" results because word-frequency doesn't understand semantic context. A more sophisticated ranker (BM25, embeddings) would help.
- **LLM prompt rules are soft constraints.** LLMs generally follow them, but they can be overridden or ignored with adversarial inputs.

> _Your answer here._

---

## 6. Limitations and Future Improvements

**Current Limitations**

1. **Word-Frequency Scoring Ignores Semantics**  
   The `score_document()` method counts query word occurrences but doesn't understand meaning. A query about "fetch all users" might not match chunks about "retrieve all user records" or "pull user list" (semantically identical). Similarly, "delete user" won't match "remove user" unless both words appear. Impact: Relevant answers are missed, or irrelevant answers appear due to keyword overlap alone.

2. **Paragraph Boundaries Can Fragment Context**  
   Documents are split on double newlines (`\n\n`). Function signatures and their documentation are sometimes split across chunks. Impact: Retrieved snippets may be incomplete without their full context, confusing users.

3. **No Control Over Chunk Length or Quality**  
   A 50-character focused chunk and a 500-character verbose chunk are ranked equally if they have the same word-frequency score. Impact: Long, rambling chunks can displace short, specific ones if keywords overlap.

4. **No Multi-Turn Conversation Support**  
   Each query is independent. If a user asks "How do I set up auth?" and then "How do I test it?", DocuBot doesn't remember the first question. Impact: Users must be verbose in every query; can't refine or build on previous answers.

5. **Naive Mode Provides No Hallucination Warning**  
   Naive mode can generate plausible but false answers, and users might not realize they're not from the docs. Example: The system confidently invented database connection code. Impact: Developers using only naive mode could implement fabricated guidance.

6. **No Version Control or Staleness Detection**  
   If documentation is updated, the system has no way to detect or warn about staleness. Example: A 6-month-old docs snapshot could reference deprecated APIs. Impact: Answers could be outdated.

**Future Improvements**

1. **Semantic Ranking via Embeddings** (High Impact, Medium Effort)  
   Replace word-frequency with cosine similarity between query and chunk embeddings (e.g., OpenAI's text-embedding-3-small or open-source models). Benefit: "fetch all users" would correctly match "retrieve all user records". Cost: Embedding inference adds latency and API cost. Estimated effort: 2-3 hours.

2. **BM25 or TF-IDF Scoring** (High Impact, Low Effort)  
   Replace word-frequency with statistical ranking that weights rare, query-specific terms higher. Benefit: "auth token" won't match every document mentioning "token" or "auth" separately; documents with both terms rank higher. Cost: Minimal; pure text analysis. Estimated effort: 1 hour.

3. **Snippet Quality Scoring** (Medium Impact, Low Effort)  
   Score chunks by relevance AND length (prefer concise, specific chunks). Benefit: Reduces noise from long, verbose explanations that happen to mention query keywords. Estimated effort: 30 minutes.

4. **Multi-Turn Conversation Support** (Medium Impact, Medium Effort)  
   Maintain query history and pass recent queries as context to the LLM. Benefit: Users can refine or build on previous answers naturally. Cost: More tokens per request. Estimated effort: 2 hours.

5. **Semantically-Aware Chunking** (Medium Impact, High Effort)  
   Parse documents as syntax trees (Markdown structure, Python AST) to split at true semantic boundaries (functions, classes, sections). Benefit: Chunks are always complete units (entire function + docstring). Cost: Language-specific parsing. Estimated effort: 3-4 hours per language.

6. **User Feedback Loop** (Low Impact, Medium Effort)  
   Track helpful vs unhelpful answers and adjust ranking over time. Benefit: System adapts to user behavior. Cost: Logging, analytics, feedback UI. Estimated effort: 4-6 hours.

---

## 7. Responsible Use

**Where could this system cause real world harm if used carelessly?**

1. **Hallucinated Setup Code Leading to Security Misconfiguration**  
   Naive mode confidently generates database connection code, authentication flows, and environment setup guidance that sounds authoritative but isn't in the docs. A developer implementing this fabricated code could:
   - Use hardcoded credentials instead of environment variables (security leak).
   - Misconfigure database connection parameters, causing data loss or exposure.
   - Implement outdated authentication patterns that are later found to be insecure.
   - Example: System returned Python/Node.js/Java database connection examples—none in actual documentation.

2. **Incomplete or Partial Information Leading to Non-Functional Implementation**  
   RAG mode correctly retrieves doc snippets but the docs are incomplete. Example: "How do I set up the authentication system?" The docs explain how tokens are signed but not how users initially authenticate or exchange credentials. A developer following this partial guide builds a system that gets stuck at the authentication step.
   - **Harm**: Wasted development time, frustration, potential security bugs from attempting workarounds.
   - **Example**: Auth token generation location not documented; developer guesses and implements incorrectly.

3. **Developers Trusting Confident-Sounding Wrong Answers**  
   Retrieval-only and RAG modes can return plausible-sounding but irrelevant snippets (e.g., auth error codes appearing in "user endpoint" results due to keyword overlap). A developer might think "I found the answer" without realizing it's off-topic.
   - **Harm**: Implementing based on incorrect guidance; shipping non-functional features.
   - **Example**: Query "Which endpoint returns all users?" returns error codes for auth failures alongside the correct function name. Developer might assume those error codes are expected from the user endpoint.

4. **Reliance on Stale or Outdated Documentation**  
   If docs are regenerated monthly but a developer is using a 6-month-old snapshot, answers could reference deprecated APIs, removed parameters, or retired features.
   - **Harm**: Following guidance that no longer applies; integration failures after code review or during deployment.
   - **Example**: Docs previously mentioned MySQL but switched to PostgreSQL two months ago. Developer still sees MySQL guidance.

5. **Over-Confidence in Partial Information**  
   Guardrails prevent answering when there's zero evidence, but they can't distinguish between "we found something relevant" and "we found something barely related." A developer might trust a weak match and waste time pursuing a dead end.
   - **Example**: Query "How does the system scale?" retrieves a chunk mentioning "server" and "config". Developer spends days optimizing based on 3 sentences about unrelated configuration.

**Safety Guidelines for Developers Using DocuBot**

1. **Prefer RAG mode over Naive mode for critical questions.**  
   Naive mode uses training data and generates confident-sounding but potentially false answers. RAG mode grounds answers in actual documentation. Use RAG for infrastructure setup, security, API contracts. Use Naive only for exploratory questions where hallucination is understood and acceptable.

2. **Cross-check critical answers with retrieval-only mode.**  
   If an answer sounds important (database setup, authentication, deployment), ask the same question in retrieval-only mode to see the raw snippets. This lets you verify that the LLM's synthesis is grounded in actual docs, not inference.

3. **Always review the provided source citations and verify them manually.**  
   DocuBot returns snippets with file names (AUTH.md, DATABASE.md, etc.). For critical guidance, open those files directly and read the full context. Snippets are out-of-context; full context might clarify or contradict the answer.

4. **Treat partial or unclear answers as starting points, not gospel.**  
   If DocuBot says "The docs explain HOW tokens are signed but not WHERE they're generated", that's honest but incomplete. Use it as a signal to ask a human (team Slack, code owner, maintainer), not a final answer. Similarly, if RAG returns contradictory snippets, it means the docs themselves are ambiguous—seek clarification.

5. **Report documentation gaps and errors to the docs team.**  
   If DocuBot refuses to answer something you believe should be documented (e.g., "How do I deploy to Kubernetes?"), file an issue or comment in your docs repo. DocuBot's limitations reveal where documentation is weakest, which benefits the entire team.

---
