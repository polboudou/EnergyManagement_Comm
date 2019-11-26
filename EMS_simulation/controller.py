

import pandas as pd
import paho.mqtt.client as mqtt # import the client
import time
#from EMS_simulation.control_algorithms import scenario1, scenario2, scenario3
from EMS_simulation.control_algorithms import scenario2
broker_address = "mqtt.eclipse.org"  # use external broker


class Controller():
    def __init__(self, description):
        self.description = description
        self.client = self.setup_client()

        if self.description == 'SC1':
            self.Tb1 = 0
            self.pb1 = 0
            self.sb1 = 0
            #self.states = [0]*2     # [T_B1, p_B1]
            #self.states[1] = 0
            self.algorithm = 'scenario1'

    def run_algorithm(self, p_x):
        action = scenario2.algo_scenario2({1: [self.Tb1, self.pb1, self.sb1]}, p_x)
        return action

    def setup_client(self):
        client = mqtt.Client(self.description)
        client.on_connect = on_connect
        client.on_log = on_log
        client.on_disconnect = on_disconnect
        client.on_message = on_message_controller
        client.connect(broker_address)
        client.loop_start()  # without the loop, the call back functions dont get processed
        return client

# callback functions for communication

def on_log(client, userdata, level, buf):
    print("log: ",buf)

def on_connect(client, userdata, flags, rc):
    if rc==0:
        print('connected OK')
    else:
        print('bad connection Returned code=', rc)

def on_disconnect(client, userdata, flags, rc=0):
    print('disconnected')

def on_message_controller(client, userdata, msg):
    message_handler(client, msg)

def message_handler(client, msg):
    if msg.topic == 'boiler_sensor':
        controller.Tb1 = float(msg.payload)
        print('received measurements from boiler 1:', float(msg.payload))


TIME_SLOT = 10  # in minutes
# HORIZON = 20 # in minutes, corresponds to 24 hours
HORIZON = 1440  # in minutes, corresponds to 24 hours

BOILER1_TEMP_MIN = 40  # in degree celsius
BOILER1_TEMP_MAX = 50  # in degree celsius

BOILER2_TEMP_MIN = 30  # in degree celsius
BOILER2_TEMP_MAX = 60  # in degree celsius

BOILER2_TEMP_INCOMING_WATER = 20  # in degree celsius (TODO to be verified!) Question: is it variable?

BOILER1_RATED_P = 7600  # in Watts
BOILER2_RATED_P = 7600  # in Watts

BOILER1_VOLUME = 800  # in litres
BOILER2_VOLUME = 800  # in litres

BOILER1_INITIAL_TEMP = 45  # in degree celsius (TODO would come from the measurements!)
BOILER2_INITIAL_TEMP = 45  # in degree celsius (TODO would come from the measurements)

px = 2000

if __name__ == '__main__':

    print('Instantiating controller!')
    controller = Controller('SC1')
    controller.client.subscribe("boiler_sensor")
    for i in range(2):
        time.sleep(2) # to ensure that all units are instantiated
        controller.client.publish('boiler', 'Request measurement')
        time.sleep(1)
        print('controller.pb1', controller.pb1)
        print('controller.Tb1', controller.Tb1)
        actions = controller.run_algorithm(px)
        controller.client.publish('boiler_actuator', str(actions[1]))

    controller.client.loop_stop()
    controller.client.disconnect(broker_address)
