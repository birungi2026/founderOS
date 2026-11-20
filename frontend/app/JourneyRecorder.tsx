"use client";
import { useEffect, useRef, useState } from "react";
import { openCamera, makeRecorder, recordingError } from "./recording";
export default function JourneyRecorder({
  disabled,
  onReady,
  onActive,
}: {
  disabled: boolean;
  onReady: (file: File | null) => void;
  onActive: (active: boolean) => void;
}) {
  const [recording, setRecording] = useState(false),
    [requesting, setRequesting] = useState(false),
    [error, setError] = useState("");
  const stream = useRef<MediaStream | null>(null),
    recorder = useRef<MediaRecorder | null>(null),
    preview = useRef<HTMLVideoElement | null>(null),
    mounted = useRef(true),
    version = useRef(0),
    timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  function stop() {
    if (recorder.current?.state === "recording") recorder.current.stop();
    stream.current?.getTracks().forEach((track) => track.stop());
    stream.current = null;
    if (timer.current) clearTimeout(timer.current);
    if (mounted.current) setRecording(false);
  }
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      version.current++;
      stop();
    };
  }, []);
  useEffect(() => {
    if (disabled) {
      version.current++;
      stop();
    }
  }, [disabled]);
  useEffect(() => {
    if (preview.current) preview.current.srcObject = stream.current;
  }, [recording]);
  useEffect(() => {
    onActive(recording || requesting);
    return () => onActive(false);
  }, [recording, requesting, onActive]);
  async function start() {
    setError("");
    const current = ++version.current;
    setRequesting(true);
    try {
      const capture = await openCamera(true);
      if (!mounted.current || current !== version.current) {
        capture.getTracks().forEach((track) => track.stop());
        return;
      }
      stream.current = capture;
      onReady(null);
      const rec = makeRecorder(capture);
      recorder.current = rec;
      let chunks: Blob[] = [],
        bytes = 0,
        tooLarge = false;
      rec.ondataavailable = (event) => {
        bytes += event.data.size;
        if (bytes > 25 * 1024 * 1024) {
          tooLarge = true;
          chunks = [];
          stop();
          if (mounted.current)
            setError(
              "Recording reached 25 MB. Please record a shorter interview.",
            );
        } else chunks.push(event.data);
      };
      rec.onstop = () => {
        capture.getTracks().forEach((track) => track.stop());
        if (
          !mounted.current ||
          current !== version.current ||
          tooLarge ||
          !bytes
        )
          return;
        const type = (rec.mimeType || chunks[0]?.type || "video/webm").split(
          ";",
        )[0];
        onReady(
          new File(
            chunks,
            "interview." + (type === "video/mp4" ? "mp4" : "webm"),
            { type },
          ),
        );
        setRecording(false);
      };
      rec.onerror = () => {
        tooLarge = true;
        chunks = [];
        stop();
        if (mounted.current)
          setError(
            "Recording stopped unexpectedly. Please record again or upload a video.",
          );
      };
      rec.start(1000);
      setRecording(true);
      timer.current = setTimeout(stop, 120000);
    } catch (e) {
      stop();
      if (mounted.current) setError(recordingError(e));
    } finally {
      if (mounted.current) setRequesting(false);
    }
  }
  return (
    <div className="journey-recorder">
      <p>
        Speak naturally for 30 seconds to 2 minutes. Share who you help, how and
        your experience.
      </p>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {recording && (
        <video
          ref={preview}
          autoPlay
          muted
          playsInline
          style={{ width: "100%", maxHeight: 320 }}
        />
      )}
      <button
        type="button"
        className="secondary"
        disabled={disabled || requesting}
        onClick={() => {
          if (recording) stop();
          else void start();
        }}
      >
        {requesting
          ? "Opening camera…"
          : recording
            ? "Stop interview recording"
            : "Record my interview"}
      </button>
      <p>
        Stays on your device until uploaded. Avatar training may need a new
        recording.
      </p>
    </div>
  );
}
