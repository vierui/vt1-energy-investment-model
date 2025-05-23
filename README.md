
# Energy Investment Optimization Model

## Overview

This project tackles a critical challenge at the intersection of energy systems engineering and investment strategy:
How can we design and operate future power systems that are both technically sound and economically viable?

The model I developed answers this by combining:
	•	Hourly power flow optimization to simulate grid operations using Linear Programming (LP).
	•	Financial evaluation of renewable and storage assets using Net Present Value (NPV) and Annuities.

It’s a decision-support tool built for evaluating energy investment scenarios—whether for national infrastructure, regional grids, or local microgrids.

⸻

## What the Model Can Do

At a glance:
	•	Simulates realistic grid behavior hour-by-hour.
	•	Optimizes generation and storage dispatch to minimize cost.
	•	Compares long-term economic outcomes across different technology mixes.
	•	Outputs clear visual and analytical reports, with optional AI-powered commentary.

This allows users to explore “what-if” strategies like:
	•	Adding batteries to stabilize solar-heavy grids.
	•	Testing nuclear versus gas baseload performance.
	•	Scaling renewables based on demand forecasts.

⸻

## Key Features
	1.	DC Optimal Power Flow (DCOPF):
Uses LP to compute the lowest-cost electricity dispatch, respecting:
	•	Generator limits
	•	Line capacities
	•	Storage constraints
	2.	Scenario-Based Analysis:
Modular setup enables batch comparison of different generation/storage portfolios, load shapes, and locations.
	3.	Integrated Techno-Economic Metrics:
Computes:
	•	NPV over 10, 20, and 30 years
	•	Annualized cost (annuity)
	•	CAPEX, OPEX breakdowns
	4.	Renewables & Storage Modeling:
Captures solar/wind variability, round-trip efficiency, and battery behavior over time.
	5.	Automated Reporting & Visualization:
	•	Markdown reports for each scenario
	•	Comparative charts for dispatch, generation mix, and financials
	•	Optional AI insights on performance trade-offs

⸻

## How It Works

1. Configure Input Data
	•	Grid topology: branch.csv, bus.csv (MATPOWER-style)
	•	Generators/load profiles: master_gen.csv, master_load.csv
	•	Scenario parameters: scenarios_parameters.csv

2. Run Optimization
	•	Solver: PuLP with CBC backend
	•	Script: dcopf.py

3. Perform Investment Analysis
	•	Script: create_master_invest.py
	•	Inputs: CAPEX, OPEX, lifetime, discount rate

4. Generate Outputs
	•	Reports: scenario-wise .md reports
	•	Plots: seasonal generation, cost breakdowns
	•	(Optional) Run scenario_critic.py for AI-driven summaries

⸻

## Example Use Cases

### Individual Scenario:
	•	Dispatch & generation visualizations
	•	Economic evaluation of wind + solar + nuclear + storage
	•	Example:
Scenario 5 analysis

### Multi-Scenario Comparison:
	•	Sorts best-performing tech mixes by annuity
	•	Visual trade-offs across strategies
	•	Explore:
Global comparison report

⸻

## How to Run the Model
	1.	Clone the repo:
    ```bash
    git clone https://github.com/vierui/vt1-energy-investment-model.git
    cd energy-investment-model
    ```

	2.	Install dependencies :
    ```bash
    poetry install
    ```

	3.	Prepare your data:
    Ensure input .csv files are in data/working/
    Configure your scenarios in scenarios_parameters.csv
	4.	Run the main script:
    ```bash
    poetry run python main.py
    ```

	5.	Explore outputs:
    Results are saved in data/results/ and report/

⸻

🧩 Customization & Extension

Designed as a flexible framework for experimentation:
	•	Scale to any grid size (9-bus test to national-level topologies)
	•	Add new generation/storage technologies by editing master_gen.csv
	•	Adapt to future pricing models, policies, or climate scenarios

⸻

🤝 Contributions

Contributions are welcome!
Fork → Branch → Commit → PR

⸻

📜 License

MIT License – see LICENSE

⸻
