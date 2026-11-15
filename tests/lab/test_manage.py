"""Offline launcher tests; no Docker process or network is dispatched."""
import contextlib
import io
import subprocess
import unittest
from unittest.mock import patch
import manage


class LauncherTests(unittest.TestCase):
    def test_existing_project_is_never_started_or_cleaned(self):
        result = subprocess.CompletedProcess([], 0, b"existing-container\n", b"")
        with patch.multiple(manage, COMPOSE=list(manage.COMPOSE), PROJECT="epochguard-lab", TEST_PORT=8787, IMAGE_PREFIX="epochguard"), patch.object(manage.sys, "argv", ["manage.py", "test", "--build", "--project-name", "isolated-test", "--test-port", "18787"]), patch.object(manage, "run", return_value=result) as run, contextlib.redirect_stderr(io.StringIO()) as output:
            with self.assertRaises(SystemExit) as caught:
                manage.main()
        self.assertEqual(caught.exception.code, 1)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[0][-3:], ["ps", "--all", "--quiet"])
        self.assertIn("No existing stack changed", output.getvalue())

    def test_interactive_port_cannot_change_application_origin(self):
        with patch.multiple(manage, IMAGE_PREFIX="epochguard"), patch.object(manage.sys, "argv", ["manage.py", "up", "--test-port", "18787"]), patch.object(manage, "run") as run, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                manage.main()
        self.assertEqual(caught.exception.code, 2)
        run.assert_not_called()

    def test_context_failure_is_actionable_without_reflecting_output(self):
        private = b"UNVERIFIED_SENTINEL secret arbitrary command/path"
        result = subprocess.CompletedProcess([], 1, b"", b'ERROR: use `docker --context=default buildx` to switch to context "default"' + private)
        with patch.object(manage.subprocess, "run", return_value=result):
            with self.assertRaises(manage.StageFailure) as caught:
                manage.run(["docker"], name="build dev/Dockerfile")
        self.assertIn("build dev/Dockerfile: builder/context mismatch", str(caught.exception))
        self.assertNotIn("SENTINEL", str(caught.exception))
        self.assertNotIn("secret", str(caught.exception))

    def test_network_unknown_and_timeout_errors_do_not_reflect_input(self):
        for data in (b"no such host PRIVATE", b"unknown PRIVATE", b"Pool overlaps PRIVATE", b"error from sender: Access is denied PRIVATE"):
            self.assertNotIn("PRIVATE", manage.diagnosis(data))
        with patch.object(manage.subprocess, "run", side_effect=subprocess.TimeoutExpired("PRIVATE", 1, output=b"PRIVATE")):
            with self.assertRaisesRegex(manage.StageFailure, "deadline exceeded"):
                manage.run(["docker"], name="startup")

    def test_builder_selection_and_private_base_namespace(self):
        for builder in (None, "desktop-linux"):
            with patch.object(manage, "IMAGE_PREFIX", "cold-005b"), patch.object(manage, "run") as run, contextlib.redirect_stdout(io.StringIO()):
                manage.build_images(builder)
            commands = [call.args[0] for call in run.call_args_list]
            self.assertEqual("--builder" in commands[0], builder is not None)
            self.assertEqual("--builder" in commands[1], builder is not None)
            self.assertIn("cold-005b-dev:002a", commands[0])
            self.assertIn("VERIFIER_BASE=cold-005b-verifier:004c", commands[2])
            self.assertIn("VERIFIER_BASE=cold-005b-verifier:004e", commands[3])

    def test_credential_environment_is_not_inherited(self):
        with patch.dict(manage.os.environ, {"TAVILY_API_KEY":"PRIVATE", "GEMINI_API_KEY":"PRIVATE", "OTHER_SECRET":"PRIVATE", "EPOCHGUARD_RUN_LIVE_004G":"1", "COMPOSE_ENV_FILES":"PRIVATE"}):
            env = manage.environment()
        self.assertFalse(any(value == "PRIVATE" for value in env.values()))
        self.assertEqual(env["COMPOSE_DISABLE_ENV_FILE"], "1")
        self.assertEqual(env["EPOCHGUARD_LAB_IMAGE_PREFIX"], "epochguard")

    def test_cleanup_failure_is_visible_and_sanitized(self):
        with patch.object(manage, "run", return_value=subprocess.CompletedProcess([], 1)), contextlib.redirect_stderr(io.StringIO()) as output:
            self.assertFalse(manage.cleanup())
        self.assertIn("cleanup failed", output.getvalue())


if __name__ == "__main__":
    unittest.main()
