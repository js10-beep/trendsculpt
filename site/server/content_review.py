"""Ground recommendations in supplied words and measurable video evidence."""

import collections
import html
import re
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

LONG_FORM = "YouTube (long-form)"
STOP = set(ENGLISH_STOP_WORDS) | {
    "like",
    "just",
    "really",
    "video",
    "today",
    "going",
    "guys",
    "hello",
    "welcome",
    "channel",
}
CUE = re.compile(
    r"(?m)^\s*((?:\d{1,2}:)?\d{2}:\d{2}[.,]\d{3})\s*-->\s*((?:\d{1,2}:)?\d{2}:\d{2}[.,]\d{3})[^\n]*\n"
)


def seconds(value):
    parts = value.replace(",", ".").split(":")
    return sum(float(p) * 60**i for i, p in enumerate(reversed(parts)))


def timestamp(value):
    value = max(0, int(value))
    return (
        f"{value // 3600}:{value // 60 % 60:02}:{value % 60:02}"
        if value >= 3600
        else f"{value // 60}:{value % 60:02}"
    )


def clean(value):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", "", value))).strip()


def parse_transcript(value):
    value = value.strip().lstrip("\ufeff").replace("\r\n", "\n")
    cues = list(CUE.finditer(value))
    segments = []
    if cues:
        last = -1
        for i, cue in enumerate(cues):
            start, end = seconds(cue[1]), seconds(cue[2])
            if start < last or end <= start or end > 86400:
                raise ValueError(
                    "Subtitle timestamps must be ordered, with each end after its start."
                )
            chunk = value[
                cue.end() : cues[i + 1].start() if i + 1 < len(cues) else len(value)
            ]
            if i + 1 < len(cues):
                chunk = re.sub(r"\n\s*\d+\s*$", "", chunk.strip())
            text = clean(chunk)
            if text:
                segments.append({"start": start, "end": end, "text": text[:3000]})
            last = start
        return segments, "Timestamped subtitles"
    if "-->" in value or value.startswith("WEBVTT"):
        raise ValueError(
            "Could not read subtitle timing. Use SRT or WebVTT timestamps."
        )
    # Timestamped pasted transcripts: 0:00 Opening words, 04:10 Main point.
    lines = []
    for line in value.splitlines():
        match = re.match(r"^\s*((?:\d+:)?\d{1,2}:\d{2})(?:\s+|\s*[-–]\s*)(.+)$", line)
        if match:
            lines.append(
                {"start": seconds(match[1]), "end": None, "text": clean(match[2])}
            )
    if lines:
        if any(b["start"] < a["start"] for a, b in zip(lines, lines[1:])):
            raise ValueError("Transcript timestamps must be in order.")
        return lines, "Timestamped transcript"
    chunks = [clean(p) for p in re.split(r"\n\s*\n|(?<=[.!?])\s+", value) if clean(p)]
    return [
        {"start": None, "end": None, "text": p[:3000]} for p in chunks
    ], "Pasted transcript"


def keywords(text):
    words = [w for w in re.findall(r"[a-z][a-z'-]{2,}", text.lower()) if w not in STOP]
    return [w for w, _ in collections.Counter(words).most_common(6)]


