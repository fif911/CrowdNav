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
    # For traffic seasonality simulation:
    # determines if car that arrived will be respawned if graceful decrease in amount of cars needed
    CarDegradationFactor = 0.3  # (for traffic seasonality simulation) # TODO: Implement in code. Now is not used
    # Defines how many ticks it takes to migrate from current amount of cars to a new one
    CarMigrationTicksAmount = 400  # TODO: Implement in code. Now is not used
    SmartCarsAverageSpeed = 0

    # @todo on shortest path possible -> minimal value

    @classmethod
    def applyCarCounter(cls):
        """ syncs the value of the carCounter to the SUMO simulation """
        while len(CarRegistry.cars) < cls.totalCarCounter:
            # to less cars -> add new
            cls.carIndexCounter += 1
            c = Car("car-" + str(CarRegistry.carIndexCounter))
            cls.cars[c.id] = c
            c.addToSimulation(0)
        while len(CarRegistry.cars) > cls.totalCarCounter:
            # to many cars -> remove cars
            print("Too many cars (" + str(len(CarRegistry.cars)) + "), removing ...")
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
        smart_cars_speeds = []

        for key in CarRegistry.cars:
            CarRegistry.cars[key].processTick(tick)
            # print('key: ' + str(key))

            if (tick % 30) == 0 and CarRegistry.cars[key].smartCar:
                smart_cars_speeds.append(traci.vehicle.getSpeed(key))

        if (tick % 30) == 0:
            smart_cars_speeds = [i if i > 1 else 1 for i in smart_cars_speeds]
            cls.SmartCarsAverageSpeed = stats.hmean(smart_cars_speeds)
            #print(cls.SmartCarsAverageSpeed)