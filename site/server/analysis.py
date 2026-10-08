import base64, io, json, math, pathlib, re, subprocess, tempfile, uuid
from datetime import datetime, timezone
import joblib, numpy as np
from .media import inspect_media
from .content_review import review_content, LONG_FORM

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODELS = joblib.load(ROOT / ".models/models.joblib")
clamp = lambda n: max(15, min(96, round(float(n))))


def analyze_content(data, media_stats=None, private_models=None):
    review = (
        review_content(data, media_stats)
        if data["type"] == "Video" or data["platform"] == LONG_FORM
        else None
    )
    text = (
        (data.get("videoTitle", "") + "\n" + review["words"]).strip()
        if review and review["words"]
        else data["text"].strip()
    )
    words = text.split()
    first = (
        review["openingQuote"]
        if review and review["openingQuote"]
        else re.split(r"[.!?\n]", text)[0]
    )
    topic = data["topic"].strip() or (
        review["topic"] if review and review["topic"] else "your next post"
    )
    audience = data["audience"].strip()
    platform = data["platform"]
    has_cta = bool(
        re.search(
            r"\b(save|share|comment|follow|click|subscribe|tell|try|download|reply|join)\b",
            text + " " + data["cta"],
            re.I,
        )
    )
    has_hook = bool(
        re.search(
            r"\b(why|how|before|mistake|stop|what|secret|build|imagine)\b", first, re.I
        )
    )
    questions = "?" in text
    hashtags = re.findall(r"#[\w]+", text)
    ideal = 110 if platform == "LinkedIn" else 30 if platform == "X" else 65
    clarity = clamp(88 - abs(len(words) - ideal) * 0.3)
    if review and review["longForm"]:
        clarity = clamp(85 - max(0, len(words) / max(1, review["passages"]) - 30) * 0.5)
    hook = clamp(
        40
        + 20 * has_hook
        + 10 * bool(re.search(r"\d", first))
        + 8 * questions
        + 10 * (15 <= len(first) <= 120)
    )
    target_terms = set(re.findall(r"\w{4,}", audience.lower()))
    content_terms = set(re.findall(r"\w{4,}", text.lower()))
    relevance = (
        clamp(60 + min(25, 10 * len(target_terms & content_terms))) if audience else 55
    )
    scores = {
        "Hook strength": hook,
        "Audience relevance": relevance,
        "Engagement potential": clamp(
            45 + 18 * has_cta + 8 * questions + clarity * 0.15
        ),
        "Discoverability": clamp(
            46
            + 15 * bool(data["topic"])
            + 12 * (0 < len(hashtags) <= 5)
            + 6 * (len(text) > 80)
        ),
        "Retention potential": clamp(clarity * 0.7 + 15 * has_hook),
    }
    recommendations = []
    strengths = []
    if hook < 75:
        recommendations.append(
            {
                "title": "Make the first line specific",
                "reason": "The opening does not yet promise a clear outcome or question.",
                "suggestion": f"Before you explore {topic}, here’s one detail worth knowing.",
            }
        )
    else:
        strengths.append("A clear opening question or specific hook")
    if not has_cta:
        recommendations.append(
            {
                "title": "Ask for one useful action",
                "reason": "One specific invitation is easier to act on than a generic closing.",
                "suggestion": "Save this for your next " + topic + " session.",
            }
        )
    else:
        strengths.append("An explicit invitation to respond")
    if not audience:
        recommendations.append(
            {
                "title": "Choose a specific audience",
                "reason": "Audience context makes the feedback more relevant.",
                "suggestion": "Describe who this helps and the problem they are trying to solve.",
            }
        )
    if clarity < 70:
        recommendations.append(
            {
                "title": "Reduce competing ideas",
                "reason": "The caption length is outside this framework’s preferred range.",
                "suggestion": "Keep one main idea, short sentences and a clear final action.",
            }
        )
    else:
        strengths.append("A manageable caption length")
    if not data["topic"]:
        recommendations.append(
            {
                "title": "Name the core topic",
                "reason": "Specific topic language supports understanding and contextual comparison.",
                "suggestion": "Add the topic or category before rerunning analysis.",
            }
        )
    evidence = None
    model_key = (
        "Instagram"
        if platform == "Instagram"
        else "YouTube" if platform in {"YouTube Shorts", LONG_FORM} else None
    )
    if model_key and text:
        model = (private_models or {}).get(model_key, MODELS[model_key])
        query = model["vector"].transform([(text + " " + topic)[:16000]])
        similarities = (model["matrix"] @ query.T).toarray().ravel()
        indices = np.argsort(similarities)[::-1][:5]
        max_similarity = float(similarities[indices[0]])
        prediction = max(0, float(np.expm1(model["reg"].predict(query)[0])))
        matched = [model["rows"][int(i)] for i in indices if similarities[i] >= 0.06]
        rates = [r["rate"] for r in model["rows"]]
        rank = clamp(sum(r <= prediction for r in rates) / len(rates) * 100)
        mae = model["info"]["holdoutMAE"]
        usable = model["info"]["beatsBaseline"] and max_similarity >= 0.15
        if usable:
            scores["Engagement potential"] = clamp(
                scores["Engagement potential"] * 0.8 + rank * 0.2
            )
        evidence = {
            "platform": model_key,
            "method": model["info"]["method"],
            "datasetRows": model["info"]["rows"],
            "historicalEstimate": round(prediction, 2),
            "range": [
                round(max(0, prediction - 2 * mae), 2),
                round(prediction + 2 * mae, 2),
            ],
            "similarity": round(max_similarity, 3),
            "matchedRows": len(matched),
            "matchedMedian": (
                round(float(np.median([r["rate"] for r in matched])), 2)
                if matched
                else None
            ),
            "modelUsedForScore": usable,
            "confidence": "Limited",
            "validation": model["info"],
            "neighbors": [
                {"title": r["title"], "observedRate": round(r["rate"], 2)}
                for r in matched[:3]
            ],
            "note": "Historical-pattern estimate, not an expected engagement rate for your post. The displayed range is an error-band heuristic, not a calibrated confidence interval.",
        }
        recommendations.append(
            {
                "title": "Test your hook with your own audience",
                "reason": f"The {model_key} reference model uses {model['info']['rows']} biased historical observations; results may not transfer to your audience.",
                "suggestion": "Run a small A/B content experiment and compare actual saves, replies or watch time—not just predicted scores.",
            }
        )
    if media_stats:
        m = media_stats
        quality = clamp(
            55
            + 15 * (m["width"] >= 720)
            + 10
            * (
                m["width"] >= m["height"]
                if platform == LONG_FORM
                else m["height"] >= m["width"]
            )
            + 10 * (m["contrast"] >= 25)
            - 15 * (m["brightness"] < 40 or m["brightness"] > 225)
        )
        scores["Visual clarity"] = quality
        if m["width"] < 720:
            recommendations.append(
                {
                    "title": "Use a higher-resolution export",
                    "reason": f"The uploaded media is {m['width']} × {m['height']} pixels.",
                    "suggestion": "For vertical video, export at 1080 × 1920 when the original footage supports it.",
                }
            )
        if m["brightness"] < 40 or m["brightness"] > 225:
            recommendations.append(
                {
                    "title": "Check the exposure",
                    "reason": f"Measured luminance is {m['brightness']}/255 in the opening frame.",
                    "suggestion": "Adjust lighting and exposure so the first frame is easy to read on a phone.",
                }
            )
        if m["contrast"] < 20:
            recommendations.append(
                {
                    "title": "Create clearer visual separation",
                    "reason": "Measured contrast in the opening frame is low.",
                    "suggestion": "Check subject/background separation and overlay legibility. This is a measurement prompt, not a semantic image judgment.",
                }
            )
        if m["duration"]:
            if m["meanFrameChange"] < 4:
                recommendations.append(
                    {
                        "title": "Review the opening pacing",
                        "reason": f"{m['framesSampled']} sampled frames show little pixel change; this does not necessarily mean weak content.",
                        "suggestion": "Check whether the opening conveys value through narration, text or purposeful movement.",
                    }
                )
            if not text:
                recommendations.append(
                    {
                        "title": "Add spoken words or a transcript",
                        "reason": "The local video pipeline does not transcribe audio.",
                        "suggestion": "Paste the opening script so hook and audience feedback includes the spoken message.",
                    }
                )
        strengths.append("Media decoded and opening-frame measurements completed")
    if not recommendations:
        recommendations = [
            {
                "title": "Try a second framing",
                "reason": "Creative choices benefit from real audience feedback.",
                "suggestion": "Compare a question-led opening with a direct benefit-led opening.",
            }
        ]
    while len(strengths) < 3:
        strengths.append(
            [
                "A concrete draft to improve",
                "Platform context supplied",
                "A starting point for experimentation",
            ][len(strengths)]
        )
    opening = first[:160] or f"A closer look at {topic}"
    body = " ".join(words[:90]).strip()
    cta = data["cta"].strip() or (
        "Tell me which part you would try first."
        if data["objective"] == "Engagement"
        else "Save this for your next planning session."
    )
    hooks = [
        f'Before you {"publish your next post" if topic=="your next post" else "explore "+topic}, consider this.',
        f"What’s one thing worth knowing about {topic}?",
        f'{opening.rstrip(".")} — here’s the useful part.',
    ]
    captions = [
        f"{hooks[0]}\n\n{body}\n\n{cta}",
        f"{hooks[1]}\n\n{body}\n\nWhat would you add?",
    ]
    ctas = [
        cta,
        "Share this with someone working on " + topic + ".",
        "Which detail matters most to you? Tell me below.",
    ]
    if review:
        recommendations = review["recommendations"]
        if media_stats and media_stats["width"] < 720:
            recommendations.append(
                {
                    "title": "Review the export resolution",
                    "reason": f"The file measures {media_stats['width']} × {media_stats['height']} pixels.",
                    "suggestion": (
                        "Use a 1920 × 1080 landscape export when the source supports it."
                        if review["longForm"]
                        else "Use a 1080 × 1920 vertical export when the source supports it."
                    ),
                    "source": "Stream metadata",
                    "priority": "Medium",
                    "timestamp": None,
                    "quote": None,
                }
            )
        hooks = review["hooks"]
        ctas = [review["cta"]] if review["words"] else []
        captions = [
            f"{h}\n\n{data['text'].strip()}\n\n{review['cta']}" for h in hooks[:2]
        ]
        if not review["words"]:
            scores = {k: v for k, v in scores.items() if k == "Visual clarity"}
            if not scores:
                scores = {"Context completeness": 15}
            strengths = (
                ["Actual media measurements available"]
                if media_stats
                else ["Platform context supplied"]
            )
        elif review["longForm"]:
            title_words = len(data.get("videoTitle", "").split())
            scores.pop("Retention potential", None)
            scores["Title clarity"] = (
                clamp(82 - abs(title_words - 9) * 4) if title_words else 15
            )
            scores["Structure clarity"] = clamp(
                45 + 5 * min(8, review["passages"]) + 12 * bool(review["timedSegments"])
            )
            scores.pop("Discoverability", None)
            strengths = [
                f"{review['passages']} supplied transcript passages reviewed",
                "Dedicated long-form title and structure review",
                "Source-labelled evidence for each edit",
            ]
        elif review["hasTranscript"]:
            scores.pop("Retention potential", None)
            scores["Structure clarity"] = clamp(55 + min(25, 5 * review["passages"]))
            strengths = [
                f"Feedback grounded in {review['source'].lower()}",
                "Opening and closing words reviewed",
                "Video samples available for inspection",
            ]
        recommendations.sort(key=lambda r: 0 if r.get("priority") == "High" else 1)
    overall = clamp(np.mean(list(scores.values())))
    summary = (
        f"Your {platform} {data['type'].lower()} has {'strong' if overall>=75 else 'developing'} potential in the content framework. The clearest next step is to {recommendations[0]['title'].lower()}. "
        + (
            "Local regression and similarity retrieval ran against the historical reference dataset."
            if evidence
            else "No platform-matched model evidence is available; this score uses transparent content heuristics."
        )
    )
    return {
        **data,
        "id": str(uuid.uuid4()),
        "title": data.get("videoTitle", "").strip()
        or first[:85]
        or data.get("mediaName")
        or "Untitled content",
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "overallScore": overall,
        "scores": scores,
        "summary": (
            f"{'Long-form YouTube' if review['longForm'] else 'Video'} review based on {review['source'].lower()}. {len(recommendations)} edit suggestions reference the supplied words and available video measurements. These are content checks, not a forecast of watch time or engagement."
            if review
            else summary
        ),
        "strengths": strengths,
        "recommendations": recommendations,
        "hooks": hooks,
        "captions": captions,
        "ctas": ctas,
        "applied": bool(data.get("applied", False)),
        "evidence": evidence,
        "mediaAnalysis": media_stats,
        "contentReview": (
            {
                k: v
                for k, v in review.items()
                if k not in {"words", "recommendations", "hooks", "cta"}
            }
            if review
            else None
        ),
        "provider": (
            "Local dataset model + content framework"
            if evidence
            else (
                "Content framework + media measurements"
                if media_stats
                else "Content framework"
            )
        ),
    }
