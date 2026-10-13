import * as tf from "@tensorflow/tfjs-core";
import "@tensorflow/tfjs-backend-cpu";
import { setWasmPaths, setThreadsCount } from "@tensorflow/tfjs-backend-wasm";
import { load } from "@tensorflow-models/coco-ssd";
import type { VisualFrame, VisualObject } from "./vision";

self.onmessage = async ({ data }) => {
  let model;
  try {
    // CPU inference in a disposable worker also supports devices without WebGPU.
    // Only the model graph and weights are fetched; image data stays local.
    setWasmPaths("/vision/tfjs-wasm-4.22.0/");
    setThreadsCount(1);
    // WASM avoids slow JavaScript convolutions. Fall back to CPU only when
    // WASM is unsupported; the main thread remains responsive either way.
    if (!(await tf.setBackend("wasm"))) await tf.setBackend("cpu");
    await tf.ready();
    model = await load({
      base: "lite_mobilenet_v2",
      modelUrl: "/vision/coco-ssd-v1/model.json",
    });
    const frames: VisualFrame[] = [];
    for (const [i, frame] of data.frames.entries()) {
      self.postMessage({
        progress: `Recognizing visible subjects: frame ${i + 1} of ${data.frames.length}…`,
      });
      const blob = await (await fetch(frame.thumbnail)).blob();
      const bitmap = await createImageBitmap(blob);
      const canvas = new OffscreenCanvas(bitmap.width, bitmap.height);
      const context = canvas.getContext("2d")!;
      context.drawImage(bitmap, 0, 0);
      bitmap.close();
      const pixels = tf.browser.fromPixels(
        context.getImageData(0, 0, canvas.width, canvas.height),
      );
      try {
        const detected = await model.detect(pixels, 8, 0.6);
        const objects: VisualObject[] = detected
          .map((object): VisualObject => {
            const [x, y, w, h] = object.bbox;
            const left = Math.max(0, Math.min(1, x / canvas.width));
            const top = Math.max(0, Math.min(1, y / canvas.height));
            return {
              label: object.class,
              confidence: Math.round(object.score * 1000) / 1000,
              box: [
                left,
                top,
                Math.min(1 - left, w / canvas.width),
                Math.min(1 - top, h / canvas.height),
              ],
            };
          })
          .filter((object) => object.box[2] > 0 && object.box[3] > 0);
        frames.push({ timestamp: frame.timestamp, objects });
      } finally {
        pixels.dispose();
      }
    }
    self.postMessage({ frames });
  } catch {
    self.postMessage({
      error:
        "The visual model could not load or inspect these frames. Retry on a recent browser; your existing review remains available.",
    });
  } finally {
    model?.dispose();
  }
};
