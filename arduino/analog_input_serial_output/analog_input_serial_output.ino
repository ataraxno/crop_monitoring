/*
  Analog Input

  Demonstrates analog input by reading an analog sensor on analog pin 0 and
  turning on and off a light emitting diode(LED) connected to digital pin 13.
  The amount of time the LED will be on and off depends on the value obtained
  by analogRead().

  The circuit:
  - potentiometer
    center pin of the potentiometer to the analog input 0
    one side pin (either one) to ground
    the other side pin to +5V
  - LED
    anode (long leg) attached to digital output 13 through 220 ohm resistor
    cathode (short leg) attached to ground

  - Note: because most Arduinos have a built-in LED attached to pin 13 on the
    board, the LED is optional.

  created by David Cuartielles
  modified 30 Aug 2011
  By Tom Igoe

  This example code is in the public domain.

  https://www.arduino.cc/en/Tutorial/BuiltInExamples/AnalogInput
*/

int sensorPinP = A4;    // select the input pin for the potentiometer
int sensorPinN = A5;
int Positive = 0;  // variable to store the value coming from the sensor
int Negative = 0;
float Voltage = 0;
float SensorValue = 0;

float map(float x, float in_min, float in_max, float out_min, float out_max)
{
  return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min;
}

void setup() {
  Serial.begin(115200);
}

void loop() {
  // read the value from the sensor:
  Positive = analogRead(sensorPinP);
  Negative = analogRead(sensorPinN);
  Voltage = map(float(Positive) - float(Negative), 0, 1023, 0, 5);
  SensorValue = Voltage*5000;
  Serial.print(SensorValue);
  Serial.println("W*m-2");
  delay(1000);
}
