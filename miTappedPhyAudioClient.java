package miPhysics.Engine;

import java.util.ArrayList;
import java.nio.FloatBuffer;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.logging.Logger;
import java.util.logging.Level;

import miPhysics.Engine.PhysicsContext;
import miPhysics.Engine.Sound.*; // listenerAxis, etc.

/**
 * Baseline tapped audio client:
 * - lets the base class render normally,
 * - snapshots the current block (outputs or inputs),
 * - forwards it to user taps,
 * - OPTIONAL: injects debug tone, prints diagnostics,
 * - NEW: mirrors and forwards listener axis & mode to taps.
 *
 * This keeps the original audio path intact while exposing
 * the user-selected axis/pos/force choice to downstream code.
 */
public class miTappedPhyAudioClient extends miPhyAudioClient {

    /** Callback fired once per processed audio block (on the audio thread). */
    public interface AudioTap {
        /** Legacy signature (kept for backward compatibility). */
        void onAudio(float[][] data, int nframes, int sampleRate, long timeNanos);

        /** 
         * Extended signature: we always call this one.
         * Default implementation delegates to legacy method so existing code continues to work.
         */
        default void onAudio(
                float[][] data,
                int nframes,
                int sampleRate,
                long timeNanos,
                boolean listenForce,
                listenerAxis axis
        ) {
            onAudio(data, nframes, sampleRate, timeNanos);
        }
    }

    private final CopyOnWriteArrayList<AudioTap> taps = new CopyOnWriteArrayList<>();
    private final int sampleRateInt;

    // --- NEW: mirror of listen mode & axis (like Luis version) ---
    private boolean listenFrc_local = false;
    private listenerAxis axis_local = listenerAxis.ALL;

    // debug: inject a test tone into the forwarded buffer so we can verify recording pipeline
    public boolean debugInjectTone = false;
    private double debugTonePhase = 0.0;
    private double debugToneFreq = 440.0; // Hz

    // diagnostics
    private long tapFramesThisSecond = 0;
    private long tapLastPrint = 0;
    private double outAbsSum = 0.0;
    private long outAbsCount = 0;
    private double inAbsSum = 0.0;
    private long inAbsCount = 0;

    /* ---------- Convenience factories (unchanged) ---------- */
    public static miTappedPhyAudioClient miPhyJack(
            float sampleRate, int bufS, int inputChannelCount, int outputChannelCount, PhysicsContext c
    ) {
        try {
            return new miTappedPhyAudioClient(sampleRate, inputChannelCount, outputChannelCount, c, bufS, "JACK");
        } catch (Exception e) {
            Logger.getLogger(miTappedPhyAudioClient.class.getName())
                    .log(Level.SEVERE, "Could not create a JACK miTappedPhyAudioClient", e);
            return null;
        }
    }

    public static miTappedPhyAudioClient miPhyClassic(
            float sampleRate, int bufS, int inputChannelCount, int outputChannelCount, PhysicsContext c
    ) {
        try {
            return new miTappedPhyAudioClient(sampleRate, inputChannelCount, outputChannelCount, c, bufS, "JavaSound");
        } catch (Exception e) {
            Logger.getLogger(miTappedPhyAudioClient.class.getName())
                    .log(Level.SEVERE, "Could not create a JavaSound miTappedPhyAudioClient", e);
            return null;
        }
    }

    /* ------------------------- Constructor ---------------------------- */
    public miTappedPhyAudioClient(
            float sampleRate,
            int inputChannelCount,
            int outputChannelCount,
            PhysicsContext c,
            int bufferSize,
            String serverType
    ) throws Exception {
        super(sampleRate, inputChannelCount, outputChannelCount, c, bufferSize, serverType);
        this.sampleRateInt = Math.round(sampleRate);
    }

    /* --------------------------- TAP API ------------------------------ */
    public void addTap(AudioTap tap) {
        if (tap != null) taps.add(tap);
    }

    public void removeTap(AudioTap tap) {
        if (tap != null) taps.remove(tap);
    }

    public void clearTaps() {
        taps.clear();
    }

    /* --------------------- NEW: Axis/Mode controls -------------------- */
    @Override
    public void listenFrc() {
        super.listenFrc();           // propagate to engine
        listenFrc_local = true;      // mirror locally (Luis-style)
    }

    @Override
    public void listenPos() {
        super.listenPos();
        listenFrc_local = false;
    }

    @Override
    public void setListenerAxis(listenerAxis a) {
        super.setListenerAxis(a);
        axis_local = a;
    }

    /** Optional convenience getters */
    public boolean isListeningForce() { return listenFrc_local; }
    public listenerAxis getListenerAxis() { return axis_local; }

