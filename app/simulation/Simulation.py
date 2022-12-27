import json
import random
from pprint import pprint

import traci
import traci.constants as tc
from app.network.Network import Network

from app.streaming import RTXForword
from colorama import Fore

from app import Config
from app.entitiy.CarRegistry import CarRegistry
from app.logging import info
from app.routing.CustomRouter import CustomRouter
from app.streaming import RTXConnector
from app.simulation.PID import PID
import time
import collections

# get the current system time
from app.routing.RoutingEdge import RoutingEdge

current_milli_time = lambda: int(round(time.time() * 1000))

BASE_DELAY = 100


class Simulation(object):
    """ here we run the simulation in """
    # history length
    historyLength = 300

    # the current tick of the simulation
    tick = 0

    # last tick time
    lastTick = current_milli_time()

    @classmethod
    def applyFileConfig(cls):
        """ reads configs from a json and applies it at realtime to the simulation """
        try:
            config = json.load(open('./knobs.json'))
            CustomRouter.explorationPercentage = config['explorationPercentage']
            CustomRouter.averageEdgeDurationFactor = config['averageEdgeDurationFactor']
            CustomRouter.maxSpeedAndLengthFactor = config['maxSpeedAndLengthFactor']
            CustomRouter.freshnessUpdateFactor = config['freshnessUpdateFactor']
            CustomRouter.freshnessCutOffValue = config['freshnessCutOffValue']
            CustomRouter.reRouteEveryTicks = config['reRouteEveryTicks']
        except:
            pass

    @classmethod
    def start(cls):
        """ start the simulation """
        info("# Start adding initial cars to the simulation", Fore.MAGENTA)
        # apply the configuration from the json file
        cls.applyFileConfig()
        CarRegistry.applyCarCounter()
        print("Total car counter: " + str(CarRegistry.totalCarCounter))
        cls.loop()

    @classmethod
    # @profile
    def loop(cls):
        """ loops the simulation """
        print("Total car counter: " + str(CarRegistry.totalCarCounter))
        delay = BASE_DELAY
        P, I, D = 1 / (0.2 * delay), 1 / (0.2 * delay), 1 / (0.2 * delay)
        pid = PID(P, I, D, normalize=True)
        remapper = lambda u: int(round(u))
        errorHistory = collections.deque(maxlen=cls.historyLength)

        # start listening to all cars that arrived at their target
        traci.simulation.subscribe((tc.VAR_ARRIVED_VEHICLES_IDS,))
        while 1:
            # print("Total car counter: " + str(CarRegistry.totalCarCounter))

            # Do one simulation step
            cls.tick += 1
            traci.simulationStep()

            # Log tick duration to kafka
            duration = current_milli_time() - cls.lastTick
            cls.lastTick = current_milli_time()
            msg = dict()
            msg["duration"] = duration
            RTXForword.publish(msg, Config.kafkaTopicPerformance)  # TODO

            current = len(CarRegistry.cars)
            target = CarRegistry.totalCarCounter
            error = current - target
            delta = error - errorHistory[-1] if errorHistory else 0
            errorHistory.append(error)
            u = pid.calculate(error, errorHistory, delta)
            delta = remapper(u)

            if error != 0 and delta == 0:
                delay = max(delay - 1, 1)
            else:
                delay = BASE_DELAY

            removedList = list(traci.simulation.getSubscriptionResults()[122])
            # p =
            # if delta > 0:
            p = delta / len(removedList) if len(removedList) > 0 else 1

            # Check for removed cars and re-add them into the system
            for removedCarId in removedList:
                despawn = random.random() < p
                CarRegistry.findById(removedCarId).setArrived(cls.tick, despawn)

            if p > 1:
                # we have to remove more cars then there have been arivals
                delay = max(delay - 1, 1)
                delta_to_nuke = delta - len(removedList)
                for _ in range(delta_to_nuke):
                    _, removedCarId = CarRegistry.cars.popitem()
                    CarRegistry.findById(removedCarId).setArrived(cls.tick, despawn=True)

            timeBeforeCarProcess = current_milli_time()
            # let the cars process this step
            CarRegistry.processTick(cls.tick)
            # log time it takes for routing
            msg = dict()
            msg["duration"] = current_milli_time() - timeBeforeCarProcess
            RTXForword.publish(msg, Config.kafkaTopicRouting)  # TODO

            # if we enable this we get debug information in the sumo-gui using global traveltime
            # should not be used for normal running, just for debugging
            # if (cls.tick % 10) == 0:
            # for e in Network.routingEdges:
            # 1)     traci.edge.adaptTraveltime(e.id, 100*e.averageDuration/e.predictedDuration)
            #     traci.edge.adaptTraveltime(e.id, e.averageDuration)
            # 3)     traci.edge.adaptTraveltime(e.id, (cls.tick-e.lastDurationUpdateTick)) # how old the data is

            # print("current cars: " + str(len(CarRegistry.cars)) + "; Target cars: " + str(CarRegistry.totalCarCounter))
            # print("Delta: " + str(delta))
            # print("U: " + str(u))
            # print("Error: " + str(error))
            # print("Delay: " + str(delay))

            if delta < 0:
                # Graceful addition of cars needed
                # calculate how much cars we want to add on this tick
                for ca in range(0, abs(delta)):
                    CarRegistry.addCar()  # adds one car to the simulation

            # real time update of config if we are not in kafka mode
            if (cls.tick % 10) == 0:
                if Config.kafkaUpdates is False and Config.mqttUpdates is False:
                    # json mode
                    cls.applyFileConfig()
                else:
                    # kafka mode
                    newConf = RTXConnector.checkForNewConfiguration()
                    if newConf is not None:
                        # print("New config received through Kafka")
                        # print(newConf)
                        if "exploration_percentage" in newConf:
                            CustomRouter.explorationPercentage = newConf["exploration_percentage"]
                            print("setting victimsPercentage: " + str(newConf["exploration_percentage"]))
                        if "route_random_sigma" in newConf:
                            CustomRouter.routeRandomSigma = newConf["route_random_sigma"]
                            print("setting routeRandomSigma: " + str(newConf["route_random_sigma"]))
                        if "max_speed_and_length_factor" in newConf:
                            CustomRouter.maxSpeedAndLengthFactor = newConf["max_speed_and_length_factor"]
                            print("setting maxSpeedAndLengthFactor: " + str(newConf["max_speed_and_length_factor"]))
                        if "average_edge_duration_factor" in newConf:
                            CustomRouter.averageEdgeDurationFactor = newConf["average_edge_duration_factor"]
                            print("setting averageEdgeDurationFactor: " + str(newConf["average_edge_duration_factor"]))
                        if "freshness_update_factor" in newConf:
                            CustomRouter.freshnessUpdateFactor = newConf["freshness_update_factor"]
                            print("setting freshnessUpdateFactor: " + str(newConf["freshness_update_factor"]))
                        if "freshness_cut_off_value" in newConf:
                            CustomRouter.freshnessCutOffValue = newConf["freshness_cut_off_value"]
                            print("setting freshnessCutOffValue: " + str(newConf["freshness_cut_off_value"]))
                        if "re_route_every_ticks" in newConf:
                            CustomRouter.reRouteEveryTicks = newConf["re_route_every_ticks"]
                            print("setting reRouteEveryTicks: " + str(newConf["re_route_every_ticks"]))
                        if "total_car_counter" in newConf:
                            CarRegistry.totalCarCounter = newConf["total_car_counter"]
                            print("setting totalCarCounter: " + str(newConf["total_car_counter"]))
                        if "car_counter_is_initial" in newConf:
                            if newConf["car_counter_is_initial"] is True \
                                    or newConf["car_counter_is_initial"] == 'true':
                                CarRegistry.applyCarCounter()
                                print("Car counter is initial - call apply: " + str(newConf["total_car_counter"]))
                        if "car_degradation_factor" in newConf:
                            CarRegistry.CarDegradationFactor = newConf["car_degradation_factor"]
                            print("setting CarDegradationFactor: " + str(newConf["car_degradation_factor"]))
                        if "car_migration_ticks_amount" in newConf:
                            CarRegistry.CarMigrationTicksAmount = newConf["car_migration_ticks_amount"]
                            print("setting CarMigrationTicksAmount: " + str(newConf["car_migration_ticks_amount"]))
                        if "edge_average_influence" in newConf:
                            RoutingEdge.edgeAverageInfluence = newConf["edge_average_influence"]
                            print("setting edgeAverageInfluence: " + str(newConf["edge_average_influence"]))
                        # print("New Config set successfully")
            # print status update if we are not running in parallel mode
            if (cls.tick % 100) == 0 and Config.parallelMode is False:
                # #print(str(Config.processID) + " -> Step:" + str(cls.tick) + " # Driving cars: " + str(
                #     traci.vehicle.getIDCount()) + "/" + str(
                #     CarRegistry.totalCarCounter) + " # avgTripDuration: " + str(
                #     CarRegistry.totalTripAverage) + "(" + str(
                #     CarRegistry.totalTrips) + ")" + " # avgTripOverhead: " + str(
                #     CarRegistry.totalTripOverheadAverage))
                pass

            if (cls.tick % 30) == 0:
                # log to kafka on every 30 ticks to kafkaTopicTick

                msg = {
                    'tick': cls.tick,
                    'traffic_volume': len(CarRegistry.cars),
                    'traffic_target': CarRegistry.totalCarCounter,
                    'smart_average_speed_h': CarRegistry._SmartCarsAverageSpeedH,
                    'smart_average_speed_a': CarRegistry._SmartCarsAverageSpeedA,
                    'average_speed_h': CarRegistry._CarsAverageSpeedH,
                    'average_speed_a': CarRegistry._CarsAverageSpeedA,
                }
                RTXForword.publish(msg, Config.kafkaTopicTick)

            if len(CarRegistry.cars) == 0:
                """This is fool-proof strategy in case simulation in RTX with 0 cars is created"""
                print("send log to kafka")
                # log to kafka, empty message
                msg = dict()
                msg["tick"] = cls.tick
                msg["overhead"] = 1
                msg["complaint"] = 0
                RTXForword.publish(msg, Config.kafkaTopicTrips)
