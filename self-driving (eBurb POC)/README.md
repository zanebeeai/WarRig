# Self-Driving Software Components

## 1. Perception  
The perception module processes camera data to detect road lines and environmental objects, and steer accordingly.
![Processed front-camera output](processed_output.gif)


*Above: an example of processed front-camera output with direction overlay.*

## 2. Localization & Mapping  
Using camera data, the vehicle determines its precise pose (position + orientation) in the world and aligns itself within mapped road features and lanes.

## 3. Planning & Control  
- **Behavioral planning**: decides *what* the vehicle should do (e.g., steer, stop, accelerate).  
- **Trajectory planning**: computes *how* to execute that behavior (smooth path, velocity profile).  
- **Control**: sends commands to actuators (steering, throttle, brake) to follow the planned trajectory.
  
![External self-driving demonstration](20250612_093538.gif)


*Above: an external view showing the full self-driving loop in action.*

## 5. Safety & Fallbacks  
I did not allow the car to throttle itself because I was scared. My foot controlled the throttle.
---

**Summary**: The self-driving stack (software side) flows from perception → localization/mapping → prediction → planning/control → safety. Each stage depends on the previous, and robustness at every step is key to a reliable autonomous vehicle.
