import numpy as np
import traci
from scipy import stats

from app import Config

from app.entitiy.Car import Car


class NullCar:
    """ a car with no function used for error prevention """

    def __init__(self):
        pass

    def setArrived(self, tick, despawn=False):
        pass


class CarRegistry(object):
    """ central registry for all our cars we have in the sumo simulation """

    # the total amount of cars that should be in the system
    totalCarCounter = Config.totalCarCounter
    # always increasing counter for carIDs
    carIndexCounter = 0
    # list of all cars
    cars = {}  # type: dict[str,app.entitiy.Car]
    # counts the number of finished trips
    totalTrips = 0
    # average of all trip durations
    totalTripAverage = 0
    # average of all trip overheads (overhead is TotalTicks/PredictedTicks)
    totalTripOverheadAverage = 0

    # Traffic seasonality simulation variables:
    # For analysis only
    _SmartCarsAverageSpeedH = 0
    _SmartCarsAverageSpeedA = 0
    _CarsAverageSpeedH = 0
    _CarsAverageSpeedA = 0

    @classmethod
    def applyCarCounter(cls):
        """ syncs the value of the carCounter to the SUMO simulation immediately """
        while len(CarRegistry.cars) < cls.totalCarCounter:
            # to less cars -> add new
            cls.carIndexCounter += 1
            c = Car("car-" + str(CarRegistry.carIndexCounter))
            cls.cars[c.id] = c
            c.addToSimulation(0)
        while len(CarRegistry.cars) > cls.totalCarCounter:
            # to many cars -> remove cars
            # print("Too many cars (" + str(len(CarRegistry.cars)) + "), removing ...")
            (k, v) = CarRegistry.cars.popitem()
            v.remove()

    @classmethod
    def addCar(cls):
        cls.carIndexCounter += 1
        c = Car("car-" + str(CarRegistry.carIndexCounter))
        cls.cars[c.id] = c
        c.addToSimulation(0)

    @classmethod
    def findById(cls, carID):
        """ returns a car by a given carID """
        try:
            return CarRegistry.cars[carID]  # type: app.entitiy.Car
        except:
            return NullCar()

    @classmethod
    def processTick(cls, tick):
        """ processes the simulation tick on all registered cars """
        # if (tick % 30) == 0:
        cars_speeds = []
        smart_cars_speeds = []

        for key in CarRegistry.cars:
            CarRegistry.cars[key].processTick(tick)

            if (tick % 30) == 0:
                cars_speeds.append(traci.vehicle.getSpeed(key))
                if CarRegistry.cars[key].smartCar:
                    smart_cars_speeds.append(traci.vehicle.getSpeed(key))

        if (tick % 30) == 0:
            cars_speeds = [i if i > 1 else 1 for i in cars_speeds]
            smart_cars_speeds = [i if i > 1 else 1 for i in smart_cars_speeds]
            cls._SmartCarsAverageSpeedA = np.mean(smart_cars_speeds)
            cls._SmartCarsAverageSpeedH = stats.hmean(smart_cars_speeds)
            cls._CarsAverageSpeedH = np.mean(cars_speeds)
            cls._CarsAverageSpeedA = stats.hmean(cars_speeds)
