import numpy as np
import csv
import matplotlib.pyplot as plt
import os
import pickle
import networkx as nx

# ===========================
# 1. Variables and Set-up
# ===========================

# Cost coefficients per p.u. for:
cost_coefficients = np.array([50,   # nuclear
                              0,    # wind
                              0,    # solar 
                              70])  # gas

# Hourly demand for 24 hours
hourly_demand = np.array([3, 3, 3, 2.5, 2.5, 3, 4, 5, 5.5, 6, 6.5, 7, 7.5, 7, 6.5, 6, 6, 6.5, 6, 5, 4, 3.5, 3, 3])
# Split total demand between Load 1 and Load 2 (e.g., 60% to Load 1, 40% to Load 2)
load1_demand = hourly_demand * 0.6  # 60% of total demand to Load 1
load2_demand = hourly_demand * 0.4  # 40% of total demand to Load 2

# Generation availability for each source (in p.u.)
nuclear_availability = np.ones(24) * 2.0
wind_availability = np.array([0.5, 0.4, 0.3, 0.4, 0.5, 1.0, 1.2, 1.5, 1.3, 1.0, 0.8, 0.6, 0.7, 1.0, 1.2, 1.5, 1.3, 1.0, 0.8, 0.6, 0.4, 0.3, 0.2, 0.1])
solar_availability = np.array([0, 0, 0, 0, 0, 0, 0.3, 0.5, 0.8, 1.0, 1.2, 1.5, 1.7, 1.6, 1.5, 1.0, 0.8, 0.5, 0.2, 0, 0, 0, 0, 0])
gas_availability = np.ones(24) * 4.0

# Reactances between buses - GUESS (in p.u.)
x_nuclear_wind = 0.1
x_nuclear_solar = 0.15
x_wind_gas = 0.2
x_solar_gas = 0.1
x_gas_load1 = 0.2
x_gas_load2 = 0.25
x_nuclear_load1 = 0.2
x_solar_load1 = 0.25
x_nuclear_load2 = 0.3
x_wind_load2 = 0.15

# Admittance matrix B' (inverse of reactances)
B_prime = np.array([
    [1/x_nuclear_wind + 1/x_nuclear_solar + 1/x_nuclear_load1 + 1/x_nuclear_load2, -1/x_nuclear_wind, -1/x_nuclear_solar, 0, -1/x_nuclear_load1, -1/x_nuclear_load2],
    [-1/x_nuclear_wind, 1/x_nuclear_wind + 1/x_wind_gas + 1/x_wind_load2, 0, -1/x_wind_gas, 0, -1/x_wind_load2],
    [-1/x_nuclear_solar, 0, 1/x_nuclear_solar + 1/x_solar_gas + 1/x_solar_load1, -1/x_solar_gas, -1/x_solar_load1, 0],
    [0, -1/x_wind_gas, -1/x_solar_gas, 1/x_wind_gas + 1/x_solar_gas, 0, 0],
    [-1/x_nuclear_load1, 0, -1/x_solar_load1, 0, 1/x_nuclear_load1 + 1/x_solar_load1 + 1/x_gas_load1, 0],
    [-1/x_nuclear_load2, -1/x_wind_load2, 0, 0, 0, 1/x_nuclear_load2 + 1/x_wind_load2 + 1/x_gas_load2]
])

# ========================
# 2. Functions
# ========================

def objective(P):
    """Objective function: total cost of generation"""
    return np.dot(cost_coefficients, P)

