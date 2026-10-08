"""Publish a credential-free check summary to a separate GitHub results branch."""

import json
import os
import pathlib
import re
import subprocess
import tempfile
from datetime import datetime, timezone


def git(*args, input=None, env=None):
    return subprocess.check_output(
        ["git", *args], input=input, text=True, env=env
    ).strip()


def main():
    sha = os.environ["GITHUB_SHA"]
    assert re.fullmatch(r"[0-9a-f]{40}", sha)
    repository = os.environ["GITHUB_REPOSITORY"]
    run_url = (
        f"https://github.com/{repository}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
    )
    report_path = pathlib.Path("/tmp/trendsculpt-live-report.json")
    raw = json.loads(report_path.read_text()) if report_path.exists() else {}
    tests = []

    def visit(suites):
        for suite in suites:
            for spec in suite.get("specs", []):
                for test in spec.get("tests", []):
                    requests = []
                    errors = []
                    for result in test.get("results", []):
                        for item in result.get("stdout", []):
                            line = item.get("text", "").strip()
                            if line.startswith("LIVE_CHECK_HTTP "):
                                try:
                                    request = json.loads(
                                        line.removeprefix("LIVE_CHECK_HTTP ")
                                    )
                                    requests.append(
                                        {
                                            k: request[k]
                                            for k in ["method", "path", "status"]
                                        }
                                    )
                                except (ValueError, KeyError):
                                    pass
                        for error in result.get("errors", []):
                            message = re.sub(
                                r"\x1b\[[0-9;]*m", "", error.get("message", "")
                            )
                            lines = message.splitlines()
                            safe_lines = [lines[0]] if lines else []
                            safe_lines.extend(
                                line
                                for line in lines[1:]
                                if line.lstrip().startswith(
                                    (
                                        "Locator:",
                                        "- waiting",
                                        "- taking",
                                        "- screenshot",
                                        "- fonts",
                                        "- scrolling",
                                        "- checking",
                                    )
                                )
                            )
                            safe = "\n".join(safe_lines[:12])
                            safe = re.sub(
                                r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
                                "[test-email]",
                                safe,
                            )
                            safe = re.sub(
                                r"[0-9a-f]{8}-[0-9a-f-]{27}",
                                "[test-id]",
                                safe,
                                flags=re.I,
                            )
                            safe = re.sub(r"[A-Za-z0-9_-]{30,}", "[redacted]", safe)
                            for password in [
                                "Creator-test-password-42",
                                "New-creator-password-42",
                            ]:
                                safe = safe.replace(password, "[test-password]")
                            errors.append(
                                {"message": safe, "location": error.get("location")}
                            )
                    tests.append(
                        {
                            "name": spec["title"],
                            "status": test.get("status", "unknown"),
                            "attempts": len(test.get("results", [])),
                            "durationMs": sum(
                                r.get("duration", 0) for r in test.get("results", [])
                            ),
                            "httpResponses": requests,
                            "errors": errors,
                        }
                    )
            visit(suite.get("suites", []))

    visit(raw.get("suites", []))
    health_path = pathlib.Path("/tmp/trendsculpt-live-health.json")
    health = json.loads(health_path.read_text()) if health_path.exists() else {}
    passed = len(tests) == 6 and all(
        t["status"] in {"expected", "flaky"} for t in tests
    )
    summary = {
        "site": "https://trendsculpt.onrender.com",
        "testedAt": datetime.now(timezone.utc).isoformat(),
        "commit": sha,
        "passed": passed,
        "health": {
            k: health.get(k)
            for k in ["ok", "storage", "hostedStorage", "emailDelivery"]
        },
        "tests": tests,
        "runUrl": run_url,
        "cleanup": "Temporary accounts are removed by each browser test fixture; cleanup errors fail their tests.",
    }
    # Never publish raw JSON test reports, logs, passwords, recovery codes,
    # cookies, uploaded content, or account identifiers.
    data = json.dumps(summary, indent=2) + "\n"
    rows = "\n".join(f"| {t['name']} | {t['status']} |" for t in tests)
    markdown = (
        f"# TrendSculpt live check\n\nStatus: {'PASS' if passed else 'FAIL'}\n\n"
        f"[Workflow details]({run_url})\n\n"
        f"Target: https://trendsculpt.onrender.com\n\n"
        f"| Journey | Result |\n|---|---|\n{rows}\n\n"
        "Only credential-free check results are published here.\n"
    )
    if os.environ.get("TRENDSCULPT_RESULT_DRY_RUN") == "true":
        print(data)
        return
    if (
        os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("TRENDSCULPT_TEST_URL") != "https://trendsculpt.onrender.com"
        or repository != "js10-beep/trendsculpt"
    ):
        raise RuntimeError(
            "Publish results only from the authorized live-site workflow."
        )
    branch = "live-check-results"
    remote = git("ls-remote", "--heads", "origin", "refs/heads/" + branch)
    parent = None
    if remote:
        git("fetch", "origin", "refs/heads/" + branch)
        parent = git("rev-parse", "FETCH_HEAD")
    fd, index = tempfile.mkstemp(prefix="trendsculpt-check-index-")
    os.close(fd)
    os.unlink(index)
    env = {**os.environ, "GIT_INDEX_FILE": index}
    try:
        git("read-tree", parent if parent else "--empty", env=env)
        for path, content in [
            (f"checks/{sha}.json", data),
            ("latest.json", data),
            ("README.md", markdown),
        ]:
            blob = git("hash-object", "-w", "--stdin", input=content)
            git(
                "update-index", "--add", "--cacheinfo", f"100644,{blob},{path}", env=env
            )
        tree = git("write-tree", env=env)
        args = [
            "-c",
            "user.name=github-actions[bot]",
            "-c",
            "user.email=41898282+github-actions[bot]@users.noreply.github.com",
            "commit-tree",
            tree,
        ]
        if parent:
            args.extend(["-p", parent])
        args.extend(["-m", "Record TrendSculpt live browser checks"])
        commit = git(*args)
        git("push", "origin", f"{commit}:refs/heads/{branch}")
    finally:
        pathlib.Path(index).unlink(missing_ok=True)
        pathlib.Path(index + ".lock").unlink(missing_ok=True)
    print(f"Published sanitized live check results: {run_url}")


if __name__ == "__main__":
    main()
