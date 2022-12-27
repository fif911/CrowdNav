# CrowdNav

![Banner](https://raw.githubusercontent.com/Starofall/CrowdNav/master/banner.PNG)


### Description
CrowdNav is a simulation based on SUMO and TraCI that implements a custom router
that can be configured using kafka messages or local JSON config on the fly while the simulation is running.
Also runtime data is send to a kafka queue to allow stream processing and logger locally to CSV.

### Version requirements
* Python version = 2.7 (tested for v2.7)
* SUMO version = 1.14.1 (tested for v1.14.1)

### Minimal Setup
* Download the CrowdNav code
* Run `python setup.py install` to download all dependencies 
* Install [SUMO](https://sumo.dlr.de/docs/Installing.html) & set environment variable SUMO_HOME to point to SUMO installation folder
* Install [Kafka](https://kafka.apache.org/) (we recommend [this](https://hub.docker.com/r/spotify/kafka/) Docker image) and set kafkaHost in Config.py
* Run `python run.py`

### Getting Started Guide
A first guide on how to use (i.e. adapt, measure, optimize) CrowdNav with the [RTX tool](https://github.com/Starofall/RTX) is available at this [Wiki page](https://github.com/Starofall/RTX/wiki/RTX-&-CrowdNav-Getting-Started-Guide). 

### Operational Modes

* Normal mode (`python run.py`) with UI to Debug the application. Runs forever.
* Parallel mode (`python parallel.py n`) to let n processes of SUMO spawn for faster data generation.
  Stops after 10k ticks and reports values.
  
### Further customization

* Runtime variables are in the knobs.json file and will only be used if `kafkaUpdates = True
` is set to false in `Config.py`. Else the tool uses Kafka for value changes.
* To disable the UI in normal mode, change the `sumoUseGUI = True` value in `Config.py` to false.

### Notes

* To let the system stabalize, no message is sent to kafka or CSV in the first 1000 ticks .

### PID

* A PID Controller is set in `PID.py` to lower the amount of delay and overshoot. In the code, proportional, integral and derivative are calculated seperatly using existing error and history data.

      def calculate(self, err, hist, derivative):
          return self.P * err + \
                 self.I * sum(hist) / (len(hist) * 1.0 if self.normalized else 1.0) + \
                 self.D * derivative

      def update(self, P, I, D):
          self.P = P
          self.I = I
          self.D = D
          
### Simulation

* PID controller is used in `Simulation.py`. The simulation start from time tick 0 and keeps coolecting values of each parameters, in every loop we decide whether to add/remove cars and how many cars to add/remove. If the actual arrived cars are less than the PID controller's expectation, we add cars, otherwise we remove cars. This simulation reports current status to Kafka every 30 ticks and print status update every 100 ticks if current running mode is not parallel.

      if (cls.tick % 100) == 0 and Config.parallelMode is False:
                print(str(Config.processID) + " -> Step:" + str(cls.tick) + " # Driving cars: " + str(
                    traci.vehicle.getIDCount()) + "/" + str(
                    CarRegistry.totalCarCounter) + " # avgTripDuration: " + str(
                    CarRegistry.totalTripAverage) + "(" + str(
                    CarRegistry.totalTrips) + ")" + " # avgTripOverhead: " + str(
                    CarRegistry.totalTripOverheadAverage))
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
* Note that the smart cars are controlled by CrowdNav routing algorithm, the normal cars are driving in some random routes to simulate the real-world traffic
