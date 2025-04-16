import os
import threading
import time
import create_topology
import visualize_topology  
from visualize_topology import start_visualization_thread

# Global path to the running network CSV
RUNNING_NETWORK_PATH = '/home/vagrant/next_gen_network_slicing/data/running_network.csv'

def main():

    start_visualization_thread(RUNNING_NETWORK_PATH)

    user_input = input("Press 'r' to create a random network or insert the path to a CSV file: ").strip()
    
    if user_input.lower() == "r":
        create_topology.create_random_network(RUNNING_NETWORK_PATH)
    elif os.path.isfile(user_input):
        create_topology.load_from_csv(user_input, RUNNING_NETWORK_PATH)
    else:
        print("Invalid input. Please enter 'r' or a valid file path.")
        return  # Stop early if invalid input


if __name__ == "__main__":
    main()
