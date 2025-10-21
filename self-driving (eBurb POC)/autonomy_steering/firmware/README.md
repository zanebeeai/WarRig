# Steering Controller Firmware

Arduino firmware for receiving steering commands and controlling a DC motor via PID loop with encoder feedback.

## Hardware Requirements

- Arduino-compatible board (Uno, Nano, Mega, etc.)
- Quadrature encoder on steering mechanism
- DC motor controller (H-bridge or similar)
- Killswitch (normally-open switch, closes when safe)

## Pin Configuration

Default pin assignments (modify in `steering_controller.ino` if needed):

- `ENC_A` (pin 2): Encoder channel A (must be interrupt-capable)
- `ENC_B` (pin 3): Encoder channel B
- `MOTOR_PWM` (pin 9): Motor PWM control
- `MOTOR_DIR` (pin 8): Motor direction control
- `KILLSWITCH_PIN` (pin 4): Killswitch input (LOW = safe, HIGH = armed)

## Calibration

Update these constants in the firmware to match `configs/system.yaml`:

- `COUNTS_PER_REV`: Encoder counts per full revolution
- `GEAR_RATIO`: Gear ratio between encoder and steering
- `STEERING_RANGE_DEG`: Maximum steering angle in degrees (±)
- `ZERO_OFFSET_COUNTS`: Encoder count at center/zero steering position

## PID Tuning

Adjust PID constants for your motor/load characteristics:

- `PID_KP`: Proportional gain
- `PID_KI`: Integral gain
- `PID_KD`: Derivative gain

## Protocol

### Receives (from host):
```json
{
  "t_ms_host": 1234567890,
  "theta_cmd": 15.5,
  "mode": "bench",
  "arm_token": "ARM1234567890",
  "seq": 42
}
```

### Sends (to host):
```json
{
  "t_us": 1234567890123,
  "enc_counts": 5120,
  "steer_angle_deg": 12.5,
  "killswitch_ok": true,
  "seq": 100
}
```

## Safety Features

1. **Arm Token**: Commands are only accepted with valid arm token
2. **Killswitch**: Motor stops immediately if killswitch is not active
3. **Command Timeout**: Disarms if no command received for 500ms
4. **Token Timeout**: Arm token expires after 3 seconds (must be refreshed)

## Installation

1. Install Arduino IDE
2. Install `ArduinoJson` library (version 6.x)
3. Open `steering_controller.ino`
4. Adjust pin definitions and calibration constants
5. Upload to Arduino
6. Connect serial at 115200 baud

## Testing

The firmware will start sending label frames immediately at 100Hz. To test motor control:

1. Ensure killswitch is active (HIGH)
2. Send steering command via serial with valid arm token
3. Motor should respond to reach commanded angle
4. Monitor encoder feedback in label frames
