import type { Report } from "./engine";
import { api } from "./store";

export type VisualObject = {
  label: string;
  confidence: number;
  box: [number, number, number, number];
};
export type VisualFrame = { timestamp: number; objects: VisualObject[] };
export type VisualReview = {
  model: string;
  frames: VisualFrame[];
  subjects: string[];
  note: string;
};

// Keep the opening, middle and ending. Use existing server-decoded previews,
// rather than uploading a second set of frames or seeking an entire long video.
export function selectVisionFrames(report: Report) {
  const frames = report.mediaAnalysis?.timeline || [];
  if (frames.length <= 8) return frames;
  const indexes = new Set([0, 1, 2, frames.length - 1]);
  for (const fraction of [0.25, 0.5, 0.75, 0.95])
    indexes.add(Math.round((frames.length - 1) * fraction));
  return [...indexes].sort((a, b) => a - b).map((i) => frames[i]);
}

export async function recognizeVideo(
  report: Report,
  progress: (message: string) => void,
  signal: AbortSignal,
): Promise<Report> {
  const frames = selectVisionFrames(report);
  if (!frames.length)
    throw new Error("This report has no video frames to inspect.");
  if (!window.Worker || !window.OffscreenCanvas || !window.createImageBitmap)
    throw new Error(
      "Visual recognition needs a recent Chrome, Edge, Firefox or Safari browser. Your existing review remains available.",
    );
  if (signal.aborted)
    throw new DOMException("Visual review stopped.", "AbortError");
  progress(
    "Loading the visual model on this device (about 19 MB on first use)…",
  );
  const worker = new Worker(new URL("./vision.worker.ts", import.meta.url), {
    type: "module",
  });
  try {
    const detections = await new Promise<VisualFrame[]>((resolve, reject) => {
      const stop = () =>
        finish(
          undefined,
          new DOMException("Visual review stopped.", "AbortError"),
        );
      signal.addEventListener("abort", stop, { once: true });
      // Terminating the worker stops inference and releases model tensors, even
      // if a weak device, broken model download or tab closure interrupts it.
      const timer = setTimeout(
        () =>
          finish(
            undefined,
            new Error(
              "Visual review took too long on this device. Your transcript and video measurements are still available.",
            ),
          ),
        180000,
      );
      const finish = (value?: VisualFrame[], error?: Error) => {
        clearTimeout(timer);
        signal.removeEventListener("abort", stop);
        error ? reject(error) : resolve(value!);
      };
      worker.onerror = () =>
        finish(
          undefined,
          new Error(
            "The visual model could not run on this device. Retry, or keep the existing review.",
          ),
        );
      worker.onmessage = ({ data }) => {
        if (data.error) finish(undefined, new Error(data.error));
        else if (data.frames) finish(data.frames);
        else if (data.progress) progress(data.progress);
      };
      worker.postMessage({ frames });
    });
    if (signal.aborted)
      throw new DOMException("Visual review stopped.", "AbortError");
    progress("Connecting visible subjects to your content…");
    return await api<Report>(
      "/reports/" + encodeURIComponent(report.id) + "/vision",
      {
        method: "POST",
        signal,
        body: JSON.stringify({
          model: "coco-ssdlite-mobilenet-v2-v1",
          frames: detections,
        }),
      },
    );
  } finally {
    worker.terminate();
  }
}
