import { runAnalysis } from "./store";
export type Input = {
  text: string;
  type: string;
  platform: string;
  objective: string;
  audience: string;
  topic: string;
  cta: string;
  applied?: boolean;
  media?: string;
  mediaName?: string;
  mediaWidth?: number;
  mediaHeight?: number;
  duration?: number;
  transcript?: string;
  videoTitle?: string;
  sourceReportId?: string;
};
export type Recommendation = {
  title: string;
  reason: string;
  suggestion: string;
  timestamp?: number | null;
  quote?: string | null;
  source?: string;
  priority?: string;
};
export type Report = Input & {
  id: string;
  title: string;
  createdAt: string;
  overallScore: number;
  scores: Record<string, number>;
  summary: string;
  strengths: string[];
  recommendations: Recommendation[];
  hooks: string[];
  captions: string[];
  ctas: string[];
  applied: boolean;
  sample?: boolean;
  provider?: string;
  contentReview?: {
    source: string;
    hasTranscript: boolean;
    timedSegments: number;
    passages: number;
    keywords: string[];
    topic: string;
    openingQuote: string;
    closingQuote: string;
    longForm: boolean;
    chapters: { timestamp: number | null; title: string; source: string }[];
    coverage: string;
  } | null;
  evidence?: {
    platform: string;
    method: string;
    datasetRows: number;
    historicalEstimate: number;
    range: number[];
    similarity: number;
    matchedRows: number;
    matchedMedian: number | null;
    modelUsedForScore: boolean;
    confidence: string;
    validation: {
      holdoutMAE: number;
      baselineMAE: number;
      label: string;
      limitations: string;
    };
    neighbors: { title: string; observedRate: number }[];
    note: string;
  } | null;
  mediaAnalysis?: {
    width: number;
    height: number;
    brightness: number;
    contrast: number;
    edgeDetail: number;
    framesSampled: number;
    duration: number | null;
    hasAudio: boolean;
    meanFrameChange: number;
    method: string;
    limits: string;
    timeline?: {
      timestamp: number;
      thumbnail: string;
      brightness: number;
      contrast: number;
      clippedPercent: number;
      overlayText: string;
      ocrStatus?: string;
    }[];
    audioWindows?: {
      timestamp: number;
      duration: number;
      meanDb: number | null;
      peakDb: number | null;
    }[];
    ocrAvailable?: boolean;
  } | null;
};
const bounded = (x: number) => Math.min(96, Math.max(18, Math.round(x)));
export function analyze(input: Input): Report {
  const text = input.text.trim();
  if (!text && !input.media)
    throw new Error("Add text or upload media before analyzing.");
  const words = text.split(/\s+/).filter(Boolean);
  const first = text.split(/[.!?\n]/)[0];
  const question = /\?/.test(text),
    number = /\d/.test(first),
    hook =
      /\b(stop|why|how|before|secret|mistake|imagine|learn|what|never|build)\b/i.test(
        first,
      );
  const hasCTA =
    /\b(save|share|comment|follow|click|subscribe|tell|try|download|reply|join)\b/i.test(
      text + " " + input.cta,
    );
  const hashtags = text.match(/#[\p{L}\d_]+/gu) || [];
  const ideal =
    input.platform === "LinkedIn" ? 120 : input.platform === "X" ? 35 : 65;
  const clarity = bounded(
    88 - Math.abs(words.length - ideal) * 0.3 - (text.length > 2000 ? 15 : 0),
  );
  const topic = input.topic.trim() || "your next post";
  const audience = input.audience.trim();
  const relevance = audience
    ? bounded(
        65 +
          (audience
            .toLowerCase()
            .split(/\s+/)
            .some((w) => w.length > 3 && text.toLowerCase().includes(w))
            ? 18
            : 4),
      )
    : 58;
  const visual = input.media
    ? bounded(
        60 +
          (input.mediaWidth && input.mediaWidth >= 720 ? 10 : 0) +
          (input.mediaHeight &&
          input.mediaWidth &&
          input.mediaHeight > input.mediaWidth
            ? 8
            : 0),
      )
    : 0;
  const scores: Record<string, number> = {
    "Hook strength": bounded(
      40 +
        (hook ? 22 : 0) +
        (number ? 10 : 0) +
        (question ? 8 : 0) +
        (first.length >= 15 && first.length <= 120 ? 10 : 0),
    ),
    "Audience relevance": relevance,
    "Engagement potential": bounded(
      43 +
        (hasCTA ? 20 : 0) +
        (question ? 10 : 0) +
        (input.objective === "Engagement" ? 5 : 0) +
        clarity * 0.15,
    ),
    Discoverability: bounded(
      45 +
        (input.topic ? 16 : 0) +
        (hashtags.length >= 1 && hashtags.length <= 5
          ? 14
          : hashtags.length > 5
            ? 3
            : 0) +
        (text.length > 80 ? 8 : 0),
    ),
    "Retention potential": bounded(
      clarity * 0.7 +
        (hook ? 15 : 4) +
        (input.type === "Video" && input.duration && input.duration <= 60
          ? 8
          : 0),
    ),
  };
  if (input.media) scores["Media readiness"] = visual;
  const overallScore = bounded(
    Object.values(scores).reduce((a, b) => a + b, 0) /
      Object.values(scores).length,
  );
  const recs: Recommendation[] = [];
  if (!hasCTA)
    recs.push({
      title: "Give your audience a next step",
      reason: "A clear invitation makes it easier to respond.",
      suggestion: "Save this for your next " + topic + " session.",
    });
  if (scores["Hook strength"] < 75)
    recs.push({
      title: "Make the opening work harder",
      reason: "Your first line needs a specific reason to keep reading.",
      suggestion: `Before you publish about ${topic}, try this one change.`,
    });
  if (!audience)
    recs.push({
      title: "Define who this is for",
      reason: "Without an audience, relevance is harder to assess.",
      suggestion: "Add a target audience and speak to one specific challenge.",
    });
  if (clarity < 70)
    recs.push({
      title: "Tighten your caption",
      reason: "The length is outside the preferred range in this heuristic.",
      suggestion: "Keep one idea, short sentences, and a clear final action.",
    });
  if (!input.topic || !hashtags.length)
    recs.push({
      title: "Add specific topic signals",
      reason: "Concrete language helps readers understand the subject.",
      suggestion:
        "Name your topic and add 1–3 relevant hashtags where appropriate.",
    });
  if (input.media)
    recs.push({
      title: "Review the first visual manually",
      reason:
        "This demo checks file dimensions, not composition or visual meaning.",
      suggestion:
        "Keep the subject clear and check that overlays are readable on a phone.",
    });
  if (!recs.length)
    recs.push({
      title: "Test a second angle",
      reason: "Even strong content benefits from experimentation.",
      suggestion:
        "Compare a curiosity-led opening with a direct value statement.",
    });
  const strengths = [
    hook ? "Specific opening language" : "A starting idea to refine",
    hasCTA
      ? "Clear call to action"
      : question
        ? "Invites a response"
        : "Simple content structure",
    clarity >= 70
      ? "Readable caption length"
      : "Room to make the message more focused",
    audience ? "Defined audience context" : "Flexible platform context",
  ];
  const hooks = [
    `Before you ${topic === "your next post" ? "publish your next post" : `explore ${topic}`}, try this.`,
    `3 things I wish I knew about ${topic}.`,
    `What actually makes ${topic} work? Here’s where to start.`,
  ];
  const ctas = [
    "Save this for later.",
    "Which part would you try first? Tell me below.",
    "Share this with someone who needs it.",
  ];
  const body = words
    .slice(0, Math.min(words.length, 70))
    .join(" ")
    .replace(/#[\p{L}\d_]+/gu, "")
    .trim();
  const captions = [
    `${hooks[0]}\n\n${body}\n\n${ctas[0]}`,
    `${hooks[2]}\n\n${body}\n\n${ctas[1]}`,
  ];
  return {
    ...input,
    id: crypto.randomUUID(),
    title: first.slice(0, 85) || input.mediaName || "Untitled content",
    createdAt: new Date().toISOString(),
    overallScore,
    scores,
    summary: `Your ${input.platform} ${input.type.toLowerCase()} has ${overallScore >= 75 ? "strong" : "developing"} potential in this heuristic. ${strengths[0]}. The next opportunity: ${recs[0].title.toLowerCase()}.`,
    strengths,
    recommendations: recs,
    hooks,
    captions,
    ctas,
    applied: false,
  };
}
export const contentAnalysisService = {
  analyze: async (input: Input) => runAnalysis(input),
};
