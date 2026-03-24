# Nexus O2C: Graph-Based Query Engine

**Nexus O2C** is an intelligent, graph-based data modeling and natural language query system designed to analyze SAP **Order-to-Cash (O2C)** workflows. 

Instead of writing complex SQL or Cypher, Nexus O2C allows you to intuitively ask questions in plain English—such as *"Which products are associated with the highest number of billing documents?"* or *"Trace the flow of outbound delivery 80738070."* The AI agent dynamically translates your questions into validated Neo4j Cypher queries, retrieves the exact relationships from the graph database, and returns the insights alongside a beautifully rendered interactive topology of the localized data.

## 🚀 Key Features
- **Conversational Memory:** The AI remembers previous context, seamlessly resolving pronouns like "this order" or "those products" intelligently.
- **Graph Visualization:** A dynamic PyVis topology map automatically renders the 1-hop neighborhood of the precise entities the LLM is discussing, built to match Streamlit's dark/light interface layouts.
- **Self-Healing Cypher Generation:** Powered by LangChain, the backend autonomously evaluates and routes queries, translating natural language against a strict SAP data schema.
- **High Performance:** Features threaded timeouts, consolidated LLM routing, and frontend graph-caching to deliver results lightning fast.

## ⚙️ Tech Stack
- **Backend:** Python, FastAPI, Uvicorn
- **Frontend / UI:** Streamlit, PyVis (for Interactive Graphing)
- **AI & Intelligent Routing:** LangChain Core, `GraphCypherQAChain`
- **LLM Provider:** Groq Engine (`llama-3.3-70b-versatile`)
- **Database:** Neo4j (AuraDB Cloud or Local Desktop)

---

## 🛠 Setup & Installation

Follow these steps to deploy Nexus O2C on your local machine:

### 1. Prerequisites
Ensure you have the following installed:
- Python 3.9+
- A running Neo4j Database (Local desktop version or a free Neo4j Aura cloud instance)
- A Groq API Key (Free tier available at console.groq.com)

### 2. Install Dependencies
Clone the repository and install the Python packages:
```bash
# If using a virtual environment (recommended):
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

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
