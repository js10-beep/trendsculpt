import { useEffect, useRef, useState } from "react";
import { Image as ImageIcon } from "lucide-react";
import type { Report } from "./engine";

const timeLabel = (seconds: number) => {
  const value = Math.round(seconds * 10) / 10;
  const whole = Math.floor(value);
  const fraction = Math.round((value - whole) * 10);
  const clock =
    whole >= 3600
      ? `${Math.floor(whole / 3600)}:${String(Math.floor(whole / 60) % 60).padStart(2, "0")}`
      : `${Math.floor(whole / 60)}`;
  return `${clock}:${String(whole % 60).padStart(2, "0")}${fraction ? `.${fraction}` : ""}`;
};

export function VisualRecognitionPanel({
  report,
  onUpdate,
}: {
  report: Report;
  onUpdate: (report: Report) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState("");
  const [error, setError] = useState("");
  const [selected, setSelected] = useState(0);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => {
    setSelected(0);
    setError("");
    return () => controller.current?.abort();
  }, [report.id]);
  const timeline = report.mediaAnalysis?.timeline || [];
  if (!timeline.length || report.sample) return null;
  const visual = report.visualReview;
  const detection = visual?.frames[selected];
  const sample =
    detection &&
    timeline.find((frame) => frame.timestamp === detection.timestamp);
  async function run() {
    setBusy(true);
    setError("");
    const abort = new AbortController();
    controller.current = abort;
    try {
      const { recognizeVideo } = await import("./vision");
      const updated = await recognizeVideo(report, setProgress, abort.signal);
      if (abort.signal.aborted) return;
      onUpdate(updated);
      setSelected(0);
    } catch (e) {
      if (!abort.signal.aborted)
        setError(
          e instanceof Error
            ? e.message
            : "Visual recognition failed. Try again.",
        );
    } finally {
      controller.current = null;
      setBusy(false);
      setProgress("");
    }
  }
  return (
    <section
      className="card visual-recognition"
      aria-label="Visual subject recognition"
    >
      <div className="card-heading">
        <div>
          <span className="eyebrow">VISIBLE SUBJECTS · ON THIS DEVICE</span>
          <h2>Look beyond the words.</h2>
        </div>
        <span className="pill">
          {visual
            ? `${visual.frames.length} frames reviewed`
            : "Optional visual review"}
        </span>
      </div>
      <p>
        Recognize people and common objects in your actual video frames. Framing
        suggestions use those detections and matching subtitle lines when
        available.
      </p>
      {!visual && (
        <p className="fine-print">
          First use downloads about 19 MB of model files from TrendSculpt. Frame
          inference runs in your browser; only detection results return to your
          private report. Older devices may take longer. This model does not
          understand complex actions or stories.
        </p>
      )}
      <div className="actions">
        <button type="button" className="button" disabled={busy} onClick={run}>
          <ImageIcon size={18} />
          {busy
            ? "Reviewing visible subjects…"
            : visual
              ? "Run visual review again"
              : "Analyze visible subjects"}
        </button>
        {busy && (
          <button
            type="button"
            className="text-button"
            onClick={() => controller.current?.abort()}
          >
            Cancel visual review
          </button>
        )}
      </div>
      {busy && (
        <p className="vision-progress" role="status">
          {progress}
        </p>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {visual && (
        <>
          <div className="review-keywords">
            {visual.subjects.map((label) => (
              <span className="pill" key={label}>
                {label}
              </span>
            ))}
            {!visual.subjects.length && (
              <span>
                No supported objects reached 60% confidence. This does not mean
                the frames are empty.
              </span>
            )}
          </div>
          <div
            className="sample-controls"
            aria-label="Recognized video samples"
          >
            {visual.frames.map((frame, index) => (
              <button
                key={frame.timestamp}
                type="button"
                className={selected === index ? "active" : ""}
                aria-pressed={selected === index}
                aria-label={`Show visual detections at ${timeLabel(frame.timestamp)}`}
                onClick={() => setSelected(index)}
              >
                {timeLabel(frame.timestamp)}
              </button>
            ))}
          </div>
          {sample && detection && (
            <div className="recognized-layout">
              <div className="recognized-frame">
                <img
                  src={sample.thumbnail}
                  alt={`Recognized objects in the actual sample at ${timeLabel(sample.timestamp)}`}
                />
                {detection.objects.map((object, index) => (
                  <div
                    className="object-box"
                    aria-hidden="true"
                    key={index}
                    style={{
                      left: `${object.box[0] * 100}%`,
                      top: `${object.box[1] * 100}%`,
                      width: `${object.box[2] * 100}%`,
                      height: `${object.box[3] * 100}%`,
                    }}
                  >
                    <span>{index + 1}</span>
                  </div>
                ))}
              </div>
              <div>
                <span className="eyebrow">
                  MODEL ESTIMATES · {timeLabel(sample.timestamp)}
                </span>
                <h3>What the model can see.</h3>
                <ul className="recognized-objects">
                  {detection.objects.map((object, index) => (
                    <li key={index}>
                      <span>
                        <b>{index + 1}</b>
                        {object.label}
                      </span>
                      <span>
                        {Math.round(object.confidence * 100)}% confidence
                      </span>
                    </li>
                  ))}
                </ul>
                {!detection.objects.length && (
                  <p>
                    No supported object reached the detection threshold in this
                    sample. Inspect the frame yourself; the model can miss
                    subjects.
                  </p>
                )}
                {sample.overlayText && (
                  <p className="fine-print">
                    On-screen text estimate: “{sample.overlayText}”
                  </p>
                )}
              </div>
            </div>
          )}
          <p className="fine-print">{visual.note}</p>
        </>
      )}
    </section>
  );
}
