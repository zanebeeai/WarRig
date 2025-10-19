# Self-Driving Software Components

## 1. Perception  
The perception module processes sensor data (e.g., camera, LiDAR) to detect and track objects in the environment: vehicles, pedestrians, traffic signs, lanes.  
![Processed front-camera output](https://i.imgur.com/Ineczy4.gif)
*Above: an example of processed front-camera output with object/lane overlay.*

## 2. Localization & Mapping  
Using sensor data plus pre-built maps, the vehicle determines its precise pose (position + orientation) in the world and aligns itself within mapped road features and lanes.

## 3. Prediction  
Once objects are detected and tracked, the system predicts their future motion (e.g., trajectories of other vehicles or pedestrians) to anticipate possible hazards and plan accordingly.

## 4. Planning & Control  
- **Behavioral planning**: decides *what* the vehicle should do (e.g., change lane, stop, yield).  
- **Trajectory planning**: computes *how* to execute that behavior (smooth path, velocity profile).  
- **Control**: sends commands to actuators (steering, throttle, brake) to follow the planned trajectory.  
![External self-driving demonstration](https://i.imgur.com/VVo0bRY.mp4)  
*Above: an external view showing the full self-driving loop in action.*

## 5. Safety & Fallbacks  
Safety modules monitor system health, detect anomalies (e.g., sensor failure, unexpected object behaviour) and trigger fallback actions or safe-stop maneuvers. Continuous validation and redundancy are crucial.

---

**Summary**: The self-driving stack (software side) flows from perception → localization/mapping → prediction → planning/control → safety. Each stage depends on the previous, and robustness at every step is key to a reliable autonomous vehicle.
