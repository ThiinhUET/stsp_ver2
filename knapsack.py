# Copyright 2021 D-Wave Systems Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import os
import itertools
import click
import pandas as pd
from dwave.system import LeapHybridCQMSampler
from dimod import ConstrainedQuadraticModel, BinaryQuadraticModel

def parse_inputs(data_file, capacity):
    """Parse user input and files for data to build CQM.

    Args:
        data_file (csv file):
            File of items (weight & cost) slated to ship.
        capacity (int):
            Max weight the shipping container can accept.

    Returns:
        Costs, weights, and capacity.
    """
    df = pd.read_csv(data_file, names=['cost', 'weight'])

    if not capacity:
        capacity = int(0.8 * sum(df['weight']))
        print("\nSetting weight capacity to 80% of total: {}".format(str(capacity)))

    return df['cost'], df['weight'], capacity

def build_knapsack_cqm(costs, weights, max_weight):
    """Construct a CQM for the knapsack problem.

    Args:
        costs (array-like):
            Array of costs for the items.
        weights (array-like):
            Array of weights for the items.
        max_weight (int):
            Maximum allowable weight for the knapsack.

    Returns:
        Constrained quadratic model instance that represents the knapsack problem.
    """
    num_items = len(costs)
    print("\nBuilding a CQM for {} items.".format(str(num_items)))

    cqm = ConstrainedQuadraticModel()
    obj = BinaryQuadraticModel(vartype='BINARY')

    # Objective is to maximize the total costs
    for i in range(num_items):
        obj.add_variable(i)
        obj.set_linear(i, -costs[i])
    cqm.set_objective(obj)

    # Constraint is to keep the sum of items' weights under or equal capacity
    constraint = [(i, weights[i]) for i in range(num_items)]
    cqm.add_constraint(constraint, sense="<=", rhs=max_weight, label='capacity')

    return cqm

def parse_solution(sampleset, costs, weights):
    """Translate the best sample returned from solver to shipped items.

    Args:

        sampleset (dimod.Sampleset):
            Samples returned from the solver.
        costs (array-like):
            Array of costs for the items.
        weights (array-like):
            Array of weights for the items.
    """
    if not any(sampleset.record["is_feasible"]):
        raise ValueError("No feasible solution found")

    best = next(itertools.filterfalse(lambda d: not getattr(d,'is_feasible'),
                list(sampleset.data())))

    selected_item_indices = [key for key, val in best.sample.items() if val==1.0]
    selected_weights = list(weights.loc[selected_item_indices])
    selected_costs = list(costs.loc[selected_item_indices])

    print("\nFound best solution at energy {}".format(best.energy))
    print("\nSelected item numbers (0-indexed):", selected_item_indices)
    print("\nSelected item weights: {}, total = {}".format(selected_weights, sum(selected_weights)))
    print("\nSelected item costs: {}, total = {}".format(selected_costs, sum(selected_costs)))

# Format the help display ("\b" enables newlines in click() help text)
datafiles = os.listdir("data")
datafile_help = """
Name of data file (under the 'data/' folder) to run on. One of:\n
File Name \t\t Total weight\n
\b
"""
for file in datafiles:
    df = pd.read_csv("data/" + file, names=['cost', 'weight'])
    datafile_help += str(file) + "\t\t" + str(sum(df['weight'])) + "\n"
datafile_help += "\nDefault is to run on data/large.csv."

@click.command()
@click.option('--filename', default='data/large.csv',
              help=datafile_help)
@click.option('--capacity', default=None,
              help="Maximum weight for the container. By default sets to 80% of the total.")
def main(filename, capacity):
    """Solve a knapsack problem using a CQM solver."""

    sampler = LeapHybridCQMSampler(solver="hybrid_constrained_quadratic_model_version1_test")

    costs, weights, capacity = parse_inputs(filename, capacity)

    cqm = build_knapsack_cqm(costs, weights, capacity)

    print("Submitting CQM to solver {}.".format(sampler.solver.name))
    sampleset = sampler.sample_cqm(cqm, label='Example - Knapsack')

    parse_solution(sampleset, costs, weights)

if __name__ == '__main__':
    main()
