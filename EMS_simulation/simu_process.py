#!/usr/bin/env python3

import subprocess

scenario = 'MPCbattery'
#scenario = 'MPCboilers'

# simulation parameters as well as load parameters need to be changed in each entity process

if __name__ == '__main__':

    print('Starting simulation!')

    if scenario == 'Scenario2' or scenario == 'MPCbattery':
        subprocess.run("python3 controller.py & python3 boiler1_model.py & python3 boiler2_model.py & python3 battery_model.py", shell=True)
    else:
        subprocess.run("python3 controller.py & python3 boiler1_model.py & python3 boiler2_model.py", shell=True)
