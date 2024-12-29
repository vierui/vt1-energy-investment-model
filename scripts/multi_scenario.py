#!/usr/bin/env python3

"""
multi_scenario.py

- Loads scenarios from scenarios_parameters.csv
- Runs DCOPF for each scenario across winter, summer, autumn_spring
- Saves results and plots in /data/results/<scenario_name>/
- Summarizes costs in scenario_results.csv
"""
# %%
import pandas as pd
import numpy as np
import ast
import os
import matplotlib.pyplot as plt
import networkx as nx
from dcopf import dcopf  # Ensure this imports your updated DCOPF code
from dotenv import load_dotenv
from scenario_critic import ScenarioCritic
from update_readme import update_readme_with_scenarios

# Paths
working_dir = "/Users/rvieira/Documents/Master/vt1-energy-investment-model/data/working"
results_root = "/Users/rvieira/Documents/Master/vt1-energy-investment-model/data/results"

bus_file = os.path.join(working_dir, "bus.csv")
branch_file = os.path.join(working_dir, "branch.csv")
master_gen_file = os.path.join(working_dir, "master_gen.csv")
master_load_file = os.path.join(working_dir, "master_load.csv")
scenarios_params_file = os.path.join(working_dir, "scenarios_parameters.csv")

# Season weights
season_weights = {
    "winter": 13,
    "summer": 13,
    "autumn_spring": 26
}

# Load environment variables
load_dotenv('../.env.local')
api_key = os.getenv('OPENAPI_KEY')

if not api_key:
    raise ValueError("OpenAI API key not found in .env.local file")

# Initialize critic
critic = ScenarioCritic(api_key)

# %%
def ask_user_confirmation(message: str) -> bool:
    """Ask user for confirmation before proceeding"""
    while True:
        response = input(f"\n{message} (y/n): ").lower().strip()
        if response in ['y', 'yes']:
            return True
        elif response in ['n', 'no']:
            return False
        print("Please answer with 'y' or 'n'")

# %%
def build_gen_time_series(master_gen, gen_positions_dict, storage_positions_dict, season_key):
    """Build generation time series for the scenario."""
    scenario_gen = master_gen[master_gen["season"] == season_key].copy()
    merged_positions = {**gen_positions_dict, **storage_positions_dict}
    selected_ids = list(merged_positions.values())
    scenario_gen = scenario_gen[scenario_gen["id"].isin(selected_ids)].copy()
    
    for bus_i, gen_id in merged_positions.items():
        scenario_gen.loc[scenario_gen["id"] == gen_id, "bus"] = bus_i
    
    scenario_gen.drop_duplicates(subset=['time', 'id'], inplace=True)
    scenario_gen.sort_values(["time", "id"], inplace=True)
    scenario_gen.reset_index(drop=True, inplace=True)
    return scenario_gen

# %%
def build_demand_time_series(master_load, load_factor, season_key):
    """Build demand time series for the scenario."""
    scenario_load = master_load[master_load["season"] == season_key].copy()
    scenario_load["pd"] *= load_factor
    scenario_load.drop_duplicates(subset=['time', 'bus'], inplace=True)
    scenario_load.sort_values(["time", "bus"], inplace=True)
    scenario_load.reset_index(drop=True, inplace=True)
    return scenario_load

