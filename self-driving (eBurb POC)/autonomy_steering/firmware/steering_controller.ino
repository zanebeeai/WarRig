/*
 * Steering Controller Firmware
 * 
 * Receives steering commands from host via serial (JSON)
 * Controls DC motor via PID loop using encoder feedback
 * Sends label frames with encoder position and killswitch status
 * 
 * Hardware:
 * - Quadrature encoder on steering (pins ENC_A, ENC_B)
 * - DC motor controller (pins MOTOR_PWM, MOTOR_DIR)
 * - Killswitch input (pin KILLSWITCH_PIN)
 * 
 * Protocol:
 * - Receives: {"t_ms_host": int, "theta_cmd": float, "mode": "bench", "arm_token": string, "seq": int}
 * - Sends: {"t_us": int, "enc_counts": int, "steer_angle_deg": float, "killswitch_ok": bool, "seq": int}
 */

#include <ArduinoJson.h>

// Pin definitions - adjust for your hardware
#define ENC_A 2          // Encoder channel A (interrupt pin)
#define ENC_B 3          // Encoder channel B
#define MOTOR_PWM 9      // Motor PWM control
#define MOTOR_DIR 8      // Motor direction (HIGH/LOW)
#define KILLSWITCH_PIN 4 // Killswitch input (LOW = safe, HIGH = armed)

// Calibration constants - match configs/system.yaml
#define COUNTS_PER_REV 1024
#define GEAR_RATIO 1.0
#define STEERING_RANGE_DEG 50.0
#define ZERO_OFFSET_COUNTS 0

// PID constants
#define PID_KP 2.0
#define PID_KI 0.1
#define PID_KD 0.5
#define PID_OUTPUT_LIMIT 255

// Timing
#define LABEL_HZ 100
#define LABEL_INTERVAL_US (1000000 / LABEL_HZ)
#define COMMAND_TIMEOUT_MS 500

// Global state
volatile long encoder_count = 0;
long last_encoder_count = 0;
unsigned long last_label_us = 0;
unsigned long last_command_ms = 0;
int label_seq = 0;
bool killswitch_ok = false;
String current_arm_token = "";
unsigned long arm_token_timeout_ms = 0;
bool armed = false;
String current_mode = "";

// PID state
float pid_setpoint = 0.0;
float pid_error = 0.0;
float pid_integral = 0.0;
float pid_last_error = 0.0;

// Encoder ISR
void encoderISR() {
  int a = digitalRead(ENC_A);
  int b = digitalRead(ENC_B);
  if (a == b) {
    encoder_count++;
  } else {
    encoder_count--;
  }
}

// Convert encoder counts to degrees
float counts_to_degrees(long counts) {
  float counts_per_deg = (COUNTS_PER_REV * GEAR_RATIO) / 360.0;
  float deg = (counts - ZERO_OFFSET_COUNTS) / counts_per_deg;
  return deg;
}

// PID control
int computePID(float setpoint, float current) {
  pid_error = setpoint - current;
  
  // Proportional
  float p_term = PID_KP * pid_error;
  
  // Integral
  pid_integral += pid_error;
  pid_integral = constrain(pid_integral, -100.0, 100.0); // Anti-windup
  float i_term = PID_KI * pid_integral;
  
  // Derivative
  float d_term = PID_KD * (pid_error - pid_last_error);
  pid_last_error = pid_error;
  
  // Compute output
  float output = p_term + i_term + d_term;
  output = constrain(output, -PID_OUTPUT_LIMIT, PID_OUTPUT_LIMIT);
  
  return (int)output;
}

// Control motor
void setMotor(int pwm_value) {
  pwm_value = constrain(pwm_value, -PID_OUTPUT_LIMIT, PID_OUTPUT_LIMIT);
  
  if (pwm_value == 0 || !armed || !killswitch_ok) {
    analogWrite(MOTOR_PWM, 0);
    return;
  }
  
  if (pwm_value > 0) {
    digitalWrite(MOTOR_DIR, HIGH);
    analogWrite(MOTOR_PWM, pwm_value);
  } else {
    digitalWrite(MOTOR_DIR, LOW);
    analogWrite(MOTOR_PWM, -pwm_value);
  }
}

