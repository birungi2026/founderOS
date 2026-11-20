/** Browser recording support shared by the interview screens. */
export async function openCamera(highResolution = false) {
  if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia)
    throw new Error(
      "Open Rymu using HTTPS (or localhost on this computer) to record. You can upload a video instead.",
    );
  if (typeof MediaRecorder === "undefined")
    throw new Error(
      "This browser cannot record video. Try Chrome or Safari, or upload a video.",
    );
  try {
    return await navigator.mediaDevices.getUserMedia({
      audio: true,
      video: highResolution
        ? {
            facingMode: "user",
            width: { ideal: 1920 },
            height: { ideal: 1080 },
          }
        : { facingMode: "user" },
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "OverconstrainedError")
      return navigator.mediaDevices.getUserMedia({ audio: true, video: true });
    throw error;
  }
}
export function makeRecorder(stream: MediaStream) {
  const types = ["video/webm;codecs=vp8,opus", "video/webm", "video/mp4"];
  for (const mimeType of types) {
    if (
      typeof MediaRecorder.isTypeSupported === "function" &&
      !MediaRecorder.isTypeSupported(mimeType)
    )
      continue;
    try {
      return new MediaRecorder(stream, {
        mimeType,
        videoBitsPerSecond: 2000000,
      });
    } catch (error) {
      if (
        !(error instanceof DOMException) ||
        error.name !== "NotSupportedError"
      )
        throw error;
    }
  }
  return new MediaRecorder(stream);
}
export function recordingError(error: unknown) {
  const name = error instanceof Error ? error.name : "";
  if (name === "NotAllowedError" || name === "PermissionDeniedError")
    return "Allow camera and microphone access in your browser’s site settings, then try again. You can also upload a video.";
  if (name === "NotFoundError" || name === "DevicesNotFoundError")
    return "No camera or microphone was found. Connect both, or upload a video.";
  if (
    name === "NotReadableError" ||
    name === "TrackStartError" ||
    name === "AbortError"
  )
    return "Your camera or microphone could not start. Close other camera apps or tabs, then try again. You can also upload a video.";
  return error instanceof Error && error.name === "Error"
    ? error.message
    : "Recording could not start. Try another browser or upload a video.";
}
