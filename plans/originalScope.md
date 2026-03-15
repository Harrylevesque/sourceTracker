# Research Assistant Project – Feature Mapping

## 1. Project Setup
**Purpose:** Define the scope and theme of a research project.

- **Sub-features:**
  - Project title
  - Project theme / topic embedding
  - Optional keywords
  - Project metadata (start date, creator, version)


---

## 2. Research Monitoring
**Purpose:** Automatically track pages and sources the user visits.

- **Sub-features:**
  - Browser monitoring / extension
  - Capture URL, title, timestamp
  - Optional snippet extraction
  - Automatic embedding generation
  - Similarity comparison with project theme


---

## 3. Semantic Filtering
**Purpose:** Only keep sources relevant to the project.

- **Sub-features:**
  - Compute similarity between source and project embedding
  - Threshold-based filtering
  - Optional keyword matching
  - Automatic discard of unrelated sources
  - Manual override option


---

## 4. Source Storage & Logging
**Purpose:** Store minimal but sufficient information about sources.

- **Sub-features:**
  - Metadata storage (URL, title, timestamp)
  - Short snippet storage
  - Vector embedding storage
  - Tagging for topics or concepts
  - Edit/remove options for incorrect info
  - Storage lightweight / purging raw content


---

## 5. Knowledge Map
**Purpose:** Visually map relationships between concepts.

- **Sub-features:**
  - Node creation for concepts/topics
  - Link nodes based on semantic similarity
  - Attach sources and snippets to nodes
  - Dynamic update as new research is added
  - Visualization interface (graph/tree)
  - Editable for corrections or additions


---

## 6. Session Logging
**Purpose:** Track research sessions for traceability.

- **Sub-features:**
  - Automatic log creation per session (.md or .txt)
  - Timestamp of session start/end
  - List of sources detected
  - Notes or manual entries
  - Topics discovered
  - Optional summary of session


---

## 7. Version Control (Git)
**Purpose:** Track changes in research, notes, and project progress.

- **Sub-features:**
  - Automatic Git commit per session
  - Commit message with date / session summary
  - Branching for experiments or different research paths
  - Easy rollback / history inspection
  - Optional remote push (GitHub, GitLab)


---

## 8. Citation Suggestions
**Purpose:** Recommend sources when writing.

- **Sub-features:**
  - Embedding generation for written text
  - Similarity search in stored sources
  - Suggest citations with confidence score
  - APA / MLA / custom citation formatting
  - Sidebar or editor plugin integration (Google Docs later)
  - Manual accept/reject option


---

## 9. Educational Chatbot
**Purpose:** Explain concepts from research without cheating.

- **Sub-features:**
  - Query parsing and embedding
  - Search knowledge base only (sources + snippets + notes)
  - RAG (Retrieval Augmented Generation) system
  - Provide explanations and source references
  - Source transparency (show which sources were used)
  - Reflection prompts instead of direct answers
  - Editable and controlled behavior


---

## 10. Research Replay & Timeline
**Purpose:** Review progression of research over time.

- **Sub-features:**
  - Timeline of sessions and commits
  - Node mapping in knowledge map for each session
  - Visual representation of idea evolution
  - Option to replay or filter by topic
  - Editable corrections for mistakes

---

## 11. Future Integration / Extensions
**Purpose:** Long-term goals and improvements.

- **Sub-features:**
  - Editor plugins (Google Docs sidebar)
  - Automatic real-time citation suggestions
  - Visual interactive knowledge map
  - AI-assisted explanations in writing
  - Multi-project support
  - Cloud sync (optional)

---