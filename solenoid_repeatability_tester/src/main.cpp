#include <SD.h>
#include <SPI.h>

// Test Variables (Don't change these)
volatile int endstopCounter = 0;
unsigned long startTime;
unsigned long lastCycleEnd = 0; // When (in millis) did the last test cycle end
unsigned long testCount = 0;    // The current test number
unsigned long passCount = 0;    // The number of passed tests so far
unsigned long failCount = 0;    // The number of failed tests so far
boolean detectedSolenoidOn = 0;
boolean detectedSolenoidOff = 0;
String testStart = "================Test Start===================";
String testEnd = "=================Test End====================";

// Board Configuration
const int solenoidPin = 27; // Pin connected to solenoid
const int endstopPin = 34;  // Pin connected to endstop (must be interrupt-capable pin)
const int chipSelect = 5;   // SD card CS pin

// Solenoid Configuration
const unsigned int solenoidFrequency = 30000;  // pwm frequency for solenoid (Hz)
const unsigned int solenoidPull = 255;         // pwm value for solenoid on (initial pull, max 255)
const unsigned int solenoidHold = 100;         // pwm value for solenoid hold (holding while on, max 255)
const unsigned int solenoidPullDuration = 100; // duration solenoid operates at pull setting

// Test Configuration
const unsigned int solenoidActivationDectectionWindow = 100;   // Time we wait before checking for activation
const unsigned int solenoidDeactivationDectectionWindow = 200; // Time we wait before checking for deactivation (note: this takes longer than activation)

const unsigned int maxOnDuration = 500; // Maximum duration solenoid can stay on during a test in milliseconds
const unsigned int maxInterval = 500;   // Maximum interval between tests in milliseconds
const unsigned int minInterval = 500;    // Minimum interval between tests in milliseconds

unsigned long timeBetweenTests = random(minInterval, maxInterval); // Time between tests

void endstopISR()
{
  endstopCounter++; // Increment the counter in the ISR
}

void logResult(String result)
{
  String testStatus;
  if (result.equals("PASS"))
  {
    passCount++;
    testStatus = "\x1B[92mPASS\x1B[0m";
  }
  else
  {
    failCount++;
    testStatus = "\x1B[91mFAIL\x1B[0m";
  }
  testCount++; // Increment the test count

  // Generate the test summary string
  String testSummary = "Test " + String(testCount) + " " + testStatus + "\nTotal passed (" + String(passCount) + "), total failed (" + String(failCount) + ")";

  // Output test summary to serial
  Serial.println(testSummary);
  Serial.println(testEnd);

  // Log to SD card
  File dataFile = SD.open("/text.txt", FILE_APPEND);
  if (dataFile)
  {
    dataFile.println(testSummary);
    dataFile.close();
  }
  else
  {
    Serial.println("Error opening datalog.txt");
  }
}

void setup()
{
  Serial.begin(115200);
  analogWriteFrequency(solenoidFrequency);
  pinMode(solenoidPin, OUTPUT);
  pinMode(endstopPin, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(endstopPin), endstopISR, FALLING); // Attach interrupt
  if (!SD.begin(chipSelect))
  {
    Serial.println("Card failed, or not present");
    while (1)
      ;
  }
  Serial.println("Card initialized.");
  randomSeed(analogRead(0)); // Seed the random generator with a noise reading

  Serial.println("Solenoid initialization test. Solenoid On for 2 second");
  analogWrite(solenoidPin, solenoidPull);
  delay(2000);
  Serial.println("Solenoid initialization test. Solenoid Off for 2 second");
  analogWrite(solenoidPin, 0);
  delay(2000);
  Serial.println("Solenoid initialization test. Solenoid On for 1 second");
  analogWrite(solenoidPin, solenoidPull);
  delay(1000);
  Serial.println("Solenoid initialization test. Solenoid Off for 1 second");
  analogWrite(solenoidPin, 0);
  delay(1000);
}

void loop()
{
  if (millis() - lastCycleEnd >= timeBetweenTests)
  {

    unsigned long onDuration = random(maxOnDuration); // Generate a random on duration
    Serial.println(testStart);
    Serial.println("Solenoid ON (" + String(onDuration) + " milliseconds)");
    endstopCounter = 0; // Reset end stop counter
    // Solenoid on at pull strength for pull duration
    analogWrite(solenoidPin, solenoidPull);

    // Check that endstop was tirggered at solenoid on
    startTime = millis();
    while (millis() - startTime < solenoidActivationDectectionWindow)
    { // 500 ms timeout for detecting endstop
      if (endstopCounter >= 1)
      { // Check if both pulses are detected
        Serial.println("Detected solenoid activation");
        detectedSolenoidOn = true;
        break;
      }
    }
    endstopCounter = 0; // Reset end stop counter
    // Wait for the pull duration (Should we subtract the detection time? It might not always be the full lenght of time if detection breaks out of the while loop)
    if (solenoidPullDuration - (millis() - startTime) > 0)
    {
      delay(solenoidPullDuration - (millis() - startTime));
      // Solenoid on at pull strength for pull duration less however long we have already waited for endstop detection
      // If this duration is less than 1, we've already waited longer than the pull duration so don't wait any longer
    }

    // Solenoid on at hold strength
    analogWrite(solenoidPin, solenoidHold);
    delay(onDuration);

    endstopCounter = 0; // Reset the endstop counter just to clear any anaomalous readings
    // Solenoid off
    analogWrite(solenoidPin, 0);
    Serial.println("Solenoid OFF");
    startTime = millis();
    while (millis() - startTime < solenoidDeactivationDectectionWindow)
    { // 500 ms timeout for detecting endstop
      if (endstopCounter >= 1)
      { // Check if both pulses are detected
        Serial.println("Detected solenoid de-activation");
        detectedSolenoidOff = true;
        break;
      }
    }
    endstopCounter = 0; // Probably redundant, but just for good measure, clear the endstop counter again

    Serial.println("Detected: Solenoid ON: " + String(detectedSolenoidOn) + " Solenoid OFF: " + String(detectedSolenoidOff) + "");

    if (detectedSolenoidOn & detectedSolenoidOff)
    {
      logResult("PASS");
    }
    else
    {
      logResult("FAIL");
    }

    detectedSolenoidOn = false; // Reset solenoid detection states
    detectedSolenoidOff = false;
    // endstopCounter = 0;                                  // Reset the endstop counter
    timeBetweenTests = random(minInterval, maxInterval); // Generate a new random interval
    lastCycleEnd = millis();                             // Reset time when test ended to now
    Serial.println("\nTest complete. Waiting for " + String(timeBetweenTests) + " milliseconds.\n");
  }
}