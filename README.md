# Semester project: "Energy management strategies for reducing a building’s electricity costs after a PV installation"
This repository contains the material of my semester project at EPFL's Laboratory for Communications and Applications (LCA).

Several control strategies are tested to reduce the electricity bill of a microgrid. Those are tested using a framework that simulates the different microgrid entities (boilers and battery) and the controller. All scripts are coded using Python 3 and can be found in the folder *EMS_simulation*. The different control algorithms are available in *'\EMS_simulation/control_algorithms'*.

When running a simulation, results will go to folder 'EMS_simulation/results_output'.

### To run a simulation, follow the following steps:

1) Download repository
2) Install Python modules 'numpy', 'pandas', 'scipy', 'subprocess' and 'paho'.
3) Run 'simu_process.py'

**Remark:** the simulation needs an internet connection to run. MQTT uses an online broker to exchange messages between entities. 

**Changing control strategy:** The control strategy is to be selected in *controller.py*. If it requires a battery, this needs to be notified in *simulation.py*, by setting *BATTERY = True*. 

**Changing simulation parameters:** Simulation parameters need to be adjusted in each of the modules composing the simulation. For instance, if the control period wants to be set a 10 minutes, it set that way in *controller.py*, but also in entities model (*battery_model.py, boiler1_model.py, boiler2_model.py*).