def dc_power_flow(P_injections):
    """Solves DC power flow for bus angles and calculates power flow between buses"""
    # Remove the last row/column for the reference bus (Gas bus here)
    B_prime_reduced = B_prime[:-1, :-1]
    P_injections_reduced = P_injections[:-1]
    
    # Solve for bus angles (excluding reference bus)
    theta = np.linalg.solve(B_prime_reduced, P_injections_reduced)
    theta = np.append(theta, 0)  # Reference bus angle set to 0 (Gas bus)

    # Calculate power flows between buses
    P_nuclear_wind = (theta[0] - theta[1]) / x_nuclear_wind
    P_nuclear_solar = (theta[0] - theta[2]) / x_nuclear_solar
    P_wind_gas = (theta[1] - theta[3]) / x_wind_gas
    P_solar_gas = (theta[2] - theta[3]) / x_solar_gas
    P_nuclear_load1 = (theta[0] - theta[4]) / x_nuclear_load1
    P_solar_load1 = (theta[2] - theta[4]) / x_solar_load1
    P_nuclear_load2 = (theta[0] - theta[5]) / x_nuclear_load2
    P_wind_load2 = (theta[1] - theta[5]) / x_wind_load2

    return theta, P_nuclear_wind, P_nuclear_solar, P_wind_gas, P_solar_gas, P_nuclear_load1, P_solar_load1, P_nuclear_load2, P_wind_load2

# ================================
# 3. Main
# ================================

# Optimized results storage
nuclear_gen = []
wind_gen = []
solar_gen = []
gas_gen = []
total_costs = []
load1_demand = np.array([1.0] * 24)  # Example constant load for bus 5
load2_demand = np.array([0.5] * 24)  # Example constant load for bus 6

# Initial guesses for power generation at buses 1-4
initial_generation = [1.0,  # nuclear
                      0.5,  # wind
                      0.5,  # solar
                      2.0]  # gas

for hour in range(24):
    # Total demand for the current hour
    demand = hourly_demand[hour]
    
    # Use wind and solar first, capped by their availability
    wind_gen_hour = min(wind_availability[hour], demand)
    remaining_demand = demand - wind_gen_hour
    
    solar_gen_hour = min(solar_availability[hour], remaining_demand)
    remaining_demand -= solar_gen_hour
    
    # Use nuclear generation next
    nuclear_gen_hour = min(nuclear_availability[hour], remaining_demand)
    remaining_demand -= nuclear_gen_hour
    
    # Gas fills any remaining demand (if any)
    gas_gen_hour = max(0, remaining_demand)  # Ensure gas generation is non-negative
    
    # Power injections now include generation for Load 1 and Load 2
    P_injections = [nuclear_gen_hour,        # Nuclear
                    wind_gen_hour,           # Wind
                    solar_gen_hour,          # Solar
                    gas_gen_hour,            # Gas
                    -load1_demand[hour],     # Negative injection for Load 1
                    -load2_demand[hour]]     # Negative injection for Load 2
    
    # Run power flow with the updated injections
    theta, P_nuclear_wind, P_nuclear_solar, P_wind_gas, P_solar_gas, P_nuclear_load1, P_solar_load1, P_nuclear_load2, P_wind_load2 = dc_power_flow(P_injections)
    
    # Store generation outputs
    nuclear_gen.append(nuclear_gen_hour)
    wind_gen.append(wind_gen_hour)
    solar_gen.append(solar_gen_hour)
    gas_gen.append(gas_gen_hour)
    
    # Calculate and store total cost (only for generation, not loads)
    total_cost = objective(P_injections[:4])  # Only consider the generation part of P_injections
    total_costs.append(total_cost)

    print(f"Hour {hour}: Nuclear: {P_injections[0]:.2f} p.u., Wind: {P_injections[1]:.2f} p.u., Solar: {P_injections[2]:.2f} p.u., Gas: {P_injections[3]:.2f} p.u.")
    print(f"Total Generation Cost: ${total_cost:.2f}")



# ================================
# 4. Save Data 
# ================================

# Save the variables into a pickle file after optimization completes
data_to_save = {
    "hourly_demand": hourly_demand,
    "nuclear_availability": nuclear_availability,
    "wind_availability": wind_availability,
    "solar_availability": solar_availability,
    "gas_availability": gas_availability,
    "nuclear_gen": nuclear_gen,
    "wind_gen": wind_gen,
    "solar_gen": solar_gen,
    "gas_gen": gas_gen,
    "total_costs": total_costs
}

