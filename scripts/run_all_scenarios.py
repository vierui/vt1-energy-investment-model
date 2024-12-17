# %%
import subprocess
import re

def run_and_get_cost(scenario_path):
    result = subprocess.run(["python", "run_scenario.py", "--scenario", scenario_path], capture_output=True, text=True)
    # parse the output to find "Total Weekly Cost: X"
    match = re.search(r"Total Weekly Cost:\s+(\d+(\.\d+)?)", result.stdout)
    if match:
        return float(match.group(1))
    else:
        return None

winter_cost = run_and_get_cost("../data/scenarios/winter")
summer_cost = run_and_get_cost("../data/scenarios/summer")
autumn_spring_cost = run_and_get_cost("../data/scenarios/autumn_spring")

annual_cost = (winter_cost * 13) + (summer_cost * 13) + (autumn_spring_cost * 26)
print(f"Estimated winter Cost: {winter_cost * 13}")
print(f"Estimated summer Cost: {summer_cost * 13}")
print(f"Estimated annual Cost: {annual_cost}")
# %%
