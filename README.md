# next_gen_network_slicing
unitn project for next generetation networks year 24/25

Project Components:

    Network Topology Creation:

        Implement a method to programmatically generate a dense network topology composed of SDN switches and host nodes.

        Each link between switches and nodes should be assigned a specific capacity (in Mbps) at the time of network creation.

        The topology can be generated either:

            Randomly using a Python script (e.g., using Mininet),

            Or by loading a predefined topology file (e.g., JSON, YAML, or GraphML format).

        Nodes (hosts) should be clearly distinguished from switches in the topology structure.

    Link Capacity Management:

        During network initialization, assign explicit capacities (e.g., 10 Mbps, 50 Mbps, etc.) to each link.

        Maintain and dynamically update the residual capacity of each link as flows are allocated or removed.

    Flow Request and Allocation System:

        Create a software interface (CLI or GUI) through which users can submit requests for bandwidth allocation (e.g., "allocate a 1 Mbps flow from host A to host B").

        Upon receiving a request:

            Check the current residual capacity along the selected path between the source and destination hosts.

            If sufficient bandwidth is available on all links along the path, approve the flow:

                Allocate the flow by updating flow tables (e.g., through an SDN controller like Ryu or POX).

                Deduct the flow's bandwidth from the residual capacity of each link along the path.

            If the requested bandwidth exceeds available capacity on any link, reject the flow and notify the user with an appropriate error message.

    Flow Table Integration:

        Ensure that the allocated flows are reflected in the flow tables of the respective SDN switches using standard SDN protocols (e.g., OpenFlow).

        Dynamically update flow rules to reflect current network status and active flows.

    Performance Measurement and Validation:

        Use iperf to perform bandwidth measurements between source and destination nodes.

        Demonstrate the system's ability to enforce network slicing by conducting experiments in two scenarios:

            With your custom flow allocation logic, enforcing link capacity constraints.

            Without allocation control, where all flow requests are accepted regardless of capacity (naive approach).

        Collect performance metrics such as:

            Actual throughput achieved,

            Packet loss,

            Flow rejection rates,

            Link utilization.

    Visualization and Reporting:

        Plot comparative graphs (e.g., matplotlib in Python) to illustrate:

            Differences in performance between the controlled and naive allocation methods.

            Residual capacity over time,

            Number of successful vs. rejected flows,

            Impact on throughput and congestion.


```text
Project structure:


next_gen_sdn_project/
├── main.py                      # Main starting script
│                                # - Offers options to randomly generate or load topology from CSV
│
|
├── create_topology.py           # Topology builder module
│                                # - Creates random or fixed network topologies
│                                # - Defines switches, hosts, and link capacities
│                                # - will use CSV file as database
|
│
├── visualize_topology.py        # Network visualization tool
|                                # - GUI to visulize the network layout and link capacities                               
│
|
├── allocate_resources.py        # Smart allocator
│                                # - Allocates flows using Dijkstra or k-Yen’s algorithm
│                                # - Checks for residual capacity along the path if using Yen
│                                # - Updates link residuals upon success
│
├── always_allocate_resources.py # Naive allocator
│                                # - Allocates all flows regardless of capacity
│                                # - Used to simulate network congestion scenarios
│
├── update_gui.py                # GUI updater (or main GUI module)
│                                # - Updates visual representation of the network
│                                # - Shows flow results if sucessful
│                                
│
├── run_iperf_tests.py           # Iperf automation script
│                                # - Starts iperf servers/clients between host pairs
│                                # - Runs performance tests for both allocation methods
│                                # - Collects raw iperf output (text or JSON)
│
├── metrics.py                   # Metrics processor
│                                # - Parses iperf output
│                                # - Computes average throughput, latency, packet loss
│                                # - Prepares clean datasets for plotting
│
├── plot_results.py              # Graph plotting script
│                                # - Visualizes performance comparison
│                                # - Generates bar/line charts using matplotlib/seaborn
│                                # - Can plot rejected vs accepted flows, throughput drop, etc.
│
├── data/                        # Static and runtime data
│   ├── topology.csv             # - Node/link definitions with capacities
│   ├── flows.csv                # - List of flow requests (source, destination, bandwidth)
│   └── iperf_results.csv        # - Collected iperf test results for analysis
│
└── README.md                    # Project documentation
                                 # - Explains project goals, usage instructions
                                 # - How to run tests, allocate flows, and interpret results
```