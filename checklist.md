

Here is the **Linear Workflow Loop** you will execute. Follow this sequence in order.

**Remember:** You act as the courier. You take the output from one agent and paste it as input for the next.

---

### 🔄 THE LEGACY REFACTOR LOOP (Scenario 4)

#### **STEP 1: THE INVESTIGATION**
*   **Agent:** `[[00_analyst]]`
*   **Input:** Your raw code (`api_server2.py`, `motor_controller.py`) + the Prompt I gave you in the previous message.
*   **Goal:** Figure out what the code actually does and define the Specification.
*   **You Do:** Run Analyst -> **Paste the Output here.**
    *   *(I will review the Spec and prepare the Architect prompt.)*

#### **STEP 2: THE DESIGN**
*   **Agent:** `[[01_architect]]`
*   **Input:** The "Functional Specification" from Step 1.
*   **Goal:** Design the modern structure. Create the "Contract" (Classes, API Routes, Database Schema).
*   **You Do:** Run Architect -> **Paste the Output here.**
    *   *(I will check the Contract and prepare the Implementer prompt.)*

#### **STEP 3: THE BUILD**
*   **Agent:** `[[02_implementer]]`
*   **Input:** The "Contract" from Step 2.
*   **Goal:** Write the new, working Python code based on the design.
*   **You Do:** Run Implementer -> **Paste the Output here.**
    *   *(I will check the code and prepare the Refiner prompt.)*

#### **STEP 4: THE CLEANUP**
*   **Agent:** `[[03_refiner]]`
*   **Input:** The raw code from Step 3.
*   **Goal:** Add Type Hints, Docstrings, Logging, and PEP8 formatting.
*   **You Do:** Run Refiner -> **Paste the Output here.**
    *   *(I will check the hygiene and prepare the Auditor prompt.)*

#### **STEP 5: THE VERIFICATION**
*   **Agent:** `[[05_auditor]]`
*   **Input:** The clean code from Step 4 + The original "Contract" from Step 2.
*   **Goal:** Ensure the code actually fulfills the design and has no bugs.
*   **You Do:** Run Auditor -> **Paste the Output here.**

---

### ⏭️ CURRENT STATUS

You are currently at **Step 1**.
Go to `[[00_analyst]]`, run the investigation, and bring me the report.