def review_content(data, media):
    long = data.get("platform") == LONG_FORM
    transcript = data.get("transcript", "").strip()
    segments, source = parse_transcript(transcript) if transcript else ([], "")
    supplied = bool(segments)
    if not segments and media:
        segments = [
            {"start": f["timestamp"], "end": None, "text": f["overlayText"]}
            for f in media.get("timeline", [])
            if f.get("overlayText")
        ]
        if segments:
            source = "Estimated on-screen text (OCR)"
    if not segments and data.get("text", "").strip():
        segments = [{"start": None, "end": None, "text": clean(data["text"])}]
        source = "Caption / supplied content context"
    all_words = " ".join(s["text"] for s in segments)
    terms = keywords(
        data.get("videoTitle", "")
        + " "
        + data.get("topic", "")
        + " "
        + all_words[:30000]
    )
    topic = (
        data.get("topic", "").strip()
        or data.get("videoTitle", "").strip()
        or ", ".join(terms[:3])
    )
    title = data.get("videoTitle", "").strip()
    first = segments[0] if segments else None
    actionable = next(
        (
            s
            for s in segments
            if re.search(
                r"\b(add|mix|use|cut|build|show|choose|check|start|prepare|replace|solve|plant|fold|avoid|compare)\b",
                s["text"],
                re.I,
            )
            and not re.match(r"^(hello|hey|welcome)", s["text"], re.I)
        ),
        first,
    )
    specific = clean(actionable["text"] if actionable else title or topic)
    recs = []

    def add(
        title, reason, suggestion, segment=None, priority="Medium", source_name=None
    ):
        point = segment.get("start") if segment else None
        recs.append(
            {
                "title": title,
                "reason": reason,
                "suggestion": suggestion,
                "timestamp": point,
                "quote": segment["text"][:220] if segment else None,
                "source": source_name or source or "Video measurements",
                "priority": priority,
            }
        )

    opening = first["text"] if first else ""
    filler = re.match(
        r"^(?:hey|hello|hi\b|welcome|what'?s up|in (?:this|today'?s) video|today (?:we|i))",
        opening,
        re.I,
    )
    promise = bool(
        re.search(
            r"\b(how|why|fix|avoid|learn|build|make|compare|before|mistake|result)\b|\d",
            opening,
            re.I,
        )
    )
    if first:
        if not supplied and source == "Estimated on-screen text (OCR)":
            add(
                "Check the first readable overlay",
                f"OCR estimates “{opening[:150]}” at {timestamp(first['start'])}. This is on-screen text, not a transcript of speech.",
                "Verify the words in the sampled frame, then check their size, contrast and whether this message is shown early enough to establish the video's point.",
                first,
                "High",
            )
        elif filler or not promise:
            add(
                "Lead with the actual point",
                f"Your opening begins with “{opening[:150]}” instead of a specific outcome or question.",
                (
                    f"Try opening with “{specific[:180]}” and show the corresponding example before introductory remarks."
                    if specific
                    else "State the result the viewer will learn before the introduction."
                ),
                first,
                "High",
            )
        elif (
            actionable
            and actionable is not first
            and actionable.get("start") is not None
            and actionable["start"] > (30 if long else 3)
        ):
            add(
                "Bring the demonstration forward",
                f"The first practical instruction appears at {timestamp(actionable['start'])} in the supplied transcript.",
                f"Preview “{actionable['text'][:160]}” in the opening, then explain the steps in sequence.",
                actionable,
                "High",
            )
        else:
            add(
                "Connect the opening to a visible example",
                f"The supplied opening is “{opening[:150]}”.",
                f"Pair this line with the actual {topic or 'demonstration'} example. Keep the words and visual focused on that single point; compare the edit against real retention data.",
                first,
                "Medium",
            )
    elif media:
        add(
            "Supply the spoken context",
            "No transcript or readable on-screen words were available; the video was measured without its spoken meaning.",
            "Upload SRT/VTT subtitles or paste the actual spoken script. This enables quoted, content-specific hook and structure suggestions.",
            priority="High",
            source_name="Coverage check",
        )

    groups = collections.defaultdict(list)
    for segment in segments:
        normalized = re.sub(r"\W+", " ", segment["text"].lower()).strip()
        if len(normalized.split()) >= 6:
            groups[normalized].append(segment)
    duplicate = next((g for g in groups.values() if len(g) > 1), None)
    if duplicate:
        add(
            "Review repeated wording",
            f"This line occurs {len(duplicate)} times in the supplied words; repetition may be intentional.",
            f"Keep one full explanation of “{duplicate[0]['text'][:140]}”. In later occurrences, add a new example or a short recap instead of repeating the same wording.",
            duplicate[1],
        )
    dense = next(
        (
            s
            for s in segments
            if s.get("end") is not None
            and s["end"] - s["start"] >= 3
            and len(s["text"].split()) / (s["end"] - s["start"]) > 4
        ),
        None,
    )
    if dense:
        add(
            "Check the pace of this instruction",
            f"The supplied cue contains {len(dense['text'].split())} words in {dense['end'] - dense['start']:.1f} seconds. Subtitle timing may be inaccurate.",
            f"Check the timing against the video. If it is correct, give “{dense['text'][:150]}” more room: split the instruction into separate steps and show each action before continuing.",
            dense,
        )
    last = segments[-1] if segments else None
    closing = " ".join(s["text"] for s in segments[-3:])
    has_cta = bool(
        re.search(
            r"\b(comment|subscribe|watch|try|save|share|download|click|tell|follow|reply|join)\b",
            closing + " " + data.get("cta", ""),
            re.I,
        )
    )
    cta = data.get("cta", "").strip() or (
        f"Which detail in “{topic}” would you like explained next? Tell me in the comments."
        if topic
        else "Which step needs a closer demonstration? Tell me in the comments."
    )
    if last and not has_cta:
        add(
            "Make the closing action fit this video",
            f"The closing “{last['text'][:140]}” does not include a clear next action.",
            cta,
            last,
        )

    timed = [s for s in segments if s["start"] is not None]
    chapters = []
    if long and supplied:
        candidates = timed or segments
        for i in sorted(
            set(
                round(n * (len(candidates) - 1) / max(1, min(5, len(candidates)) - 1))
                for n in range(min(5, len(candidates)))
            )
        ):
            segment = candidates[i]
            chapters.append(
                {
                    "timestamp": segment["start"],
                    "title": segment["text"][:85],
                    "source": source,
                }
            )
        add(
            "Turn the actual sections into chapters",
            f"The review found {len(segments)} transcript passages. The chapter draft below uses their actual wording and available timestamps.",
            "Review the chapter boundaries in your editor. Start the final YouTube chapter list at 0:00, use at least 3 chapters, and keep each chapter at least 10 seconds long.",
            priority="Medium",
            source_name="Transcript structure",
        )
    if long:
        if not title:
            add(
                "Review a title against the video",
                "A YouTube title was not supplied, so title-to-content alignment could not be checked.",
                (
                    f"Try a truthful title built around “{topic}”, then compare it with the actual explanation."
                    if topic
                    else "Add the planned title and a transcript to check whether its promise is actually covered."
                ),
                priority="High",
                source_name="Packaging check",
            )
        elif supplied:
            title_terms = set(keywords(title))
            overlap = title_terms & set(re.findall(r"\w+", all_words.lower()))
            if len(title.split()) > 16 or len(title.split()) < 4 or not overlap:
                add(
                    "Align the title with the actual explanation",
                    f"The title “{title}” has {len(title.split())} words and {len(overlap)} matching topic terms in the provided transcript.",
                    f"Keep the main topic and a supported outcome. A starting direction is “{topic}: {specific[:100]}”. Check this against your footage and avoid unsupported results.",
                    priority="High",
                    source_name="Title + transcript",
                )

    if media:
        timeline = media.get("timeline", [])
        overlays = [f for f in timeline if len(keywords(f.get("overlayText", ""))) >= 2]
        transcript_terms = set(re.findall(r"\w+", all_words.lower()))
        if (
            supplied
            and overlays
            and not any(
                set(keywords(f["overlayText"])) & transcript_terms for f in overlays
            )
        ):
            observed = overlays[0]
            add(
                "Check the transcript against the on-screen wording",
                f"OCR estimates “{observed['overlayText'][:160]}” at {timestamp(observed['timestamp'])}, without matching topic terms in the supplied transcript. OCR or captions may be wrong, or the difference may be intentional.",
                "Inspect this frame and verify that these subtitles belong to this video. If the visual label is unrelated to the spoken point, make that relationship clear in the edit.",
                {"start": observed["timestamp"], "text": observed["overlayText"]},
                "High",
                "Transcript + estimated frame text",
            )
        dark = next(
            (f for f in timeline if f["brightness"] < 40 or f["brightness"] > 225), None
        )
        if dark:
            add(
                "Inspect the exposure at this point",
                f"At {timestamp(dark['timestamp'])}, sampled luminance is {dark['brightness']}/255 with {dark['clippedPercent']}% clipped pixels. A stylized or title frame may explain this.",
                "Use the sampled frame below to verify the issue. Adjust exposure in this section if important details are lost, then compare the re-export.",
                {"start": dark["timestamp"], "text": dark.get("overlayText", "")},
                "Medium",
                "Sampled frame",
            )
        quiet = next(
            (
                a
                for a in media.get("audioWindows", [])
                if a.get("meanDb") is not None and a["meanDb"] < -35
            ),
            None,
        )
        if quiet:
            add(
                "Check the quiet audio sample",
                f"The audio sample starting at {timestamp(quiet['timestamp'])} averages {quiet['meanDb']} dBFS. Silence, music or a transition may be intentional.",
                "Listen to this section. If speech should be audible, reduce background interference and adjust the voice level without clipping.",
                {"start": quiet["timestamp"], "text": ""},
                "Medium",
                "Measured audio window",
            )
        if not media.get("hasAudio"):
            add(
                "Decide how the message is delivered",
                "The uploaded video has no audio track.",
                f"If this is a silent {topic or 'visual'} demonstration, make its steps legible on screen. Otherwise export with the intended narration or sound track.",
                priority="Medium",
                source_name="Stream metadata",
            )

    hooks = list(
        dict.fromkeys(
            h
            for h in [
                specific[:180],
                (
                    f"{title or topic}: {specific[:145]}"
                    if (title or topic) and specific
                    else ""
                ),
                f"Here's the key step: {specific[:150]}" if specific else "",
            ]
            if h
        )
    )[:3]
    return {
        "source": source or "Video measurements only",
        "hasTranscript": supplied,
        "timedSegments": len(timed),
        "passages": len(segments),
        "keywords": terms,
        "topic": topic,
        "openingQuote": opening[:250],
        "closingQuote": last["text"][:250] if last else "",
        "chapters": chapters,
        "recommendations": recs,
        "hooks": hooks,
        "cta": cta,
        "words": all_words,
        "longForm": long,
        "coverage": "Provided words are reviewed as supplied, not verified speech recognition. Frame text is OCR and may contain errors. Sparse frame and audio samples do not measure audience retention or identify visual subjects.",
    }