with open('data/optimization_results.pkl', 'wb') as f:
    pickle.dump(data_to_save, f)
print("Optimization results saved to 'data/optimization_results.pkl'")

# Save the results in a CSV file
with open("data/results/generation_results.csv", "w", newline='') as csvfile:
    writer = csv.writer(csvfile)
    # Write the header with units
    writer.writerow(["Hour", "Nuclear (p.u.)", "Wind (p.u.)", "Solar (p.u.)", "Gas (p.u.)", "Total Cost ($)"])
    
    # Write the data for each hour with formatted numbers
    for hour in range(24):
        writer.writerow([
            f"{hour:02}",  # Ensure hour is always 2 digits
            f"{nuclear_gen[hour]:.2f}", 
            f"{wind_gen[hour]:.2f}", 
            f"{solar_gen[hour]:.2f}", 
            f"{gas_gen[hour]:.2f}", 
            f"{total_costs[hour]:.2f}"
        ])

# ================================
# 5. Results Plotting 
# ================================

# Ensure the logs/figures directory exists
os.makedirs('logs/figures', exist_ok=True)

# Plot the results
hours = np.arange(24)

# Plot the generation per source
plt.figure(figsize=(10, 6))
plt.plot(hours, nuclear_gen, label="Nuclear Generation", marker='o')
plt.plot(hours, wind_gen, label="Wind Generation", marker='o')
plt.plot(hours, solar_gen, label="Solar Generation", marker='o')
plt.plot(hours, gas_gen, label="Gas Generation", marker='o')
plt.xlabel("Hour of the Day")
plt.ylabel("Generation (p.u.)")
plt.title("Generation per Source Over 24 Hours")
plt.legend()
plt.grid(True)
plt.show()

# Plot total generation costs over time
plt.figure(figsize=(10, 6))
plt.plot(hours, total_costs, label="Total Generation Cost", marker='o', color='r')
plt.xlabel("Hour of the Day")
plt.ylabel("Total Generation Cost ($)")
plt.title("Total Generation Costs Over 24 Hours")
plt.grid(True)
plt.show()

# ================================

# Grid overview
G = nx.DiGraph() # Create a directed graph
G.add_node("Nuclear", pos=(0, 2))
G.add_node("Wind", pos=(2, 3))
G.add_node("Solar", pos=(2, 1))
G.add_node("Gas", pos=(4, 2))
G.add_node("Load 1", pos=(5, 1))
G.add_node("Load 2", pos=(5, 3))

# Add edges representing transmission lines (reactances)
G.add_edge("Nuclear", "Wind", weight=x_nuclear_wind)
G.add_edge("Nuclear", "Solar", weight=x_nuclear_solar)
G.add_edge("Wind", "Gas", weight=x_wind_gas)
G.add_edge("Solar", "Gas", weight=x_solar_gas)
G.add_edge("Nuclear", "Load 1", weight=x_nuclear_load1)
G.add_edge("Solar", "Load 1", weight=x_solar_load1)
G.add_edge("Gas", "Load 1", weight=x_gas_load1)
G.add_edge("Nuclear", "Load 2", weight=x_nuclear_load2)
G.add_edge("Wind", "Load 2", weight=x_wind_load2)
G.add_edge("Gas", "Load 2", weight=x_gas_load2)


# Get positions for all nodes
pos = nx.get_node_attributes(G, 'pos') 

# Draw the network
plt.figure(figsize=(8, 6))
nx.draw(G, pos, with_labels=True, node_size=3000, node_color='lightblue', font_size=12, font_weight='bold', edge_color='gray', width=2) # Draw the network

# Draw edge labels (reactances)
edge_labels = nx.get_edge_attributes(G, 'weight')
nx.draw_networkx_edge_labels(G, pos, edge_labels={(u, v): f'{d["weight"]} p.u.' for u, v, d in G.edges(data=True)}, font_size=10)

plt.title("Grid Overview with Reactances (p.u.)")
plt.grid(False)
plt.show()