// Send label frame
void sendLabelFrame() {
  unsigned long t_us = micros();
  long counts = encoder_count;
  float angle_deg = counts_to_degrees(counts);
  
  // Read killswitch (inverted: LOW = safe, HIGH = armed)
  killswitch_ok = digitalRead(KILLSWITCH_PIN) == HIGH;
  
  StaticJsonDocument<200> doc;
  doc["t_us"] = t_us;
  doc["enc_counts"] = counts;
  doc["steer_angle_deg"] = angle_deg;
  doc["killswitch_ok"] = killswitch_ok;
  doc["seq"] = label_seq++;
  
  serializeJson(doc, Serial);
  Serial.println();
}

// Process incoming command
void processCommand(String line) {
  StaticJsonDocument<200> doc;
  DeserializationError error = deserializeJson(doc, line);
  
  if (error) {
    return; // Invalid JSON
  }
  
  // Validate required fields
  if (!doc.containsKey("mode") || !doc.containsKey("arm_token") || 
      !doc.containsKey("theta_cmd") || !doc.containsKey("seq")) {
    return;
  }
  
  String mode = doc["mode"].as<String>();
  String token = doc["arm_token"].as<String>();
  float theta_cmd = doc["theta_cmd"];
  int seq = doc["seq"];
  
  // Only accept bench mode commands
  if (mode != "bench") {
    return;
  }
  
  // Validate arm token
  // If no token set yet, accept first valid token (starts with "ARM")
  if (current_arm_token.length() == 0) {
    if (token.startsWith("ARM")) {
      current_arm_token = token;
      arm_token_timeout_ms = millis() + 3000; // 3 second timeout
    } else {
      return; // Invalid token format
    }
  }
  
  // Check if token matches
  if (token != current_arm_token) {
    armed = false;
    return;
  }
  
  // Check token timeout (3 seconds default)
  if (millis() > arm_token_timeout_ms) {
    armed = false;
    current_arm_token = ""; // Reset token
    return;
  }
  
  // Arm if token is valid
  armed = true;
  current_mode = mode;
  last_command_ms = millis();
  
  // Set PID setpoint
  theta_cmd = constrain(theta_cmd, -STEERING_RANGE_DEG, STEERING_RANGE_DEG);
  pid_setpoint = theta_cmd;
}

void setup() {
  Serial.begin(115200);
  
  // Configure pins
  pinMode(ENC_A, INPUT_PULLUP);
  pinMode(ENC_B, INPUT_PULLUP);
  pinMode(MOTOR_PWM, OUTPUT);
  pinMode(MOTOR_DIR, OUTPUT);
  pinMode(KILLSWITCH_PIN, INPUT_PULLUP);
  
  // Attach encoder interrupt
  attachInterrupt(digitalPinToInterrupt(ENC_A), encoderISR, CHANGE);
  
  // Initialize motor to stopped
  analogWrite(MOTOR_PWM, 0);
  digitalWrite(MOTOR_DIR, LOW);
  
  // Initialize timing
  last_label_us = micros();
  last_command_ms = millis();
  
  // Wait for serial (optional, for debugging)
  // while (!Serial) { delay(10); }
}

void loop() {
  unsigned long now_us = micros();
  unsigned long now_ms = millis();
  
  // Send label frames at configured rate
  if (now_us - last_label_us >= LABEL_INTERVAL_US) {
    sendLabelFrame();
    last_label_us = now_us;
  }
  
  // Read incoming commands
  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    if (line.length() > 0) {
      processCommand(line);
    }
  }
  
  // Safety: disarm if no command received for timeout period
  if (armed && (now_ms - last_command_ms > COMMAND_TIMEOUT_MS)) {
    armed = false;
    pid_integral = 0.0; // Reset integral on disarm
  }
  
  // Safety: stop motor if killswitch is not OK
  if (!killswitch_ok && armed) {
    armed = false;
    pid_integral = 0.0;
  }
  
  // Run PID control loop
  if (armed && killswitch_ok) {
    float current_angle = counts_to_degrees(encoder_count);
    int motor_output = computePID(pid_setpoint, current_angle);
    setMotor(motor_output);
  } else {
    // Disarmed or killswitch active - stop motor
    setMotor(0);
    pid_integral = 0.0; // Reset integral
  }
  
  // Small delay to prevent watchdog issues
  delayMicroseconds(100);
}
