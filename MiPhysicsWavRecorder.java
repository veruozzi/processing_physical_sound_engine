package miPhysics.Engine;

import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;

import java.util.ArrayList;
import java.nio.FloatBuffer;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;

import miPhysics.Engine.PhysicsContext;
import miPhysics.Engine.Sound.*;

import java.util.logging.Logger;
import java.util.logging.Level;

/**
 * High-quality WAV recorder for miPhysics using miTappedPhyAudioClient.
 * 
 * Usage:
 *
 *   MiPhysicsWavRecorder rec = new MiPhysicsWavRecorder(48000, 2);
 *   audioClient.addTap(rec);   // start listening
 *   rec.start("test.wav");     // begin recording
 *   ...
 *   rec.stop();                // finalize WAV
 *
 */
public class MiPhysicsWavRecorder implements miTappedPhyAudioClient.AudioTap {

    private FileOutputStream out;
    private boolean recording = false;

    private int sampleRate;
    private int channels;
    private long totalFrames = 0;
    private long framesThisSecond = 0;
    private long lastPrintMillis = 0;
    // diagnostics for amplitude
    private double absSum = 0.0;
    private long absCount = 0;
    private float maxAbs = 0f;

    public MiPhysicsWavRecorder(int sampleRate, int channels) {
        this.sampleRate = sampleRate;
        this.channels = channels;
    }

    /** Start recording into the specified WAV file */
    public void start(String filename) {
        try {
            out = new FileOutputStream(filename);
            writeEmptyHeader();
            totalFrames = 0;

            // reset diagnostics
            framesThisSecond = 0;
            lastPrintMillis = System.currentTimeMillis();

            recording = true;
            System.out.println("🎙️ Recording started → " + filename);
        }
        catch (IOException e) {
            e.printStackTrace();
            recording = false;
        }
    }

    /** Stop recording and finalize proper WAV header */
    public void stop() {
        if (!recording) return;
        recording = false;

        try {
            finalizeHeader();
            out.close();
            System.out.println("💾 Recording saved.");
        }
        catch (Exception e) {
            e.printStackTrace();
        }
    }

    /** Called automatically by miTappedPhyAudioClient on every processed block */
    @Override
    public void onAudio(float[][] data, int nframes, int sampleRate, long timeNanos) {
        if (!recording) return;

        // --- diagnostics: count real frames per second ---
        framesThisSecond += nframes;
        long now = System.currentTimeMillis();
        if (now - lastPrintMillis >= 1000) {
            double avg = absCount > 0 ? (absSum / (double)absCount) : 0.0;
            System.out.println("🔎 Audio frames/sec (actual): " + framesThisSecond + " | avg abs:" + String.format("%.6f", avg) + " max:" + maxAbs);
            framesThisSecond = 0;
            lastPrintMillis = now;
            // reset amplitude diagnostics for next interval
            absSum = 0.0;
            absCount = 0;
            maxAbs = 0f;
        }

        try {
            byte[] block = new byte[nframes * channels * 2];
            int idx = 0;

            for (int i = 0; i < nframes; i++) {
                for (int ch = 0; ch < channels; ch++) {
                    float s = data[ch][i];
                    // accumulate diagnostics
                    float as = Math.abs(s);
                    absSum += as;
                    absCount++;
                    if (as > maxAbs) maxAbs = as;
                    s = Math.max(-1f, Math.min(1f, s));
                    short pcm = (short)(s * 32767f);
                    block[idx++] = (byte)(pcm & 0xff);
                    block[idx++] = (byte)((pcm >> 8) & 0xff);
                }
            }

            out.write(block);
            totalFrames += nframes;
        }
        catch (IOException e) {
            e.printStackTrace();
        }
    }

    /*-------------------------------------------------------------*
     *  WAV HEADER HANDLING
     *-------------------------------------------------------------*/

    private void writeEmptyHeader() throws IOException {
        // create dummy header placeholder
        byte[] header = new byte[44];
        out.write(header);
    }

    private void finalizeHeader() throws IOException {

        long byteRate  = sampleRate * channels * 2;
        long dataSize  = totalFrames * channels * 2;
        long chunkSize = 36 + dataSize;

        ByteBuffer buffer = ByteBuffer.allocate(44);
        buffer.order(ByteOrder.LITTLE_ENDIAN);

        buffer.put("RIFF".getBytes());
        buffer.putInt((int) chunkSize);
        buffer.put("WAVE".getBytes());

        // fmt chunk
        buffer.put("fmt ".getBytes());
        buffer.putInt(16);            // PCM header size
        buffer.putShort((short) 1);   // format: PCM
        buffer.putShort((short) channels);
        buffer.putInt(sampleRate);
        buffer.putInt((int) byteRate);
        buffer.putShort((short)(channels * 2)); // block align
        buffer.putShort((short)16);             // bits per sample

        // data chunk
        buffer.put("data".getBytes());
        buffer.putInt((int) dataSize);

        // rewrite header at beginning
        out.getChannel().position(0);
        out.write(buffer.array());
    }
}
