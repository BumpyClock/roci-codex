#!/usr/bin/env python3
"""Execute the workflow's actual Bash detector and required fan-in in temp Git repos."""

import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/rust-ci.yml"


def step_body(marker):
    text = WORKFLOW.read_text().split(marker, 1)[1].split("run: |\n", 1)[1]
    lines = []
    for line in text.splitlines():
        if line and not line.startswith("          "):
            break
        lines.append(line[10:])
    return "\n".join(lines)


class ChangedPathsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.git("init", "-q")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "user.name", "CI fixture")
        self.commit("docs/guide.md")
        self.base = self.git("rev-parse", "HEAD").strip()

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.repo, text=True)

    def commit(self, path):
        file = self.repo / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("fixture\n")
        self.git("add", "--", path)
        self.git("commit", "-qm", "fixture")

    def detect(self, base=None, head="HEAD", event="pull_request"):
        body = step_body("- name: Detect changed paths (no external action)")
        # Also runs the pre-repair inline detector, so the regression can be demonstrated.
        values = {"github.event_name": event, "github.event.pull_request.base.sha": base or self.base,
                  "github.event.pull_request.head.sha": head}
        body = re.sub(r"\$\{\{ (.*?) \}\}", lambda m: values[m[1]], body)
        output = self.repo / "outputs"
        output.write_text("")
        result = subprocess.run(["bash", "-c", body], cwd=self.repo, capture_output=True,
                                text=True, env={**os.environ, "GITHUB_OUTPUT": str(output),
                                "GITHUB_EVENT_NAME": event, "BASE_SHA": base or self.base,
                                "HEAD_SHA": head})
        return result, dict(line.split("=", 1) for line in output.read_text().splitlines())

    def test_bad_refs_never_emit_skip_outputs(self):
        for base, head in [("missing-base", "HEAD"), (self.base, "missing-head")]:
            with self.subTest(base=base, head=head):
                result, outputs = self.detect(base, head)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(outputs, {})

    def test_rust_rename_and_deletion(self):
        self.commit("codex-rs/file with spaces.rs")
        base = self.git("rev-parse", "HEAD").strip()
        self.git("mv", "codex-rs/file with spaces.rs", "docs/renamed.md")
        self.git("commit", "-qm", "rename")
        result, outputs = self.detect(base)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(outputs["codex"], "true")
        self.commit("codex-rs/deleted.rs")
        base = self.git("rev-parse", "HEAD").strip()
        self.git("rm", "codex-rs/deleted.rs")
        self.git("commit", "-qm", "delete")
        result, outputs = self.detect(base)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(outputs["codex"], "true")

    def test_shared_and_hidden_rust_changes(self):
        for path in ["MODULE.bazel", ".cargo/config.toml", "rust-toolchain.toml", "justfile",
                     "docs/hidden.rs", "unknown/new-input", "codex-rs/.hidden/input.rs"]:
            with self.subTest(path=path):
                base = self.git("rev-parse", "HEAD").strip()
                self.commit(path)
                result, outputs = self.detect(base)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(outputs["codex"], "true")
                self.assertEqual(outputs["argument_comment_lint"], "true")

    def test_workflow_and_manual_full_scope(self):
        self.commit(".github/scripts/detector.py")
        for event in ["pull_request", "workflow_dispatch", "push"]:
            with self.subTest(event=event):
                result, outputs = self.detect(event=event)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(set(outputs.values()), {"true"})

    def test_empty_and_documentation_only_diff(self):
        for path in [None, "docs/guide.md"]:
            if path:
                (self.repo / path).write_text("updated\n")
                self.git("commit", "-qam", "docs")
            result, outputs = self.detect()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(set(outputs.values()), {"false"})

    def test_failed_or_missing_detector_cannot_pass_required_aggregate(self):
        body = step_body("- name: Summarize")
        for state in ["failure", "cancelled", "skipped", "", "success"]:
            with self.subTest(state=state):
                rendered = re.sub(r"\$\{\{ needs\.changed\.result \}\}", state, body)
                rendered = re.sub(r"\$\{\{ .*? \}\}", "skipped", rendered)
                env = {**os.environ, "NEEDS_CHANGED_RESULT": state}
                for key in ["ARGUMENT_COMMENT_LINT", "CODEX", "WORKFLOWS", "ARGUMENT_COMMENT_LINT_PACKAGE"]:
                    env["NEEDS_CHANGED_OUTPUTS_" + key] = ""
                result = subprocess.run(["bash", "-c", rendered], cwd=self.repo, env=env,
                                        capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)

    def test_successful_docs_only_aggregate_and_required_full_checks(self):
        body = re.sub(r"\$\{\{ .*? \}\}", "skipped", step_body("- name: Summarize"))
        for value, expected in [("false", 0), ("true", 1)]:
            env = {**os.environ, "NEEDS_CHANGED_RESULT": "success"}
            for key in ["ARGUMENT_COMMENT_LINT", "CODEX", "WORKFLOWS", "ARGUMENT_COMMENT_LINT_PACKAGE"]:
                env["NEEDS_CHANGED_OUTPUTS_" + key] = value
            result = subprocess.run(["bash", "-c", body], cwd=self.repo, env=env,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, expected)

    def test_outer_required_aggregate_propagates_child_failure(self):
        for state, expected in [("success", 0), ("failure", 1), ("cancelled", 1), ("skipped", 1)]:
            needs = {"rust-ci": {"result": state}, "sdk": {"result": "success"}}
            result = subprocess.run(["python3", str(ROOT / ".github/scripts/check_ci_results.py")],
                                    env={**os.environ, "NEEDS": json.dumps(needs)},
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, expected)


if __name__ == "__main__":
    unittest.main()
