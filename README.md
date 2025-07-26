# CT Patient Intake System using Agentic AI Workflow

🏥 **CT_Patient-Intake-System-using-Agentic-AI-Workflow** is a multi-agent, agentic-AI-driven solution designed to streamline and automate the patient intake process for healthcare organizations. It leverages intelligent agents, modular data models, and interactive UI elements to collect, validate, and process patient and insurance information efficiently.

---

<img width="1918" height="867" alt="image" src="https://github.com/user-attachments/assets/41b5ffbf-5da4-4a8d-acd6-0e39218f6fba" />

---

## 🚀 Features

- **Multi-Agent Pipeline:** Uses agentic AI for dynamic, context-aware patient data collection and intake.
- **Automated Data Validation:** Built-in validators enforce completeness and correctness for insurance, benefits, and authorization fields.
- **Comprehensive Models:** Modular Pydantic models for all relevant domains (client, insurance, benefits, documents, payor contacts, etc.).
- **Session Management:** Robust session tracking for seamless multi-step intakes.
- **Interactive CLI & UI:** Supports both command-line and web-based workflows for users and staff.
- **Synthetic Data Generation:** Built-in tools for demo and testing with realistic, synthetic sample data.
- **Extensible Benefits Verification:** Models and agents for prior authorization, maximum caps, visit limits, and coordination of benefits.

## 🏗️ Main Components

- `agentic-ai/main.py`:  
  The system orchestrator. Initializes the session, runs the main patient intake pipeline, manages agent interaction loops, and tracks session state.  
  - Starts the intake process and handles user/agent dialogue.
  - Prints step-by-step progress and session state updates.
  - Handles completion and error cases gracefully.

- `agentic-ai/model/benefit_check_form.py` & `model/soap_note.py`:  
  Modular Pydantic models for all patient, insurance, benefit, and document data used throughout the pipeline.  
  - Enforces type and value validation for all fields.
  - Includes validators for complex business logic (e.g., prior auth required if certain fields are set).
  - Supports synthetic data generation for demos and testing.

- `agentic-ai/app/intake_ui.py`:  
  (Optional UI extension) Provides web-based intake with real-time session management, status displays, and quick action buttons.

- **Agentic Workflow Logic:**  
  ADK/Google agentic AI runners handle the dialogue and workflow steps, adapting dynamically to user responses and context.

## ✨ Example Workflow

1. **Session Initialization:**  
   Unique session & user IDs assigned for every intake.

2. **Pipeline Start:**  
   The agent-based system welcomes the user and begins interactive data gathering.

3. **Data Collection:**  
   The system collects and validates:
   - Patient demographics
   - Insurance details
   - Benefit verification (copays, deductibles, OOP max, etc.)
   - Prior authorization and visit limits
   - Coordination of benefits if needed
   - Document tracking and payor contacts

4. **Completion:**  
   Once all required fields are collected and verified, the system marks the intake as complete and can communicate results (e.g., via email).

5. **Synthetic Example:**  
   The models include a script to generate and print realistic sample benefit check data for testing.

---

## 🛠️ Usage

### Requirements

- Python 3.9+
- [Pydantic](https://pydantic.dev/)
- [Streamlit](https://streamlit.io/) (for optional UI)
- Google ADK / genai agentic AI libraries

### Run the Main Pipeline

```bash
cd agentic-ai
python main.py
```

### Run the Synthetic Data Generator

```bash
cd agentic-ai/model
python benefit_check_form.py
```

### (Optional) Start the Web UI

```bash
cd agentic-ai/app
streamlit run intake_ui.py
```

---

## 📁 Project Structure

```
agentic-ai/
  ├── main.py                # Main entrypoint, session & pipeline logic
  ├── app/
  │   └── intake_ui.py       # Streamlit-based web UI
  ├── model/
  │   ├── benefit_check_form.py # Pydantic models for all benefit/intake data
  │   ├── soap_note.py         # SOAP note and benefit validation models
  │   └── benefit_check_summary.py # Agent usage example
  └── ...
```

---

## 📝 License

This project is licensed under the MIT License &copy; 2025 Aaryaman K.

---

## 🤖 Acknowledgements

- Built using Python, Pydantic, Streamlit, and Google ADK/genai agentic AI runners.

---

## 🌟 Contributing

Pull requests and collaborations are welcome! Please open an issue to discuss major changes.
