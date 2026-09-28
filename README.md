# Science-Fit

> **Evidence-Based AI Fitness & Nutrition Coach**  
> Grounded in peer-reviewed exercise physiology (ACSM, ISSN, Schoenfeld, Morton, Mifflin-St Jeor).

Science-Fit is a hybrid deterministic–probabilistic coaching system. Rather than relying on LLMs to perform arithmetic or hallucinate workout splits, the system executes proven mathematical and physiological formulas in Python, manages state with **LangGraph**, grounds its reasoning in a **Qdrant** scientific literature vector base, and protects trainees with safety guardrails.

---

## Key Capabilities

- **Zero-Hallucination Math**: BMR, TDEE, goal caloric adjustments, and macronutrient targets (protein, fat, carbs) are pre-calculated using the Mifflin-St Jeor equation and ISSN protein guidelines ($\ge 1.6 - 2.2\text{ g/kg}$).
- **Evidence-Based Volume Landmarks**: Evaluates weekly sets per muscle against scientific thresholds: Minimum Effective Volume (MEV), Maximum Adaptive Volume (MAV), and Maximum Recoverable Volume (MRV) sourced from Schoenfeld (2017) and ACSM (2009).
- **Double-Progression Tracking**: Automatically checks performance across sessions and prescribes weight increases or rep progressions.
- **Dynamic Tool-Augmented LLM**: The coach dynamically invokes deterministic tools (`calculate_hypothetical_macros`, `get_training_guidelines`, `search_scientific_evidence`) during reasoning turns.
- **Self-Correcting Guardrails**: Catches dangerous recommendations (deficits $>1000\text{ kcal}$ or volume exceeding MRV) and loops back to self-correct before presenting answers to the trainee.
- **Peer-Reviewed Citations**: Every recommendation includes exact literature citations (e.g. `[MORTON-2018]`, `[SCHOENFELD-2021]`).

---

## Quickstart

### 1. Prerequisites
- Python 3.11+
- [Ollama](https://ollama.com/) running locally with models:
  ```bash
  ollama pull gemma4:31b-cloud   # or your preferred chat model
  ollama pull nomic-embed-text    # embedding model
  ```
- [Docker Desktop](https://www.docker.com/) (optional, for persistent PostgreSQL and Qdrant RAG)

### 2. Installation
```bash
git clone https://github.com/AhmedA005/science-fit.git
cd science-fit

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e .
```

### 3. Environment Configuration
Copy the example configuration:
```bash
cp .env.example .env
```
Ensure your Ollama host and credentials match your setup.

---

## Running the Coach

You can run Science-Fit in two interactive modes:

### Mode A: Interactive Terminal Coach (CLI)
Start the terminal coach with the onboarding wizard:
```bash
python run.py
```
1. Input your personal stats (Age, Gender, Height, Weight, Experience, Goal, Days/week).
2. Review your verified baseline metrics (BMR, TDEE, Calorie/Macro targets, MEV/MRV).
3. Chat freely with the coach with full multi-turn conversation memory.

### Mode B: Web Browser Application (Streamlit)
Launch the visual web application:
```bash
python run.py --web
# or: streamlit run app.py
```
- Open `http://localhost:8501` in your browser.
- Adjust your profile and goals dynamically in the sidebar to see real-time macro and volume updates.
- Chat with the AI coach, view executed tool calls, and inspect peer-reviewed citations.

---

## (Optional) Running with Full Database & RAG Persistence

To enable multi-user PostgreSQL storage and vector search across the scientific literature:

```bash
# 1. Start PostgreSQL and Qdrant containers
docker compose up -d postgres qdrant

# 2. Run database migrations
alembic upgrade head

# 3. Seed exercise and food catalogs
python scripts/seed_exercises.py
python scripts/seed_foods.py

# 4. Index peer-reviewed research papers into Qdrant
python scripts/seed_knowledge.py

# 5. (Optional) Create a demo trainee with 3 weeks of logged workouts
python scripts/create_test_user.py
```

---

## Architecture Overview

```
┌────────────────────────────────────────────────────────────────────────┐
│ Layer 4: LangGraph Orchestrator & Multi-Turn State Machine             │
│   Intent Routing ──► Context Injection ──► Tool Calling ──► Guardrails │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ consumes verified DTOs & citations
┌───────────────────────────────────▼────────────────────────────────────┐
│ Layer 3: Deterministic Engines & RAG                                   │
│   • Training Engine     • Volume Calculator (MEV/MAV/MRV)              │
│   • Progression Checker • Nutrition Calculator (Mifflin-St Jeor)       │
│   • Qdrant Vector DB (Peer-reviewed literature: Morton, Schoenfeld)    │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ clean schemas (Pydantic V2)
┌───────────────────────────────────▼────────────────────────────────────┐
│ Layer 1 & 2: Persistence & Repository Pattern                          │
│   • PostgreSQL (asyncpg / SQLAlchemy) + Repository abstraction         │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
science-fit/
├── app.py                      # Streamlit interactive Web Application
├── run.py                      # Unified launcher (CLI or Web)
├── docker-compose.yml          # PostgreSQL & Qdrant containers
├── knowledge/                  # Peer-reviewed scientific research markdown papers
├── config/
│   ├── training_config.yaml    # Evidence landmarks (MEV/MAV/MRV) and RIR rules
│   └── nutrition_config.yaml   # BMR/TDEE multipliers and macro rules
├── src/
│   ├── agent/                  # Layer 4: LangGraph StateGraph, nodes, tools, prompts
│   ├── services/               # Layer 3: Deterministic engines (volume, progression, nutrition)
│   ├── rag/                    # Layer 3: Vector search and indexing (Qdrant + embeddings)
│   ├── repositories/           # Layer 2: Database repository queries
│   ├── schemas/                # Layer 2: Pydantic DTO contracts
│   └── models/                 # Layer 1: SQLAlchemy ORM models
└── scripts/
    ├── interactive_coach.py    # Terminal interactive coach with onboarding wizard
    ├── test_agent.py           # Automated multi-turn verification test
    ├── seed_knowledge.py       # Qdrant knowledge base indexer
    └── create_test_user.py     # Realistic test user with workout logs
```

---

## License
MIT License.
