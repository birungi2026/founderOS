"use client";
import { useEffect, useRef, useState } from "react";
import { openCamera, makeRecorder, recordingError } from "./recording";
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
    const version = ++requestVersion.current;
    setRequesting(true);
    try {
      const capture = await openCamera();
      if (
        !mounted.current ||
        !isActive.current ||
        version !== requestVersion.current
      ) {
        capture.getTracks().forEach((t) => t.stop());
        return;
      }
      stream.current = capture;
      const rec = makeRecorder(capture);
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
        if (
          mounted.current &&
          isActive.current &&
          version === requestVersion.current &&
          !oversized
        ) {
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
        oversized = true;
        chunks = [];
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
    } catch (error) {
      stream.current?.getTracks().forEach((t) => t.stop());
      if (mounted.current) setError(recordingError(error));
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
        HeyGen demo: recordings stay on your device. No uploads, avatar training
        or rendering.
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
              Face the camera in good light and speak naturally. This demo
              records but does not analyze or clone you.
            </p>
            <div className="interview-prompt">
              <small>
                Question {question + 1} of {prompts.length}
              </small>
              <h3>
                {personal
                  ? [
                      "Tell us about yourself and what you enjoy.",
                      "What would you like to post about?",
                      "Who would enjoy your posts?",
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
                  Recording on your device · 3-minute limit.
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
                  {personal
                    ? "Record my interview"
                    : "Record founder interview"}
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
                  to your Rymu account.
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
                : "No demo transcription. Add your interview notes and speaking preferences."}{" "}
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
              You confirm your facts and speaking style. No facial personality
              analysis.
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
              Live cloning requires your permission and HeyGen’s identity,
              consent and filming checks.
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
              Demo only. This checkbox does not authorize cloning or posting.
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
              A live setup trains your avatar and renders a sample. This demo
              makes no provider requests.
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
              A real sample lets you check voice, accent, lip sync and movement.
              This placeholder does not show cloning quality.
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
                Demo complete. Live cloning needs HeyGen, verified consent,
                training and an approved sample. Publishing is off.
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
        This preview resets on reload or company change. Leaving stops the
        camera. Delete your local recording anytime. Live processing requires
        provider setup.
      </small>
    </section>
  );
}
