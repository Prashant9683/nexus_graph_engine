# 🕸️ Nexus O2C: Graph-Based Query Engine

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=FastAPI&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=flat&logo=Streamlit&logoColor=white)
![Neo4j](https://img.shields.io/badge/Neo4j-018bff?style=flat&logo=neo4j&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-1C3C3C?style=flat)

**Nexus O2C** is an intelligent, graph-based data modeling and natural language query system designed to analyze SAP **Order-to-Cash (O2C)** workflows. 

Instead of writing complex SQL or Cypher, Nexus O2C allows you to intuitively ask questions in plain English—such as *"Which products are associated with the highest number of billing documents?"* or *"Trace the flow of outbound delivery 80738070."* The AI agent dynamically translates your questions into validated Neo4j Cypher queries, retrieves the exact relationships from the graph database, and returns the insights alongside a beautifully rendered interactive topology of the localized data.

---

## ✨ Key Features

- 🗣️ **Natural Language to Graph:** Powered by LangChain, the backend autonomously evaluates, routes, and translates natural language into precise Cypher queries against a strict SAP data schema.
- 🧠 **Conversational Memory:** The AI remembers previous context, seamlessly resolving pronouns like "this order" or "those products" for continuous, natural exploration.
- 🕸️ **Interactive Graph Visualization:** A dynamic PyVis topology map automatically renders the 1-hop neighborhood of the precise entities the LLM is discussing.
- 🛡️ **Enterprise-Grade Guardrails:** Built-in semantic routing rejects out-of-domain queries (e.g., general knowledge or prompt injection) before they ever hit the database.
- ⚡ **High Performance & Safe Executions:** Features threaded execution timeouts, consolidated LLM routing, and frontend graph-caching to deliver results safely and lightning-fast.

---

## 🏗️ Architecture & Engineering Decisions

### 1. System Architecture
The system is built on a decoupled, microservice-inspired architecture:
* **Backend (FastAPI):** Handles the LLM orchestration, prompt routing, and database connections. This ensures the database credentials and LLM API keys remain completely isolated from the client.
* **Frontend (Streamlit + PyVis):** Provides a lightweight, stateless chat interface. The graph visualization is dynamically rendered using HTML/JS injected via Streamlit components, reacting instantly to the semantic context of the LLM's text output.
* **Concurrency & Timeouts:** Graph database queries (especially variable-length path traversals) can suffer from combinatorial explosion. The backend wraps LangChain execution in a `ThreadPoolExecutor` with a strict 45-second timeout, ensuring the API never hangs the frontend indefinitely.

### 2. Database Choice: Why Neo4j over SQL?
While this O2C dataset could technically be stored in relational tables (PostgreSQL), **Neo4j** was chosen because supply chain analysis is fundamentally a network topology problem. 
* **Traversal Efficiency:** Tracing a document flow (e.g., `Sales Order` -> `Delivery` -> `Billing` -> `Journal Entry`) in SQL requires expensive, recursive `JOIN` operations. In Neo4j, relationships are first-class citizens (Index-Free Adjacency), allowing `MATCH path=(:SalesOrder)-[*1..4]-(:JournalEntry)` to execute in milliseconds.
* **Broken Flow Detection:** Identifying "Delivered but not billed" requires complex anti-joins in SQL. In Neo4j, this is natively handled via highly optimized topological checks: `WHERE NOT EXISTS { (node)-[]-(target) }`.
* *(Note: Database indexing was applied to all primary IDs like `order_id` and `product_id` to drop initial node-lookup latency from O(N) to O(1)).*

### 3. LLM Prompting Strategy
Translating natural language to Cypher reliably is notoriously brittle. The prompting strategy utilizes several "fail-safe" rules:
1.  **Undirected Paths:** The LLM is instructed to omit directional arrows (`()-[]-()`) to prevent false-negative empty returns caused by guessing the wrong schema direction.
2.  **Aliased UNIONs:** When evaluating mutually exclusive broken flows (e.g., billed without delivery OR delivered without billing), the prompt explicitly enforces strict column aliasing to prevent Cypher syntax crashes.
3.  **Context Squeezing:** To prevent blowing out the Groq API context window, the Cypher prompt enforces a strict `LIMIT 5` on multi-entity returns, and strictly forbids returning whole nodes (`RETURN n`), forcing property-only returns (`RETURN n.order_id`).

### 4. Semantic Routing & Security
A standalone **Semantic Router** was implemented *before* the LangChain QA Chain. 
* **Intent Classification:** The router evaluates the user's prompt against the conversation history. If the query falls outside the O2C domain, it intercepts the request and returns a static rejection message without executing a database query.
* **Pronoun Resolution:** The router rewrites contextual follow-up questions (e.g., resolving "What about that one?" to "What about Sales Order 123456?") to ensure the Cypher generator always has absolute context.

---

## 🛠️ Setup & Installation

Follow these steps to deploy Nexus O2C on your local machine.

### 1. Prerequisites
Ensure you have the following installed:
- Python 3.9+
- A running Neo4j Database (Local desktop version or a free Neo4j Aura cloud instance)
- A Groq API Key (Free tier available at console.groq.com)

### 2. Install Dependencies
Clone the repository and install the required Python packages:
```bash
# If using a virtual environment (recommended):
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate

# Install requirements
pip install -r requirements.txt
```

### 3. Environment Variables
Create a `.env` file in the root directory (or rename `.env.example`) and fill in your credentials:
```env
NEO4J_URI=bolt://localhost:7687  # Or your Aura Cloud URI (e.g. neo4j+s://xxxx.databases.neo4j.io)
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
GROQ_API_KEY=gsk_your_groq_api_key_here
```

### 4. Data Ingestion
Nexus O2C expects the raw SAP JSONL data to be located in `data/sap_dataset/sap-o2c-data/`. 
To populate your empty Neo4j database with the complete graph schema (Nodes and Edges):
```bash
python backend/ingest.py
```
*(This script will first erase any existing nodes in your DB, then batch-process thousands of records representing the entire Order-to-Cash lifecycle.)*

### 5. Start the AI Backend (FastAPI)
The FastAPI engine controls the LangChain router and securely manages database execution. Start it via Uvicorn:
```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### 6. Start the User Interface (Streamlit)
In a **new terminal window**, spin up the Nexus O2C interface:
```bash
streamlit run frontend/app.py --server.port 8501
```

You can now navigate to `http://localhost:8501` and start analyzing your SAP supply chain!
