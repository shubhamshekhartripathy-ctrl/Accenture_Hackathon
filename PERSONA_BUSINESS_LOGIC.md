# ReasonFlow Personas & Business Logic

In ReasonFlow, a KPI is not just a number on a dashboard—it is a **governed business object**. This means that when a KPI drops and the system recommends actions (like "Air-freight expedite" or "Activate backup supplier"), the system must enforce strict **Decision Rights**. 

A generic recommendation engine says *"Do X."* But if an AI recommends spending ₹3.4M on air freight, the business needs to know: **Who is authorized to approve this?** 

This is why ReasonFlow implements four distinct personas. Each persona has different visibility, different goals, and strictly enforced decision limits.

---

### 1. Executive (CEO / CFO / COO)
* **The Goal:** Strategic approval, risk management, and handling escalations.
* **What they do:** Executives don't need to see the deep statistical math; they need to know the financial exposure, the cost of waiting, and what decision is required. 
* **The Business Logic (Decisions Tab):** Executives have the highest authority. They can see all strategic options across departments. If an option requires breaking a standard constraint (like exceeding a planned budget), they have a special **"Override w/ reason"** capability to force an approval and record an auditable trail of *why* they made that exception. They are also the final approver for expensive options escalated by operational teams.

### 2. Supply Chain Manager (Operations)
* **The Goal:** Taking rapid operational action within predefined limits.
* **What they do:** They look at operational evidence (inventory, out-of-stock data, supplier communications) and execute playbooks to fix physical supply issues.
* **The Business Logic (Decisions Tab):** They can simulate options and hit **"Approve"** on actions that fall *within* their predefined budget or authority limits. 
    * **Example:** In the demo scenario, activating a standard backup supplier costs ₹1.6M. Because this is within their ₹2M limit, they see a green `AUTHORIZED` badge and can approve it.
    * **Why it locked for you:** The "Air-freight expedite" option costs ₹3.4M. This exceeds the Supply Chain Manager's spend limit. Therefore, the business logic marks it as `ESCALATE → EXECUTIVE`. The Supply Chain Manager is physically prevented from approving it to protect the company's P&L.

### 3. Analyst
* **The Goal:** Investigating the math, evidence, and data methodology. 
* **What they do:** Analysts dig into the "Explain" tab to see the deterministic SQL breakdowns, evidence extraction, and statistical models. They challenge the machine's hypotheses and correct drivers.
* **The Business Logic (Decisions Tab):** Analysts are designed to provide evidence, not to spend company money. Therefore, they have **No Approval Rights**. On the Decisions tab, they can view the options and run simulations to project impacts, but the system physically disables their ability to approve or commit to any business action.

### 4. KPI Owner / Data Steward
* **The Goal:** Ensuring the underlying data feeding the decision is trustworthy.
* **What they do:** They manage the "KPI Contract" (the official definition of the metric). If the ERP system says one number but the Finance system says another, they must reconcile it.
* **The Business Logic (Decisions Tab):** If the pipeline detects a severe data collision (e.g., conflicting definitions), the system halts. The KPI Owner gets a special **"Resolve Conflict"** control panel that other personas do not see. They are authorized to tell the system which data source is the "truth" so the investigation can proceed safely.

---

### Summary: The "One Truth, Many Views" Principle
The core business logic of ReasonFlow is that **the underlying structured conclusion never changes**. The math, the evidence, and the recommended actions are exactly the same across the entire enterprise. 

However, the UI dynamically restricts **what you can do** with that truth based on your contract entitlements. An Analyst can check the math, the Data Steward ensures the data is clean, the Supply Chain Manager executes the standard playbook, and the Executive approves the expensive exceptions.
