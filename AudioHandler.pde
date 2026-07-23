// PipeWire (Ubuntu 22.04+/24.04) locks its session clock to a fixed rate -
// check yours with `pw-metadata -n settings 0 clock.rate` in a terminal.
// Every audio object below must request exactly that rate, or javax.sound's
// direct-line open throws LineUnavailableException. On this machine that's
// 48000 Hz; the old 42930/44100 values were tuned for the Ubuntu 20.04 /
// PulseAudio stack, which resampled mismatched requests transparently.
static final int SAMPLE_RATE = 48000;

public void setAudioClient() {
  if (audioStreamHandler != null) {
    audioStreamHandler.shutdown();
    audioStreamHandler = null;
  }
  audioStreamHandler = miTappedPhyAudioClient.miPhyClassic(SAMPLE_RATE, 1024, 0, 2, phys);
  phys.setSimRate(SAMPLE_RATE);
  audioStreamHandler.setListenerAxis(listenerAxis.X);
  audioStreamHandler.setGain(gain);
  audioStreamHandler.start();
  // enable debug tone injection so the tap/WAV writer can be tested end-to-end
  audioStreamHandler.debugInjectTone = false;
  // miPhysics tap recorder (writes WAV from miPhysics audio)
  miTapRecorder = new MiPhysicsWavRecorder(SAMPLE_RATE, 2);
  audioStreamHandler.addTap(miTapRecorder);
  
  // Minim previously opened its own line here, but nothing in this sketch
  // reads from `in`/`out` — playback runs through audioStreamHandler and
  // recording runs through MiPhysicsWavRecorder. Leaving Minim's line open
  // just contends with audioStreamHandler for exclusive access to the sound
  // card and throws LineUnavailableException. Disabled until it's actually
  // needed for something (e.g. level metering, waveform display).
  // If you do need it later, route it to a different input/output device
  // than audioStreamHandler, or use audioStreamHandler's own tap API
  // (see addTap()) instead of a second competing line.
  /*
  minim = new Minim(this);
  int buffSize = 2048;
  try {
    boolean stereoAvailable = true;
    in = minim.getLineIn(Minim.STEREO, buffSize, SAMPLE_RATE);
    if (in != null) {
      if (in.getFormat().getChannels() != 2) {
        in.close();
        stereoAvailable = false;
        in = minim.getLineIn(Minim.MONO, buffSize, SAMPLE_RATE);
      }
    } else {
      stereoAvailable = false;
      in = minim.getLineIn(Minim.MONO, buffSize, SAMPLE_RATE);
    }

  out = minim.getLineOut(stereoAvailable ? Minim.STEREO : Minim.MONO, buffSize, SAMPLE_RATE);
  // Minim recorder creation disabled: we prefer the miPhysics tapped WAV writer.
  // If you want Minim recording later, uncomment the following line.
  // minimRecorder = minim.createRecorder(out, "recording_"+recCount+".wav", true);
  }
  catch (Exception e) {
    println("Error requesting stereo. Falling back to mono.");
  in = minim.getLineIn(Minim.MONO, buffSize, SAMPLE_RATE);
  out = minim.getLineOut(Minim.MONO, buffSize, SAMPLE_RATE);
  // minimRecorder = minim.createRecorder(out, "recording_"+recCount+".wav", true);
    
  }
  */
}

public void resetAudioClient() {
  if (audioStreamHandler != null) {
    audioStreamHandler.shutdown();
    audioStreamHandler = null;
    in = null;
    out = null;
  }
  setAudioClient();
}
