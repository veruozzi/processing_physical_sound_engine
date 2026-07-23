void oscEvent(OscMessage msg) {
  String pattern = msg.addrPattern();
  switch(pattern) {
    //case "/msgTrigger":
    //  triggerText = msg.get(0).stringValue();
    //  println("received trigger msg::" + triggerText);
    //  showText = true;  // Enable the text to be displayed
    //  textTimer = millis();  // Reset the timer
    //  break;
           
    case "/magnitudeMultipleToggle":
        // Safely handle mismatched argument / driver counts and malformed values
        int nArgs = msg.arguments().length;
        int nDrivers = driversList.size();
        if (nArgs != nDrivers) {
          println("⚠️ /magnitudeMultipleToggle: arg count (" + nArgs + ") != driver count (" + nDrivers + ") — clamping to minimum");
        }
        int n = min(nArgs, nDrivers);
        for (int k = 0; k < n; k++) {
          try {
            float excF = msg.get(k).floatValue(); 
            Driver3D dr = (Driver3D) driversList.get(k);
            if (dr != null) {
              // apply force as a 3D vector (x,y,z)
              dr.applyFrc(new Vect3D(0, 0, excF));
              println("playing driver: "+dr+" with received value: " + excF);
            }
          } catch (Exception e) {
            println("Error handling /magnitudeMultipleToggle argument " + k + ": " + e.getMessage());
          }
        }
      break;
  
    case "/record/start": 
      if (!oscRecording) {
        // Read file path string passed from Python
        String explicitPath = msg.get(0).stringValue();
        println("Received recording path from msg: " + explicitPath);
        // Ensure folders exist
        File f = new File(explicitPath);
        f.getParentFile().mkdirs();
    
        miTapRecorder.start(explicitPath);
        oscRecording = true;
  
        println("🎙️ OSC: START recording → " + explicitPath);
      }
      break;
  
      case "/record/end": 
        if (oscRecording) {
          miTapRecorder.stop();
          oscRecording = false;
          println("💾 OSC: STOP recording");
        }
      break;
        
      case "/quit":
        println("👋 Received /quit message. Exiting...");
        exit();  // This will close the Processing sketch cleanly
        break; 
  }
}