# %%
def plot_scenario_results(results, demand_time_series, branch, bus, scenario_folder, season_key, id_to_type, id_to_gencost, id_to_pmax):
    """
    Generate and save plots:
    - Generation vs. Demand
    - Histogram of Total Generation per Asset with Remaining Capacity
    - Histogram of Total Generation Cost per Asset
    """
    # Create default scenario folder if none provided
    if scenario_folder is None:
        scenario_folder = os.path.join(results_root, "temp_plots")
    
    # Ensure the directory exists
    os.makedirs(scenario_folder, exist_ok=True)

    generation_over_time = results['generation'].copy()
    flows_over_time = results['flows'].copy()

    # Pivot the Generation Data
    gen_pivot = generation_over_time.groupby(['time', 'id']).sum().reset_index()
    gen_pivot = gen_pivot.pivot(index='time', columns='id', values='gen')

    if gen_pivot.index.duplicated().any():
        gen_pivot = gen_pivot.groupby(level=0).sum()

    gen_pivot.sort_index(inplace=True)

    # Prepare the Total Demand Series
    demand_ts = demand_time_series.groupby('time')['pd'].sum().reindex(gen_pivot.index, fill_value=0)

    # Map generator IDs to types
    gen_pivot.rename(columns=id_to_type, inplace=True, errors="ignore")

    # Plot Generation vs. Demand
    plt.figure(figsize=(12, 6))
    plt.stackplot(gen_pivot.index, gen_pivot.T, labels=gen_pivot.columns, alpha=0.8)
    plt.plot(demand_ts.index, demand_ts.values, label='Total Demand', color='black', linewidth=2)
    plt.xlabel('Time')
    plt.ylabel('Power (MW)')
    plt.title(f'Generation vs Demand ({season_key.capitalize()})')
    plt.legend(loc='upper left')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(os.path.join(scenario_folder, f"gen_vs_demand_{season_key}.png"))
    plt.close()
    print(f"Saved Generation vs Demand plot => gen_vs_demand_{season_key}.png")

    # Histogram of Total Generation per Asset with Remaining Capacity
    total_gen_per_asset = gen_pivot.sum().sort_values(ascending=False)
    
    # Calculate remaining capacity based on pmax and season weights
    remaining_capacity = {}
    for asset, gen in total_gen_per_asset.items():
        # Find gen_id based on type
        gen_ids = [id for id, typ in id_to_type.items() if typ == asset]
        if gen_ids:
            gen_id = gen_ids[0]  # Assuming unique type
            total_pmax = id_to_pmax.get(gen_id, 0)  # Total available generation from pmax
            remaining = total_pmax - gen
            remaining_capacity[asset] = remaining if remaining > 0 else 0
        else:
            remaining_capacity[asset] = 0

    remaining_capacity_series = pd.Series(remaining_capacity)

    # Plot stacked histogram
    plt.figure(figsize=(10, 6))
    plt.bar(total_gen_per_asset.index, total_gen_per_asset, color='skyblue', label='Total Generation (MW)')
    plt.bar(remaining_capacity_series.index, remaining_capacity_series, bottom=total_gen_per_asset, color='lightgray', label='Remaining Capacity (MW)')
    plt.xlabel('Asset')
    plt.ylabel('Power (MW)')
    plt.title(f'Total Generation and Remaining Capacity per Asset ({season_key.capitalize()})')
    plt.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(os.path.join(scenario_folder, f"hist_total_gen_with_capacity_{season_key}.png"))
    plt.close()
    print(f"Saved Generation with Capacity histogram => hist_total_gen_with_capacity_{season_key}.png")

    # Histogram of Total Generation Cost per Asset
    total_gen_cost_per_asset = {}
    for asset, gen in total_gen_per_asset.items():
        # Find the corresponding ID
        gen_ids = [id for id, typ in id_to_type.items() if typ == asset]
        if gen_ids:
            gen_id = gen_ids[0]  # Assuming unique type
            if gen_id in id_to_gencost:
                total_gen_cost_per_asset[asset] = gen * id_to_gencost[gen_id]
            else:
                total_gen_cost_per_asset[asset] = 0.0  # Handle missing gencost
        else:
            total_gen_cost_per_asset[asset] = 0.0  # Handle missing asset

    total_gen_cost_series = pd.Series(total_gen_cost_per_asset)
    plt.figure(figsize=(10, 6))
    plt.bar(total_gen_cost_series.index, total_gen_cost_series, color='salmon')
    plt.xlabel('Asset')
    plt.ylabel('Total Generation Cost')
    plt.title(f'Total Generation Cost per Asset ({season_key.capitalize()})')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(os.path.join(scenario_folder, f"hist_total_gen_cost_{season_key}.png"))
    plt.close()
    print(f"Saved Generation Cost histogram => hist_total_gen_cost_{season_key}.png")

    # Check Flow Limits
    flows_with_limits = flows_over_time.merge(
        branch[['fbus', 'tbus', 'ratea']],
        left_on=['from_bus', 'to_bus'],
        right_on=['fbus', 'tbus'],
        how='left'
    )
    flows_with_limits['abs_flow'] = flows_with_limits['flow'].abs()
    flows_with_limits['within_limits'] = flows_with_limits['abs_flow'] <= flows_with_limits['ratea']
    exceeding = flows_with_limits[~flows_with_limits['within_limits']]
    if not exceeding.empty:
        exceeding.to_csv(os.path.join(scenario_folder, f"flows_exceeding_{season_key}.csv"), index=False)
        print(f"Flows exceeding limits saved => flows_exceeding_{season_key}.csv")
    else:
        print(f"All line flows are within limits for {season_key}.")

    # Commented out: Plot Line Flows Over Time
    # plt.figure(figsize=(12,6))
    # for (fbus, tbus), group in flows_with_limits.groupby(['from_bus', 'to_bus']):
    #     plt.plot(group['time'], group['flow'], label=f"{fbus}->{tbus}")
    # plt.xlabel('Time')
    # plt.ylabel('Flow (MW)')
    # plt.title(f'Line Flows Over Time ({season_key.capitalize()})')
    # plt.legend()
    # plt.xticks(rotation=45)
    # plt.tight_layout()
    # plt.savefig(os.path.join(scenario_folder, f"line_flows_{season_key}.png"))
    # plt.close()
    # print(f"Saved Line Flows plot => line_flows_{season_key}.png")

    # Convert Series to dict if needed, otherwise return the dict directly
    total_gen_per_asset_dict = (total_gen_per_asset.to_dict() 
                               if hasattr(total_gen_per_asset, 'to_dict') 
                               else total_gen_per_asset)
    
    total_gen_cost_per_asset_dict = (total_gen_cost_per_asset.to_dict() 
                                    if hasattr(total_gen_cost_per_asset, 'to_dict') 
                                    else total_gen_cost_per_asset)
    
    remaining_capacity_dict = (remaining_capacity_series.to_dict() 
                             if hasattr(remaining_capacity_series, 'to_dict') 
                             else remaining_capacity_series)

    return (total_gen_per_asset_dict, 
            total_gen_cost_per_asset_dict, 
            remaining_capacity_dict)

