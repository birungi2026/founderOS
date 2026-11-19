"use client";
import { useEffect, useRef, useState } from "react";
const prompts = [
  "Introduce yourself and tell us why you started your company.",
  "What problem do you solve, and how does your solution work?",
  "Who are your target customers, and what makes your approach different?",
  "Explain something you know well, in your natural speaking style.",
  "How should your content sound? Share preferred pronunciations, languages and accent references.",
];
const steps = [
  "Interview",
  "Review brief",
  "Consent",
  "HeyGen setup",
  "Sample approval",
];
export default function FounderInterview({
  canWrite,
  active,
  personal = false,
}: {
  canWrite: boolean;
  active: boolean;
  personal?: boolean;
}) {
  const [step, setStep] = useState(0),
    [question, setQuestion] = useState(0),
    [url, setUrl] = useState(""),
    [sample, setSample] = useState(false),
    [recording, setRecording] = useState(false),
    [recordedBytes, setRecordedBytes] = useState(0),
    [requesting, setRequesting] = useState(false),
    [error, setError] = useState(""),
    [notes, setNotes] = useState(""),
    [tone, setTone] = useState(""),
    [consent, setConsent] = useState(false),
    [approved, setApproved] = useState(false),
    [prepared, setPrepared] = useState(false);
  const requestVersion = useRef(0);
  const recorder = useRef<MediaRecorder | null>(null),
    stream = useRef<MediaStream | null>(null),
    preview = useRef<HTMLVideoElement | null>(null),
    timer = useRef<ReturnType<typeof setTimeout> | null>(null),
    mounted = useRef(true),
    isActive = useRef(active);
  isActive.current = active;
  function stop() {
    if (recorder.current?.state === "recording") recorder.current.stop();
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
    if (timer.current) clearTimeout(timer.current);
    setRecording(false);
  }
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      if (recorder.current?.state === "recording") recorder.current.stop();
      stream.current?.getTracks().forEach((t) => t.stop());
      if (timer.current) clearTimeout(timer.current);
    };
  }, []);
  useEffect(() => {
    if (!active) {
      requestVersion.current++;
      stop();
    }
  }, [active]);
  useEffect(
    () => () => {
      if (url) URL.revokeObjectURL(url);
    },
    [url],
  );
  useEffect(() => {
    if (preview.current) preview.current.srcObject = stream.current;
  }, [recording]);
  function reset() {
    requestVersion.current++;
    stop();
    setUrl("");
    setSample(false);
    setNotes("");
    setTone("");
    setConsent(false);
    setPrepared(false);
    setApproved(false);
    setStep(0);
    setQuestion(0);
    setError("");
  }
  async function record() {
    setError("");
    if (
      !navigator.mediaDevices?.getUserMedia ||
      typeof MediaRecorder === "undefined"
    ) {
      setError(
        "Recording is unavailable in this browser. Upload a video or use the sample interview. Camera access requires localhost or HTTPS.",
      );
      return;
    }
    const version = ++requestVersion.current;
    setRequesting(true);
    try {
      const capture = await navigator.mediaDevices.getUserMedia({
        video: true,
        audio: true,
      });
      if (
        !mounted.current ||
        !isActive.current ||
        version !== requestVersion.current
      ) {
        capture.getTracks().forEach((t) => t.stop());
        return;
      }
      stream.current = capture;
      const rec = new MediaRecorder(capture);
      recorder.current = rec;
      let chunks: Blob[] = [];
      let bytes = 0;
      let oversized = false;
      rec.ondataavailable = (e) => {
        bytes += e.data.size;
        if (bytes > 100 * 1024 * 1024) {
          oversized = true;
          chunks = [];
          stop();
          setError(
            "Recording exceeded 100 MB. Please record a shorter interview.",
          );
        } else if (e.data.size) {
          chunks.push(e.data);
          if (mounted.current) setRecordedBytes(bytes);
        }
      };
      rec.onstop = () => {
        capture.getTracks().forEach((t) => t.stop());
        if (timer.current) clearTimeout(timer.current);
        if (mounted.current && !oversized) {
          setRecording(false);
          if (!chunks.length) {
            setError(
              "No video data was captured. Record a little longer or upload a video.",
            );
            return;
          }
          setUrl(URL.createObjectURL(new Blob(chunks, { type: rec.mimeType })));
          setSample(false);
          setRecording(false);
        }
      };
      rec.onerror = () => {
        stop();
        setError("Recording failed. Please try uploading a video.");
      };
      setRecordedBytes(0);
      rec.start(1000);
      setRecording(true);
      setUrl("");
      setSample(false);
      setConsent(false);
      setPrepared(false);
      setApproved(false);
      timer.current = setTimeout(stop, 180000);
    } catch {
      stream.current?.getTracks().forEach((t) => t.stop());
      if (mounted.current)
        setError(
          "Camera or microphone access was unavailable. Allow access in your browser, upload a video, or use the sample interview.",
        );
    } finally {
      if (mounted.current) setRequesting(false);
    }
  }
  return (
    <section
      className="panel interview-studio"
      aria-label="Founder video interview"
    >
      <span className="eyebrow">
        {personal
          ? "PERSONAL BRAND INTERVIEW · HEYGEN DEMO"
          : "FOUNDER INTERVIEW · HEYGEN DEMO"}
      </span>
      <h2>Your story. Your voice. Your digital twin.</h2>
      <p>
        Explore the complete onboarding flow before connecting HeyGen. Recording
        works locally; avatar creation and rendering are placeholders. No video,
        voice or notes are uploaded or sent to HeyGen.
      </p>
      <ol className="interview-steps" aria-label="Interview progress">
        {steps.map((name, i) => (
          <li key={name} aria-current={step === i ? "step" : undefined}>
            {i + 1}. {name}
          </li>
        ))}
      </ol>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <fieldset disabled={!canWrite}>
        {step === 0 && (
          <>
            <h3>1. Meet your growth employee</h3>
            <p>
              Use good lighting, face the camera and speak naturally in your
              usual accent. This footage can capture your face, expressions,
              mannerisms and voice as reference; this demo does not analyze or
              clone them.
            </p>
            <div className="interview-prompt">
              <small>
                Question {question + 1} of {prompts.length}
              </small>
              <h3>
                {personal
                  ? [
                      "Introduce yourself and tell us the story behind your personal brand.",
                      "What topics do you know well, and what do you want to be known for?",
                      "Who do you want to reach, and what makes your perspective useful?",
                      "Explain a topic you care about in your natural speaking style.",
                      prompts[4],
                    ][question]
                  : prompts[question]}
              </h3>
              <button
                type="button"
                className="secondary"
                disabled={question === 0}
                onClick={() => setQuestion(question - 1)}
              >
                Previous question
              </button>
              <button
                type="button"
                className="secondary"
                disabled={question === prompts.length - 1}
                onClick={() => setQuestion(question + 1)}
              >
                Next question
              </button>
            </div>
            {recording && (
              <>
                <video
                  ref={preview}
                  autoPlay
                  muted
                  playsInline
                  aria-label="Live interview camera preview"
                />
                <p role="status">
                  Recording locally · stops after 3 minutes. Move through the
                  questions while recording.
                  <output
                    aria-label="Recorded interview size"
                    data-recorded-bytes={recordedBytes}
                  >
                    {" "}
                    Captured: {Math.ceil(recordedBytes / 1024)} KB
                  </output>
                </p>
                <button type="button" onClick={stop}>
                  Stop recording
                </button>
              </>
            )}
            {!recording && (
              <>
                <button type="button" disabled={requesting} onClick={record}>
                  Record founder interview
                </button>
                <label>
                  Or upload your interview video
                  <input
                    disabled={requesting}
                    type="file"
                    accept="video/*"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (!file) return;
                      if (
                        !file.type.startsWith("video/") ||
                        file.size > 100 * 1024 * 1024
                      ) {
                        setError("Choose a video file up to 100 MB.");
                        e.target.value = "";
                        return;
                      }
                      setUrl(URL.createObjectURL(file));
                      setSample(false);
                      setConsent(false);
                      setPrepared(false);
                      setApproved(false);
                      setError("");
                    }}
                  />
                </label>
                <button
                  type="button"
                  className="secondary"
                  disabled={requesting}
                  onClick={() => {
                    setSample(true);
                    setUrl("");
                    setNotes(
                      personal
                        ? "EXAMPLE ONLY: I share practical engineering lessons with early-career developers. I want to grow a useful newsletter and attract mentoring opportunities."
                        : "EXAMPLE ONLY: I founded a company that helps small teams understand their customers. Our target customers are early-stage software teams.",
                    );
                    setTone(
                      "EXAMPLE ONLY: Conversational, practical and warm. The founder speaks in their own natural accent.",
                    );
                    setConsent(false);
                    setPrepared(false);
                    setApproved(false);
                    setError("");
                  }}
                >
                  Use sample interview
                </button>
              </>
            )}
            {url && (
              <>
                <h4>Your local recording</h4>
                <video
                  src={url}
                  controls
                  playsInline
                  aria-label="Recorded founder interview"
                />
                <p>
                  Your recording stays in this browser’s memory. It is not saved
                  to your FounderOS account.
                </p>
              </>
            )}
            {sample && (
              <p role="status">
                Sample interview selected. No real founder recording or voice is
                included.
              </p>
            )}
            <button
              type="button"
              disabled={requesting || recording || (!url && !sample)}
              onClick={() => setStep(1)}
            >
              Continue to review brief
            </button>
          </>
        )}
        {step === 1 && (
          <>
            <h3>2. Review your interview brief</h3>
            <p>
              {sample
                ? "These are fictional example notes. Edit them to explore the flow."
                : "Automatic transcription is not connected in this demo. Watch your recording and enter the facts and delivery preferences you want to confirm."}{" "}
              These notes do not update your approved founder profile.
            </p>
            <label>
              {personal
                ? "Personal brand interview notes"
                : "Founder and company interview notes"}
              <textarea
                required
                rows={5}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                maxLength={6000}
                placeholder="Your story, the problem, solution, target customers and differentiator"
              />
            </label>
            <label>
              Voice, accent and delivery preferences
              <textarea
                rows={3}
                value={tone}
                maxLength={2000}
                onChange={(e) => setTone(e.target.value)}
                placeholder="Describe your natural accent, tone, pace and preferred pronunciations"
              />
            </label>
            <p>
              Facial appearance is not used to infer personality. You confirm
              the facts and speaking preferences.
            </p>
            <button
              type="button"
              disabled={notes.trim().length < 10 || tone.trim().length < 3}
              onClick={() => setStep(2)}
            >
              Confirm brief and continue
            </button>
          </>
        )}
        {step === 2 && (
          <>
            <h3>3. Review face and voice consent</h3>
            <p>
              A live integration will require the founder’s explicit
              authorization and HeyGen’s own identity/consent process. A general
              interview may not meet the provider’s filming requirements.
            </p>
            <label className="check">
              <input
                type="checkbox"
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
              />
              I understand the face and voice consent step and want to simulate
              it in this demo.
            </label>
            <p>
              This checkbox only advances the preview. It is not stored as legal
              consent and does not authorize a real clone or public posting.
            </p>
            <button
              type="button"
              disabled={!consent}
              onClick={() => setStep(3)}
            >
              Continue to HeyGen setup
            </button>
          </>
        )}
        {step === 3 && (
          <>
            <h3>4. Set up your HeyGen digital twin</h3>
            <p>
              <strong>Provider: HeyGen · Demo adapter · Not connected</strong>
            </p>
            <ul>
              <li>
                Interview reference:{" "}
                {sample ? "fictional sample" : "local video, not uploaded"}
              </li>
              <li>Founder brief: confirmed for this preview</li>
              <li>
                Consent: simulated only; live provider verification still
                required
              </li>
              <li>
                Voice and accent: founder-provided preferences, not a trained
                voice
              </li>
            </ul>
            <p>
              In production, this step submits authorized media, waits for
              provider training and creates a test video. No provider request
              occurs here.
            </p>
            <button
              type="button"
              onClick={() => {
                setPrepared(true);
                setStep(4);
              }}
            >
              Prepare placeholder sample
            </button>
          </>
        )}
        {step === 4 && prepared && (
          <>
            <h3>5. Review your sample before activation</h3>
            <div className="avatar-placeholder">
              <span aria-hidden="true">F</span>
              <div>
                <strong>HeyGen video placeholder</strong>
                <p>No synthetic video or cloned audio has been generated.</p>
              </div>
            </div>
            <h4>Example sample script</h4>
            <blockquote>
              Hi, I’m the founder. Here’s the problem we’re solving and why it
              matters to our customers.
            </blockquote>
            <p>
              In a live rendered sample, check pronunciation, accent, lip sync,
              facial movement and overall delivery before approving. This
              placeholder cannot demonstrate cloning quality.
            </p>
            <label className="check">
              <input
                type="checkbox"
                checked={approved}
                onChange={(e) => setApproved(e.target.checked)}
              />
              I approve the demo workflow preview, not a real avatar or voice.
            </label>
            {approved && (
              <p className="notice" role="status">
                Demo onboarding complete. A real digital twin still needs a
                connected HeyGen account, verified consent, training and
                approval of a rendered sample. Content generation and publishing
                have not been activated.
              </p>
            )}
            <button
              type="button"
              className="secondary"
              onClick={() => {
                setApproved(false);
                setStep(1);
              }}
            >
              Revise brief
            </button>
          </>
        )}
        {step > 0 && (
          <button
            type="button"
            className="secondary"
            onClick={() => setStep(step - 1)}
          >
            Back to previous step
          </button>
        )}
        {(url || sample || step > 0) && (
          <button type="button" className="secondary" onClick={reset}>
            Delete local interview and reset demo
          </button>
        )}
      </fieldset>
      <small>
        Reloading or switching company removes this interview preview. Leaving
        this section stops camera capture. You can delete the local recording at
        any time. Real media storage, transcription, provider enrollment and
        video rendering require the live integration.
      </small>
    </section>
  );
}
