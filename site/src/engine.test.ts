import test from "node:test";
import assert from "node:assert/strict";
import { analyze, Input } from "./engine";
const base: Input = {
  text: "Some tips",
  type: "Text",
  platform: "Instagram",
  objective: "Reach",
  audience: "",
  topic: "",
  cta: "",
};
test("rejects empty input", () =>
  assert.throws(() => analyze({ ...base, text: "" })));
test("signals produce differentiated, reproducible scores", () => {
  const a = analyze(base),
    b = analyze({
      ...base,
      text: "How to build 3 habits for creators? Save this and share your favorite. #creator",
      audience: "creators",
      topic: "habits",
    });
  assert.ok(b.overallScore > a.overallScore);
  assert.deepEqual(
    b.scores,
    analyze({ ...base, text: b.text, audience: "creators", topic: "habits" })
      .scores,
  );
  assert.ok(b.recommendations.length && b.captions.length);
  Object.values(b.scores).forEach((x) => assert.ok(x >= 0 && x <= 100));
});
test("file readiness does not pretend to evaluate visual composition", () => {
  const r = analyze({
    ...base,
    text: "",
    type: "Image",
    media: "blob:test",
    mediaWidth: 1080,
    mediaHeight: 1920,
  });
  assert.ok(r.scores["Media readiness"]);
  assert.ok(
    r.recommendations.some((x) => x.reason.includes("not composition")),
  );
});