# %%
def main():
    # Load Data
    bus = pd.read_csv(bus_file)
    branch = pd.read_csv(branch_file)
    branch.rename(columns={"rateA": "ratea"}, inplace=True, errors="ignore")
    branch["sus"] = 1 / branch["x"]
    branch["id"] = np.arange(1, len(branch) + 1)

    master_gen = pd.read_csv(master_gen_file, parse_dates=["time"]).sort_values("time")
    master_load = pd.read_csv(master_load_file, parse_dates=["time"]).sort_values("time")

    # Create mappings from master_gen.csv
    id_to_type = master_gen.drop_duplicates(subset=['id'])[['id', 'type']].set_index('id')['type'].to_dict()
    type_to_id = master_gen.drop_duplicates(subset=['type'])[['type', 'id']].set_index('type')['id'].to_dict()
    id_to_gencost = master_gen.drop_duplicates(subset=['id'])[['id', 'gencost']].set_index('id')['gencost'].to_dict()
    id_to_pmax = master_gen.drop_duplicates(subset=['id'])[['id', 'pmax']].set_index('id')['pmax'].to_dict()

    # Load Scenarios
    scenarios_df = pd.read_csv(scenarios_params_file)
    scenario_results = []

    for _, row in scenarios_df.iterrows():
        scenario_name = row["scenario_name"]
        gen_pos_raw = ast.literal_eval(row["gen_positions"])       # e.g., {1:'nuclear', 4:'solar'}
        storage_pos_raw = ast.literal_eval(row["storage_units"])   # e.g., {2:'battery1'}
        load_factor = float(row["load_factor"])

        # Map types to IDs
        try:
            gen_positions = {bus: type_to_id[gen_type] for bus, gen_type in gen_pos_raw.items()}
        except KeyError as e:
            print(f"Error: Generator type '{e.args[0]}' not found in type_to_id mapping.")
            continue

        try:
            storage_positions = {bus: type_to_id[gen_type] for bus, gen_type in storage_pos_raw.items()}
        except KeyError as e:
            print(f"Error: Storage type '{e.args[0]}' not found in type_to_id mapping.")
            continue

        print(f"\nProcessing {scenario_name} with Generators: {gen_pos_raw} and Storage: {storage_pos_raw}")

        season_costs = {}
        all_ok = True

        # Initialize accumulators for metrics
        total_gen_year = {}
        total_gen_cost_year = {}
        total_avail_gen_year = {}

        # Create scenario folder early
        scenario_folder = os.path.join(results_root, scenario_name)
        os.makedirs(scenario_folder, exist_ok=True)

        for season in ["winter", "summer", "autumn_spring"]:
            print(f"  Running {season}...")
            gen_ts = build_gen_time_series(master_gen, gen_positions, storage_positions, season)
            demand_ts = build_demand_time_series(master_load, load_factor, season)
            results = dcopf(gen_ts, branch, bus, demand_ts, delta_t=1)

            if results and results.get("status") == "Optimal":
                season_costs[season] = results.get("cost", 0.0)
                print(f"    Optimal. Cost: {results['cost']}")
            else:
                print(f"    Not Optimal.")
                all_ok = False
                break

            # Plotting and metric extraction
            if all_ok:
                # Plotting and metric extraction
                plot_gen, plot_gen_cost, plot_avail = plot_scenario_results(
                    results, 
                    demand_ts, 
                    branch, 
                    bus, 
                    scenario_folder=scenario_folder,  # Now always providing a valid path
                    season_key=season, 
                    id_to_type=id_to_type, 
                    id_to_gencost=id_to_gencost, 
                    id_to_pmax=id_to_pmax
                )

                # Accumulate metrics weighted by season
                weight = season_weights[season]
                for asset, gen in plot_gen.items():
                    total_gen_year[asset] = total_gen_year.get(asset, 0) + gen * weight
                for asset, cost in plot_gen_cost.items():
                    total_gen_cost_year[asset] = total_gen_cost_year.get(asset, 0) + cost * weight
                for asset, avail in plot_avail.items():
                    total_avail_gen_year[asset] = total_avail_gen_year.get(asset, 0) + avail * weight

        if all_ok:
            # Calculate Annual Cost
            annual_cost = sum(season_costs[season] * season_weights[season] for season in season_costs)

            for season in ["winter", "summer", "autumn_spring"]:
                print(f"  Plotting {season}...")
                gen_ts_plot = build_gen_time_series(master_gen, gen_positions, storage_positions, season)
                demand_ts_plot = build_demand_time_series(master_load, load_factor, season)
                plot_results = dcopf(gen_ts_plot, branch, bus, demand_ts_plot, delta_t=1)
                if plot_results and plot_results.get("status") == "Optimal":
                    # Save plots and obtain metrics again
                    plot_gen, plot_gen_cost, plot_avail = plot_scenario_results(
                        plot_results, 
                        demand_ts_plot, 
                        branch, 
                        bus, 
                        scenario_folder, 
                        season, 
                        id_to_type, 
                        id_to_gencost, 
                        id_to_pmax
                    )

            # Prepare result entry with new metrics
            result_entry = {
                "scenario_name": scenario_name,
                "annual_cost": round(annual_cost, 1)
            }

            # Add Total Generation per Asset
            for asset, gen in total_gen_year.items():
                result_entry[f"gen_{asset}"] = round(gen, 1)

            # Add Total Generation Cost per Asset
            for asset, cost in total_gen_cost_year.items():
                result_entry[f"gen_cost_{asset}"] = round(cost, 1)

            # Add Total Available Generation per Asset
            for asset, avail in total_avail_gen_year.items():
                result_entry[f"avail_gen_{asset}"] = round(avail, 1)

            # Optional: Add Capacity Factor per Asset
            capacity_factor_year = {}
            for asset, gen in total_gen_year.items():
                avail = total_avail_gen_year.get(asset, 0)
                if avail > 0:
                    capacity_factor_year[asset] = round(gen / avail, 2)  # Rounded to 2 decimal places
                else:
                    capacity_factor_year[asset] = 0.0
            for asset, cf in capacity_factor_year.items():
                result_entry[f"capacity_factor_{asset}"] = cf

            scenario_results.append(result_entry)
            print(f"  Annual Cost: {round(annual_cost, 1)}")
        else:
            scenario_results.append({
                "scenario_name": scenario_name,
                "annual_cost": None
            })
            print(f"  {scenario_name} marked as NOT Optimal.")

    # Save Results
    results_df = pd.DataFrame(scenario_results)

    # Ask user before generating critiques
    if ask_user_confirmation("Do you want to generate AI critiques and markdown reports?"):
        print("\nGenerating AI critiques and markdown reports...")
        for _, row in results_df.iterrows():
            if row['annual_cost'] is not None:  # Only analyze valid scenarios
                critic.analyze_scenario(row.to_dict(), results_root)
        
        # Generate global comparison report
        if ask_user_confirmation("Do you want to generate a global comparison report?"):
            print("\nGenerating global comparison report...")
            critic.create_global_comparison_report(results_df, results_root)
        
        print("All scenarios processed and analyzed.")
    else:
        print("\nSkipping AI critiques generation.")

    # Save the CSV as before
    results_df.to_csv(os.path.join(results_root, "scenario_results.csv"), index=False)
    print("Results saved to CSV.")
    
    # Update README with scenario links
    update_readme_with_scenarios()
    print("README.md updated with scenario links.")

# %%
if __name__ == "__main__":
    main()
# %%