    /* ----------------------- Audio hook logic -------------------------- */
    /**
     * We let the base class render first (super.process), which writes nframes
     * into each FloatBuffer and advances its position. Then we snapshot the
     * just-written region [pos - nframes, pos) for every channel and notify taps.
     */
    @Override
    public boolean process(long time, List<FloatBuffer> inputs, List<FloatBuffer> outputs, int nframes) {
        boolean ok = super.process(time, inputs, outputs, nframes); // baseline behavior
        if (!ok) return ok;

        final int outCount = outputs.size();
        final int inCount = inputs != null ? inputs.size() : 0;

        // snapshot outputs
        float[][] snapOut = new float[outCount][nframes];
        for (int ch = 0; ch < outCount; ch++) {
            FloatBuffer buf = outputs.get(ch);
            int end = buf.position();
            int start = end - nframes;
            if (start < 0) start = 0;
            if (end > buf.limit()) end = buf.limit();
            FloatBuffer ro = buf.asReadOnlyBuffer();
            ro.position(start);
            ro.limit(end);
            int len = ro.remaining();
            ro.get(snapOut[ch], 0, len);
            if (len < nframes) {
                for (int i = len; i < nframes; i++) snapOut[ch][i] = 0f;
            }
            // diagnostics
            for (int i = 0; i < nframes; i++) {
                float v = snapOut[ch][i];
                outAbsSum += Math.abs(v);
                outAbsCount++;
            }
        }

        // snapshot inputs for diagnostics (if present)
        float[][] snapIn = new float[inCount][nframes];
        for (int ch = 0; ch < inCount; ch++) {
            FloatBuffer buf = inputs.get(ch);
            int end = buf.position();
            int start = end - nframes;
            if (start < 0) start = 0;
            if (end > buf.limit()) end = buf.limit();
            FloatBuffer ro = buf.asReadOnlyBuffer();
            ro.position(start);
            ro.limit(end);
            int len = ro.remaining();
            ro.get(snapIn[ch], 0, len);
            if (len < nframes) {
                for (int i = len; i < nframes; i++) snapIn[ch][i] = 0f;
            }
            for (int i = 0; i < nframes; i++) {
                float v = snapIn[ch][i];
                inAbsSum += Math.abs(v);
                inAbsCount++;
            }
        }

        // decide which buffer to forward to taps: prefer outputs, but fallback to inputs
        float[][] forwardBuf = snapOut;
        double outAvgNow = outAbsCount > 0 ? (outAbsSum / (double) outAbsCount) : 0.0;
        double inAvgNow = inAbsCount > 0 ? (inAbsSum / (double) inAbsCount) : 0.0;
        if (inAvgNow > outAvgNow * 10.0 && inCount > 0) {
            forwardBuf = snapIn;
        }

        // optional debug: inject a test tone into the forwarded buffer so taps (and the WAV writer)
        // receive non-zero samples even if miPhysics produced silence. Toggle via debugInjectTone.
        if (debugInjectTone) {
            double phase = debugTonePhase;
            double phaseInc = 2.0 * Math.PI * debugToneFreq / (double) sampleRateInt;
            float amp = 0.1f;
            int chs = forwardBuf.length;
            for (int i = 0; i < nframes; i++) {
                float s = (float) (amp * Math.sin(phase));
                for (int ch = 0; ch < chs; ch++) {
                    forwardBuf[ch][i] = s;
                }
                phase += phaseInc;
            }
            debugTonePhase = phase % (2.0 * Math.PI);
        }

        // notify taps (extended overload: passes listen mode + axis)
        if (!taps.isEmpty()) {
            for (AudioTap tap : taps) {
                try {
                    tap.onAudio(forwardBuf, nframes, sampleRateInt, time, listenFrc_local, axis_local);
                } catch (Exception e) {
                    // keep audio thread stable - log and continue
                    Logger.getLogger(miTappedPhyAudioClient.class.getName()).log(Level.WARNING, "Tap threw", e);
                }
            }
        }

        // periodic diagnostics print
        tapFramesThisSecond += nframes;
        long now = System.currentTimeMillis();
        if (now - tapLastPrint >= 1000) {
            double outAvgPrint = outAbsCount > 0 ? (outAbsSum / (double) outAbsCount) : 0.0;
            double inAvgPrint = inAbsCount > 0 ? (inAbsSum / (double) inAbsCount) : 0.0;
            //System.out.println("[tap diagnostics] frames/s: " + tapFramesThisSecond
            //        + " outs:" + outCount + " ins:" + inCount
            //        + " outAvg:" + String.format("%.6f", outAvgPrint)
            //        + " inAvg:" + String.format("%.6f", inAvgPrint));

            // Print a small sample snippet (first few frames) for quick inspection
            int snippetLen = Math.min(8, nframes);
            if (outCount > 0) {
                StringBuilder sbo = new StringBuilder();
                //sbo.append("[tap diagnostics] outSnip[0]=");
                //for (int i = 0; i < snippetLen; i++) {
                //    sbo.append(String.format("%.6f", snapOut[0][i]));
                //    if (i < snippetLen - 1) sbo.append(",");
                //}
                //System.out.println(sbo.toString());
            }
            if (inCount > 0) {
                StringBuilder sbi = new StringBuilder();
                //sbi.append("[tap diagnostics] inSnip[0]=");
                //for (int i = 0; i < snippetLen; i++) {
                //    sbi.append(String.format("%.6f", snapIn[0][i]));
                //    if (i < snippetLen - 1) sbi.append(",");
                //}
                //System.out.println(sbi.toString());
            }

            tapFramesThisSecond = 0;
            tapLastPrint = now;
            outAbsSum = 0.0; outAbsCount = 0; inAbsSum = 0.0; inAbsCount = 0;
        }

        return true;
    }
}
