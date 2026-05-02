import configparser
import io
import json
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import claudex


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


def _make_section(d):
    """Return a dict-like ConfigParser-style section for resolve_model / handlers."""
    return d


def _make_config(sections):
    """Return a ConfigParser instance populated with given sections dict."""
    cfg = configparser.ConfigParser()
    for name, items in sections.items():
        cfg.add_section(name)
        for k, v in items.items():
            cfg[name][k] = v
    return cfg


# ---------------------------------------------------------------------------
# TestLoadCredentials
# ---------------------------------------------------------------------------

class TestLoadCredentials(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmpdir.cleanup()

    def _fpath(self, name):
        return os.path.join(self.tmpdir.name, name)

    def test_nonexistent_file(self):
        self.assertEqual(claudex.load_credentials(self._fpath("nope")), {})

    def test_empty_file(self):
        _write(self._fpath("c"), "")
        self.assertEqual(claudex.load_credentials(self._fpath("c")), {})

    def test_single_provider(self):
        _write(self._fpath("c"), "deepseek=sk-abc123\n")
        self.assertEqual(claudex.load_credentials(self._fpath("c")), {"deepseek": "sk-abc123"})

    def test_multiple_providers(self):
        _write(self._fpath("c"), "deepseek=sk-a\nminimax=eyJb\n")
        self.assertEqual(claudex.load_credentials(self._fpath("c")), {"deepseek": "sk-a", "minimax": "eyJb"})

    def test_strips_whitespace(self):
        _write(self._fpath("c"), "  deepseek  =  sk-abc  \n")
        self.assertEqual(claudex.load_credentials(self._fpath("c")), {"deepseek": "sk-abc"})

    def test_strips_double_quotes(self):
        _write(self._fpath("c"), 'deepseek="sk-abc"\n')
        self.assertEqual(claudex.load_credentials(self._fpath("c")), {"deepseek": "sk-abc"})

    def test_strips_single_quotes(self):
        _write(self._fpath("c"), "deepseek='sk-abc'\n")
        self.assertEqual(claudex.load_credentials(self._fpath("c")), {"deepseek": "sk-abc"})

    def test_skips_blank_lines(self):
        _write(self._fpath("c"), "\n\ndeepseek=sk-a\n\n")
        self.assertEqual(claudex.load_credentials(self._fpath("c")), {"deepseek": "sk-a"})

    def test_skips_comment_lines(self):
        _write(self._fpath("c"), "# my key\ndeepseek=sk-a\n")
        self.assertEqual(claudex.load_credentials(self._fpath("c")), {"deepseek": "sk-a"})

    def test_hash_in_value_not_comment(self):
        _write(self._fpath("c"), "#comment\ndeepseek=sk-#notacomment\n")
        self.assertEqual(claudex.load_credentials(self._fpath("c")), {"deepseek": "sk-#notacomment"})

    def test_line_without_equals(self):
        _write(self._fpath("c"), "just some text\n")
        self.assertEqual(claudex.load_credentials(self._fpath("c")), {})

    def test_multiple_equals(self):
        _write(self._fpath("c"), "key=val=with=equals\n")
        self.assertEqual(claudex.load_credentials(self._fpath("c")), {"key": "val=with=equals"})


# ---------------------------------------------------------------------------
# TestResolveModel
# ---------------------------------------------------------------------------

class TestResolveModel(unittest.TestCase):
    def test_opus_explicit(self):
        self.assertEqual(claudex.resolve_model({"opus_model": "claude-opus-4"}, "opus"), "claude-opus-4")

    def test_opus_fallback_to_model(self):
        self.assertEqual(claudex.resolve_model({"model": "claude-sonnet-4"}, "opus"), "claude-sonnet-4")

    def test_opus_no_match(self):
        self.assertIsNone(claudex.resolve_model({}, "opus"))

    def test_opus_prefers_explicit_over_fallback(self):
        self.assertEqual(claudex.resolve_model({"opus_model": "opus-turbo", "model": "fallback"}, "opus"), "opus-turbo")

    def test_sonnet_explicit(self):
        self.assertEqual(claudex.resolve_model({"sonnet_model": "claude-sonnet-4"}, "sonnet"), "claude-sonnet-4")

    def test_sonnet_fallback_to_model(self):
        self.assertEqual(claudex.resolve_model({"model": "claude-haiku-4"}, "sonnet"), "claude-haiku-4")

    def test_sonnet_no_match(self):
        self.assertIsNone(claudex.resolve_model({}, "sonnet"))

    def test_haiku_explicit(self):
        self.assertEqual(claudex.resolve_model({"haiku_model": "claude-haiku-4"}, "haiku"), "claude-haiku-4")

    def test_haiku_fallback_small_fast_model(self):
        self.assertEqual(claudex.resolve_model({"small_fast_model": "claude-haiku-3.5"}, "haiku"), "claude-haiku-3.5")

    def test_haiku_fallback_to_model(self):
        self.assertEqual(claudex.resolve_model({"model": "catchall"}, "haiku"), "catchall")

    def test_haiku_prefers_explicit_over_small_fast(self):
        self.assertEqual(
            claudex.resolve_model({"haiku_model": "h1", "small_fast_model": "sf1"}, "haiku"), "h1"
        )

    def test_haiku_prefers_small_fast_over_model(self):
        self.assertEqual(
            claudex.resolve_model({"small_fast_model": "sf1", "model": "m1"}, "haiku"), "sf1"
        )

    def test_haiku_no_match(self):
        self.assertIsNone(claudex.resolve_model({}, "haiku"))

    def test_unknown_tier(self):
        self.assertIsNone(claudex.resolve_model({"model": "x"}, "bogus"))


# ---------------------------------------------------------------------------
# TestApplyModelOverrides
# ---------------------------------------------------------------------------

class TestApplyModelOverrides(unittest.TestCase):
    def test_all_explicit(self):
        s = {"opus_model": "o1", "sonnet_model": "s1", "haiku_model": "h1"}
        self.assertEqual(
            claudex._apply_model_overrides(s),
            {
                "ANTHROPIC_DEFAULT_OPUS_MODEL": "o1",
                "ANTHROPIC_DEFAULT_SONNET_MODEL": "s1",
                "ANTHROPIC_DEFAULT_HAIKU_MODEL": "h1",
            },
        )

    def test_only_model_fallback(self):
        s = {"model": "catchall"}
        self.assertEqual(
            claudex._apply_model_overrides(s),
            {
                "ANTHROPIC_DEFAULT_OPUS_MODEL": "catchall",
                "ANTHROPIC_DEFAULT_SONNET_MODEL": "catchall",
                "ANTHROPIC_DEFAULT_HAIKU_MODEL": "catchall",
            },
        )

    def test_mixed_explicit_and_fallback(self):
        s = {"opus_model": "o1", "model": "fallback"}
        self.assertEqual(
            claudex._apply_model_overrides(s),
            {
                "ANTHROPIC_DEFAULT_OPUS_MODEL": "o1",
                "ANTHROPIC_DEFAULT_SONNET_MODEL": "fallback",
                "ANTHROPIC_DEFAULT_HAIKU_MODEL": "fallback",
            },
        )

    def test_none_resolved(self):
        self.assertEqual(claudex._apply_model_overrides({}), {})

    def test_only_haiku_set(self):
        s = {"haiku_model": "h1"}
        self.assertEqual(claudex._apply_model_overrides(s), {"ANTHROPIC_DEFAULT_HAIKU_MODEL": "h1"})


# ---------------------------------------------------------------------------
# TestFmtLine
# ---------------------------------------------------------------------------

class TestFmtLine(unittest.TestCase):
    def test_with_color(self):
        result = claudex._fmt_line("Label:", "value", claudex.CYAN)
        self.assertIn("Label:", result)
        self.assertIn("value", result)
        self.assertIn(claudex.CYAN, result)
        self.assertIn(claudex.NC, result)

    def test_without_color(self):
        result = claudex._fmt_line("Label:", "value", "")
        self.assertIn("Label:", result)
        self.assertIn("value", result)

    def test_label_padding(self):
        result = claudex._fmt_line("Short:", "v", "")
        self.assertTrue(result.startswith("  Short:"))


# ---------------------------------------------------------------------------
# TestLoadSettings
# ---------------------------------------------------------------------------

class TestLoadSettings(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmpdir.cleanup()

    def _path(self, name):
        return os.path.join(self.tmpdir.name, name)

    def test_nonexistent(self):
        self.assertEqual(claudex._load_settings(self._path("nope")), {})

    def test_valid_json(self):
        _write(self._path("s.json"), '{"env": {"KEY": "val"}}')
        self.assertEqual(claudex._load_settings(self._path("s.json")), {"env": {"KEY": "val"}})

    def test_invalid_json(self):
        _write(self._path("s.json"), "not json{{{")
        with patch("sys.stderr", new=io.StringIO()) as stderr:
            result = claudex._load_settings(self._path("s.json"))
        self.assertEqual(result, {})
        self.assertIn("Warning", stderr.getvalue())

    def test_empty_json_object(self):
        _write(self._path("s.json"), "{}")
        self.assertEqual(claudex._load_settings(self._path("s.json")), {})

    def test_permission_error_exits(self):
        p = self._path("s.json")
        _write(p, '{"env": {}}')
        with patch("sys.stderr", new=io.StringIO()) as stderr:
            with patch("builtins.open", side_effect=PermissionError("Permission denied")):
                with self.assertRaises(SystemExit):
                    claudex._load_settings(p)
        self.assertIn("Cannot read", stderr.getvalue())


# ---------------------------------------------------------------------------
# TestSaveSettings
# ---------------------------------------------------------------------------

class TestSaveSettings(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmpdir.cleanup()

    def _path(self, name):
        return os.path.join(self.tmpdir.name, name)

    def test_creates_parent_dirs(self):
        p = os.path.join(self.tmpdir.name, "sub", "deep", "settings.json")
        claudex._save_settings(p, {"a": 1})
        self.assertTrue(os.path.exists(p))

    def test_writes_indented_json(self):
        p = self._path("s.json")
        claudex._save_settings(p, {"env": {"KEY": "val"}})
        with open(p) as f:
            raw = f.read()
        self.assertIn('\n  "env"', raw)

    def test_adds_trailing_newline(self):
        p = self._path("s.json")
        claudex._save_settings(p, {"a": 1})
        with open(p) as f:
            raw = f.read()
        self.assertTrue(raw.endswith("\n"))

    def test_roundtrip(self):
        p = self._path("s.json")
        data = {"env": {"A": "1", "B": "2"}}
        claudex._save_settings(p, data)
        self.assertEqual(claudex._load_settings(p), data)


# ---------------------------------------------------------------------------
# TestMergeSettings
# ---------------------------------------------------------------------------

class TestMergeSettings(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmpdir.cleanup()

    def _spath(self):
        return os.path.join(self.tmpdir.name, "settings.json")

    def test_empty_updates_noop(self):
        p = self._spath()
        _write(p, '{"env": {"EXISTING": "keep"}}')
        claudex.merge_settings(p, {})
        data = claudex._load_settings(p)
        self.assertEqual(data, {"env": {"EXISTING": "keep"}})

    def test_sets_new_env_var(self):
        p = self._spath()
        claudex.merge_settings(p, {"NEW_KEY": "val"})
        data = claudex._load_settings(p)
        self.assertEqual(data["env"]["NEW_KEY"], "val")

    def test_preserves_existing_env_vars(self):
        p = self._spath()
        _write(p, '{"env": {"OLD": "keep"}}')
        claudex.merge_settings(p, {"NEW": "add"})
        data = claudex._load_settings(p)
        self.assertEqual(data["env"], {"OLD": "keep", "NEW": "add"})

    def test_preserves_non_env_top_level_keys(self):
        p = self._spath()
        _write(p, '{"other": true, "env": {}}')
        claudex.merge_settings(p, {"K": "v"})
        data = claudex._load_settings(p)
        self.assertTrue(data["other"])
        self.assertEqual(data["env"]["K"], "v")

    def test_empty_string_deletes_key(self):
        p = self._spath()
        _write(p, '{"env": {"K": "v"}}')
        claudex.merge_settings(p, {"K": ""})
        data = claudex._load_settings(p)
        self.assertNotIn("K", data["env"])

    def test_none_value_noop_preserves(self):
        p = self._spath()
        _write(p, '{"env": {"K": "existing"}}')
        claudex.merge_settings(p, {"K": None})
        data = claudex._load_settings(p)
        self.assertEqual(data["env"]["K"], "existing")

    def test_file_does_not_exist_yet(self):
        p = self._spath()
        claudex.merge_settings(p, {"K": "v"})
        data = claudex._load_settings(p)
        self.assertEqual(data, {"env": {"K": "v"}})

    def test_overwrites_existing_value(self):
        p = self._spath()
        _write(p, '{"env": {"K": "old"}}')
        claudex.merge_settings(p, {"K": "new"})
        data = claudex._load_settings(p)
        self.assertEqual(data["env"]["K"], "new")


# ---------------------------------------------------------------------------
# TestClearProviderSettings
# ---------------------------------------------------------------------------

class TestClearProviderSettings(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmpdir.cleanup()

    def _spath(self):
        return os.path.join(self.tmpdir.name, "settings.json")

    def test_nonexistent_file(self):
        claudex.clear_provider_settings(self._spath())

    def test_invalid_json(self):
        p = self._spath()
        _write(p, "garbage")
        with patch("sys.stderr", new=io.StringIO()) as stderr:
            claudex.clear_provider_settings(p)
        self.assertIn("Warning", stderr.getvalue())

    def test_removes_all_provider_keys(self):
        p = self._spath()
        env = {k: "set" for k in claudex.PROVIDER_ENV_KEYS}
        _write(p, json.dumps({"env": env}))
        claudex.clear_provider_settings(p)
        data = claudex._load_settings(p)
        for k in claudex.PROVIDER_ENV_KEYS:
            self.assertNotIn(k, data["env"])

    def test_preserves_non_provider_env_keys(self):
        p = self._spath()
        _write(p, '{"env": {"ANTHROPIC_BASE_URL": "https://x.com", "CUSTOM": "keep-me"}}')
        claudex.clear_provider_settings(p)
        data = claudex._load_settings(p)
        self.assertNotIn("ANTHROPIC_BASE_URL", data["env"])
        self.assertEqual(data["env"]["CUSTOM"], "keep-me")

    def test_preserves_non_env_top_level_keys(self):
        p = self._spath()
        _write(p, '{"other": 42, "env": {"ANTHROPIC_BASE_URL": "x"}}')
        claudex.clear_provider_settings(p)
        data = claudex._load_settings(p)
        self.assertEqual(data["other"], 42)
        self.assertNotIn("ANTHROPIC_BASE_URL", data["env"])

    def test_no_env_key_in_file(self):
        p = self._spath()
        _write(p, '{"other": 1}')
        claudex.clear_provider_settings(p)
        data = claudex._load_settings(p)
        self.assertEqual(data, {"other": 1, "env": {}})


# ---------------------------------------------------------------------------
# TestHandleOllama
# ---------------------------------------------------------------------------

def _ollama_section(d):
    """Return a real ConfigParser section for handle_ollama tests."""
    cfg = configparser.ConfigParser()
    cfg.add_section("ollama")
    for k, v in d.items():
        cfg["ollama"][k] = v
    return cfg["ollama"]


class TestHandleOllama(unittest.TestCase):
    def test_minimal_section(self):
        result = claudex.handle_ollama(_ollama_section({}))
        self.assertEqual(result["ANTHROPIC_BASE_URL"], "http://localhost:11434")
        self.assertEqual(result["ANTHROPIC_AUTH_TOKEN"], "ollama")
        self.assertEqual(result["ANTHROPIC_API_KEY"], "")
        self.assertEqual(result["API_TIMEOUT_MS"], "600000")
        self.assertEqual(result["NONESSENTIAL_TRAFFIC"], "1")
        self.assertNotIn("ANTHROPIC_DEFAULT_OPUS_MODEL", result)

    def test_custom_host(self):
        result = claudex.handle_ollama(_ollama_section({"host": "http://10.0.0.1:11434"}))
        self.assertEqual(result["ANTHROPIC_BASE_URL"], "http://10.0.0.1:11434")

    def test_with_model(self):
        result = claudex.handle_ollama(_ollama_section({"model": "llama3:8b"}))
        self.assertEqual(result["ANTHROPIC_DEFAULT_OPUS_MODEL"], "llama3:8b")
        self.assertEqual(result["ANTHROPIC_DEFAULT_SONNET_MODEL"], "llama3:8b")
        self.assertEqual(result["ANTHROPIC_DEFAULT_HAIKU_MODEL"], "llama3:8b")

    def test_custom_timeout(self):
        result = claudex.handle_ollama(_ollama_section({"timeout_ms": "300000"}))
        self.assertEqual(result["API_TIMEOUT_MS"], "300000")

    def test_custom_nonessential(self):
        result = claudex.handle_ollama(_ollama_section({"nonessential_traffic": "0"}))
        self.assertEqual(result["NONESSENTIAL_TRAFFIC"], "0")

    def test_full_section(self):
        s = _ollama_section({
            "host": "http://0.0.0.0:9999",
            "model": "mixtral",
            "timeout_ms": "999999",
            "nonessential_traffic": "0",
        })
        result = claudex.handle_ollama(s)
        self.assertEqual(result["ANTHROPIC_BASE_URL"], "http://0.0.0.0:9999")
        self.assertEqual(result["ANTHROPIC_DEFAULT_OPUS_MODEL"], "mixtral")
        self.assertEqual(result["API_TIMEOUT_MS"], "999999")
        self.assertEqual(result["NONESSENTIAL_TRAFFIC"], "0")


# ---------------------------------------------------------------------------
# TestHandleStandardProvider
# ---------------------------------------------------------------------------

def _std_section(d):
    """Return a real ConfigParser section for handle_standard_provider tests."""
    cfg = configparser.ConfigParser()
    cfg.add_section("testprov")
    for k, v in d.items():
        cfg["testprov"][k] = v
    return cfg["testprov"]


class TestHandleStandardProvider(unittest.TestCase):
    def test_api_key_from_credentials(self):
        result = claudex.handle_standard_provider(
            _std_section({"base_url": "https://api.example.com"}), "testprov", {"testprov": "sk-abc"}
        )
        self.assertEqual(result["ANTHROPIC_AUTH_TOKEN"], "sk-abc")
        self.assertEqual(result["ANTHROPIC_API_KEY"], "")

    def test_api_key_from_section_fallback(self):
        result = claudex.handle_standard_provider(
            _std_section({"base_url": "https://api.example.com", "api_key": "sk-xyz"}), "testprov", {}
        )
        self.assertEqual(result["ANTHROPIC_AUTH_TOKEN"], "sk-xyz")
        self.assertEqual(result["ANTHROPIC_API_KEY"], "")

    def test_api_key_without_base_url_sets_auth_token(self):
        result = claudex.handle_standard_provider(
            _std_section({}), "testprov", {"testprov": "sk-abc"}
        )
        self.assertEqual(result["ANTHROPIC_AUTH_TOKEN"], "sk-abc")
        self.assertEqual(result["ANTHROPIC_API_KEY"], "")
        self.assertNotIn("ANTHROPIC_BASE_URL", result)

    def test_no_api_key_at_all(self):
        result = claudex.handle_standard_provider(_std_section({}), "testprov", {})
        self.assertNotIn("ANTHROPIC_API_KEY", result)
        self.assertNotIn("ANTHROPIC_AUTH_TOKEN", result)

    def test_base_url_set(self):
        result = claudex.handle_standard_provider(
            _std_section({"base_url": "https://api.example.com"}), "testprov", {}
        )
        self.assertEqual(result["ANTHROPIC_BASE_URL"], "https://api.example.com")

    def test_model_overrides_applied(self):
        result = claudex.handle_standard_provider(
            _std_section({"opus_model": "o1"}), "testprov", {}
        )
        self.assertEqual(result["ANTHROPIC_DEFAULT_OPUS_MODEL"], "o1")

    def test_timeout_set(self):
        result = claudex.handle_standard_provider(
            _std_section({"timeout_ms": "120000"}), "testprov", {}
        )
        self.assertEqual(result["API_TIMEOUT_MS"], "120000")

    def test_timeout_not_set(self):
        result = claudex.handle_standard_provider(_std_section({}), "testprov", {})
        self.assertNotIn("API_TIMEOUT_MS", result)

    def test_nonessential_traffic_default_empty(self):
        result = claudex.handle_standard_provider(_std_section({}), "testprov", {})
        self.assertEqual(result["NONESSENTIAL_TRAFFIC"], "")

    def test_nonessential_traffic_set(self):
        result = claudex.handle_standard_provider(
            _std_section({"nonessential_traffic": "0"}), "testprov", {}
        )
        self.assertEqual(result["NONESSENTIAL_TRAFFIC"], "0")

    def test_credentials_preferred_over_section_api_key(self):
        result = claudex.handle_standard_provider(
            _std_section({"base_url": "https://api.example.com", "api_key": "sk-section"}),
            "testprov",
            {"testprov": "sk-cred"},
        )
        self.assertEqual(result["ANTHROPIC_AUTH_TOKEN"], "sk-cred")


# ---------------------------------------------------------------------------
# TestDetectActiveProvider
# ---------------------------------------------------------------------------

class TestDetectActiveProvider(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmpdir.cleanup()

    def _set_settings(self, env_dict):
        path = os.path.join(self.tmpdir.name, "settings.json")
        _write(path, json.dumps({"env": env_dict}))
        return path

    def _test(self, env_dict, config, expected):
        path = self._set_settings(env_dict)
        with patch("claudex.SETTINGS_PATH", path):
            result = claudex._detect_active_provider(config)
        self.assertEqual(result, expected)

    def test_anthropic_default(self):
        self._test({}, _make_config({}), ("anthropic", None))

    def test_anthropic_empty_strings(self):
        self._test(
            {"ANTHROPIC_BASE_URL": "", "ANTHROPIC_AUTH_TOKEN": ""},
            _make_config({}),
            ("anthropic", None),
        )

    def test_ollama_auth_token_with_section(self):
        config = _make_config({"ollama": {"host": "http://localhost:11434", "model": "llama3"}})
        self._test({"ANTHROPIC_AUTH_TOKEN": "ollama"}, config, ("ollama", config["ollama"]))

    def test_ollama_auth_token_no_section(self):
        self._test({"ANTHROPIC_AUTH_TOKEN": "ollama"}, _make_config({}), ("ollama", None))

    def test_base_url_match(self):
        config = _make_config({"deepseek": {"base_url": "https://api.deepseek.com/anthropic"}})
        self._test(
            {"ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic"},
            config,
            ("deepseek", config["deepseek"]),
        )

    def test_base_url_no_match(self):
        self._test(
            {"ANTHROPIC_BASE_URL": "https://unknown.example.com"},
            _make_config({"deepseek": {"base_url": "https://api.deepseek.com/anthropic"}}),
            (None, None),
        )

    def test_skips_anthropic_section(self):
        config = _make_config({"anthropic": {"base_url": "https://api.anthropic.com"}})
        self._test(
            {"ANTHROPIC_BASE_URL": "https://api.anthropic.com"}, config, (None, None)
        )

    def test_auth_token_set_but_unrecognized(self):
        self._test({"ANTHROPIC_AUTH_TOKEN": "sk-xyz"}, _make_config({}), (None, None))


# ---------------------------------------------------------------------------
# TestCmdList
# ---------------------------------------------------------------------------

class TestCmdList(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_lists_anthropic_always(self):
        with patch("sys.stdout", new=io.StringIO()) as stdout:
            with patch("claudex.PROVIDERS_PATH", os.path.join(self.tmpdir.name, "nonexistent.ini")):
                claudex.cmd_list()
        out = stdout.getvalue()
        self.assertIn("anthropic (default)", out)

    def test_lists_providers_from_ini(self):
        ini_path = os.path.join(self.tmpdir.name, "providers.ini")
        _write(ini_path, "[deepseek]\nbase_url=https://x.com\n[ollama]\n")
        with patch("sys.stdout", new=io.StringIO()) as stdout:
            with patch("claudex.PROVIDERS_PATH", ini_path):
                claudex.cmd_list()
        out = stdout.getvalue()
        self.assertIn("deepseek", out)
        self.assertIn("ollama", out)

    def test_no_providers_ini_file(self):
        with patch("sys.stdout", new=io.StringIO()) as stdout:
            with patch("claudex.PROVIDERS_PATH", os.path.join(self.tmpdir.name, "missing.ini")):
                claudex.cmd_list()
        out = stdout.getvalue()
        self.assertIn("anthropic (default)", out)


# ---------------------------------------------------------------------------
# TestCmdStatus
# ---------------------------------------------------------------------------

class TestCmdStatus(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.config_dir = os.path.join(self.tmpdir.name, "config")
        os.makedirs(self.config_dir, exist_ok=True)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _set_settings(self, env_dict):
        path = os.path.join(self.tmpdir.name, "settings.json")
        _write(path, json.dumps({"env": env_dict}))
        path_patcher = patch("claudex.SETTINGS_PATH", path)
        path_patcher.start()
        self.addCleanup(path_patcher.stop)
        return path

    def _set_providers(self, content):
        path = os.path.join(self.config_dir, "providers.ini")
        _write(path, content)
        path_patcher = patch("claudex.PROVIDERS_PATH", path)
        path_patcher.start()
        self.addCleanup(path_patcher.stop)

    def test_status_anthropic_active(self):
        self._set_settings({})
        with patch("sys.stdout", new=io.StringIO()) as stdout:
            with patch("claudex.CONFIG_DIR", self.config_dir):
                claudex.cmd_status()
        out = stdout.getvalue()
        self.assertIn("anthropic", out.lower())

    def test_status_ollama_active(self):
        self._set_settings({"ANTHROPIC_AUTH_TOKEN": "ollama"})
        self._set_providers("[ollama]\nmodel=llama3\nhost=http://localhost:11434\n")
        with patch("sys.stdout", new=io.StringIO()) as stdout:
            with patch("claudex.CONFIG_DIR", self.config_dir):
                claudex.cmd_status()
        out = stdout.getvalue()
        self.assertIn("ollama", out.lower())
        self.assertIn("localhost:11434", out)

    def test_status_standard_provider_active(self):
        self._set_settings(
            {"ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic", "ANTHROPIC_AUTH_TOKEN": "sk-abc"}
        )
        self._set_providers("[deepseek]\nbase_url=https://api.deepseek.com/anthropic\n")
        with patch("sys.stdout", new=io.StringIO()) as stdout:
            with patch("claudex.CONFIG_DIR", self.config_dir):
                claudex.cmd_status()
        out = stdout.getvalue()
        self.assertIn("deepseek", out)

    def test_status_unknown_provider(self):
        self._set_settings({"ANTHROPIC_BASE_URL": "https://unknown.example.com"})
        with patch("sys.stdout", new=io.StringIO()) as stdout:
            with patch("claudex.CONFIG_DIR", self.config_dir):
                claudex.cmd_status()
        out = stdout.getvalue()
        self.assertIn("unknown", out.lower())

    def test_status_shows_config_dir(self):
        self._set_settings({})
        with patch("sys.stdout", new=io.StringIO()) as stdout:
            with patch("claudex.CONFIG_DIR", self.config_dir):
                claudex.cmd_status()
        out = stdout.getvalue()
        self.assertIn("Config:", out)

    def test_status_available_providers_with_active_dot(self):
        self._set_settings({"ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic", "ANTHROPIC_AUTH_TOKEN": "sk-abc"})
        self._set_providers("[deepseek]\nbase_url=https://api.deepseek.com/anthropic\n[ollama]\nhost=http://x\n")
        with patch("sys.stdout", new=io.StringIO()) as stdout:
            with patch("claudex.CONFIG_DIR", self.config_dir):
                claudex.cmd_status()
        out = stdout.getvalue()
        self.assertIn("deepseek", out)


# ---------------------------------------------------------------------------
# TestSwitchAndLaunch
# ---------------------------------------------------------------------------

class TestSwitchAndLaunch(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.config_dir = os.path.join(self.tmpdir.name, "config")
        os.makedirs(self.config_dir, exist_ok=True)

        self.providers_path = os.path.join(self.config_dir, "providers.ini")
        self.creds_path = os.path.join(self.config_dir, "credentials")
        self.settings_path = os.path.join(self.tmpdir.name, "settings.json")

        self.patch_providers = patch("claudex.PROVIDERS_PATH", self.providers_path)
        self.patch_creds = patch("claudex.CREDENTIALS_PATH", self.creds_path)
        self.patch_settings = patch("claudex.SETTINGS_PATH", self.settings_path)
        self.patch_execv = patch("os.execv")
        self.patch_which = patch("shutil.which", return_value="/usr/bin/claude")

        self.patch_providers.start()
        self.patch_creds.start()
        self.patch_settings.start()
        self.mock_execv = self.patch_execv.start()
        self.patch_which.start()
        self.patch_stderr = patch("sys.stderr", new=io.StringIO())
        self.patch_stderr.start()

    def tearDown(self):
        self.patch_stderr.stop()
        self.patch_providers.stop()
        self.patch_creds.stop()
        self.patch_settings.stop()
        self.patch_execv.stop()
        self.patch_which.stop()
        self.tmpdir.cleanup()

    def _write_providers(self, content):
        _write(self.providers_path, content)

    def _write_creds(self, content):
        _write(self.creds_path, content)

    def test_missing_providers_ini(self):
        self.assertFalse(os.path.exists(self.providers_path))
        with self.assertRaises(SystemExit):
            claudex.switch_and_launch("deepseek", [])

    def test_no_provider_name_defaults_to_anthropic(self):
        self._write_providers("[deepseek]\nbase_url=https://x.com\n")
        claudex.switch_and_launch("", [])
        self.mock_execv.assert_called_once_with("/usr/bin/claude", ["/usr/bin/claude"])

    def test_anthropic_with_model_overrides(self):
        self._write_providers("[anthropic]\nopus_model=claude-opus-4\n")
        claudex.switch_and_launch("anthropic", [])
        data = claudex._load_settings(self.settings_path)
        self.assertEqual(data["env"]["ANTHROPIC_DEFAULT_OPUS_MODEL"], "claude-opus-4")

    def test_anthropic_no_model_overrides(self):
        self._write_providers("[deepseek]\nbase_url=https://x.com\n")
        claudex.switch_and_launch("anthropic", [])
        data = claudex._load_settings(self.settings_path)
        self.assertNotIn("ANTHROPIC_DEFAULT_OPUS_MODEL", data.get("env", {}))

    def test_ollama_basic(self):
        self._write_providers("[ollama]\nmodel=llama3\n")
        claudex.switch_and_launch("ollama", [])
        data = claudex._load_settings(self.settings_path)
        self.assertEqual(data["env"]["ANTHROPIC_AUTH_TOKEN"], "ollama")

    def test_unknown_provider(self):
        self._write_providers("[deepseek]\nbase_url=https://x.com\n")
        with self.assertRaises(SystemExit):
            claudex.switch_and_launch("bogus", [])

    def test_unknown_provider_with_suggestion(self):
        self._write_providers("[deepseek]\nbase_url=https://x.com\n")
        with patch("sys.stderr", new=io.StringIO()) as stderr:
            with self.assertRaises(SystemExit):
                claudex.switch_and_launch("deapseek", [])
        self.assertIn("deepseek", stderr.getvalue())

    def test_unknown_provider_no_suggestion(self):
        self._write_providers("[deepseek]\nbase_url=https://x.com\n")
        with patch("sys.stderr", new=io.StringIO()) as stderr:
            with self.assertRaises(SystemExit):
                claudex.switch_and_launch("xyzzz", [])
        self.assertNotIn("Did you mean", stderr.getvalue())

    def test_standard_provider_missing_credentials(self):
        self._write_providers("[deepseek]\nbase_url=https://api.deepseek.com/anthropic\n")
        with self.assertRaises(SystemExit):
            claudex.switch_and_launch("deepseek", [])

    def test_standard_provider_missing_base_url(self):
        self._write_providers("[deepseek]\n")
        self._write_creds("deepseek=sk-abc\n")
        with self.assertRaises(SystemExit):
            claudex.switch_and_launch("deepseek", [])

    def test_standard_provider_success(self):
        self._write_providers(
            "[deepseek]\nbase_url=https://api.deepseek.com/anthropic\nopus_model=deepseek-v4\n"
        )
        self._write_creds("deepseek=sk-abc\n")
        claudex.switch_and_launch("deepseek", ["--extra"])
        data = claudex._load_settings(self.settings_path)
        self.assertEqual(data["env"]["ANTHROPIC_AUTH_TOKEN"], "sk-abc")
        self.assertEqual(data["env"]["ANTHROPIC_BASE_URL"], "https://api.deepseek.com/anthropic")
        self.mock_execv.assert_called_once_with("/usr/bin/claude", ["/usr/bin/claude", "--extra"])

    def test_claude_not_in_path(self):
        self.patch_which.stop()
        with patch("shutil.which", return_value=None):
            self._write_providers(
                "[deepseek]\nbase_url=https://api.deepseek.com/anthropic\n"
            )
            self._write_creds("deepseek=sk-abc\n")
            with self.assertRaises(SystemExit):
                claudex.switch_and_launch("deepseek", [])
        # claude check now happens before settings write — nothing written
        data = claudex._load_settings(self.settings_path)
        self.assertEqual(data, {})
        # restart the patch for tearDown
        self.patch_which.start()


# ---------------------------------------------------------------------------
# TestMainDispatch
# ---------------------------------------------------------------------------

class TestMainDispatch(unittest.TestCase):
    def setUp(self):
        self.patch_execv = patch("os.execv")
        self.patch_which = patch("shutil.which", return_value="/usr/bin/claude")
        self.mock_execv = self.patch_execv.start()
        self.patch_which.start()
        self.patch_stderr = patch("sys.stderr", new=io.StringIO())
        self.patch_stderr.start()

    def tearDown(self):
        self.patch_stderr.stop()
        self.patch_execv.stop()
        self.patch_which.stop()

    def test_no_args_no_claude(self):
        with patch("shutil.which", return_value=None):
            with patch("sys.argv", ["claudex"]):
                with self.assertRaises(SystemExit):
                    claudex.main()

    def test_no_args_with_claude(self):
        with patch("sys.argv", ["claudex"]):
            claudex.main()
        self.mock_execv.assert_called_once_with("/usr/bin/claude", ["/usr/bin/claude"])

    def test_help_short(self):
        with patch("sys.argv", ["claudex", "-h"]):
            with patch("sys.stdout", new=io.StringIO()) as stdout:
                claudex.main()
        self.assertIn("Usage:", stdout.getvalue())

    def test_help_long(self):
        with patch("sys.argv", ["claudex", "--help"]):
            with patch("sys.stdout", new=io.StringIO()) as stdout:
                claudex.main()
        self.assertIn("Usage:", stdout.getvalue())

    def test_list(self):
        with patch("sys.argv", ["claudex", "--list"]):
            with patch("sys.stdout", new=io.StringIO()) as stdout:
                with patch("claudex.PROVIDERS_PATH", "/nonexistent/path.ini"):
                    claudex.main()
        self.assertIn("anthropic (default)", stdout.getvalue())

    def test_status(self):
        with patch("sys.argv", ["claudex", "status"]):
            with patch("sys.stdout", new=io.StringIO()) as stdout:
                with patch("claudex.SETTINGS_PATH", "/nonexistent/settings.json"):
                    with patch("claudex.CONFIG_DIR", "/nonexistent"):
                        with patch("claudex.PROVIDERS_PATH", "/nonexistent/providers.ini"):
                            claudex.main()
        self.assertIn("anthropic", stdout.getvalue().lower())

    def test_provider_switch_delegates(self):
        with patch("sys.argv", ["claudex", "deepseek", "-p", "hello"]):
            with patch("claudex.switch_and_launch") as mock_switch:
                claudex.main()
        mock_switch.assert_called_once_with("deepseek", ["-p", "hello"])


# ---------------------------------------------------------------------------
# TestInstallSh — smoke tests via subprocess
# ---------------------------------------------------------------------------

INSTALL_SH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "install.sh")


def _bash(code):
    """Run bash code sourcing install.sh first. Returns (stdout, stderr, returncode)."""
    full = f'set -euo pipefail; source "{INSTALL_SH}"; {code}'
    r = subprocess.run(["bash", "-c", full], capture_output=True, text=True, timeout=10)
    return r.stdout, r.stderr, r.returncode


class TestInstallSh(unittest.TestCase):
    def test_tilde_replaces_home(self):
        stdout, _, rc = _bash('_tilde "$HOME/.config"')
        self.assertEqual(rc, 0)
        self.assertIn("~/.config", stdout)

    def test_tilde_unchanged_outside_home(self):
        stdout, _, rc = _bash('_tilde "/opt/bin"')
        self.assertEqual(rc, 0)
        self.assertIn("/opt/bin", stdout)

    def test_tilde_home_only(self):
        stdout, _, rc = _bash('_tilde "$HOME"')
        self.assertEqual(rc, 0)
        self.assertIn("~", stdout)

    def test_copy_if_missing_dest_does_not_exist(self):
        _, _, rc = _bash(
            'd=$(mktemp -d); echo hello > "$d/src"; '
            'copy_if_missing "$d/dest" "$d/src" && test -f "$d/dest"'
        )
        self.assertEqual(rc, 0)

    def test_copy_if_missing_dest_exists(self):
        _, _, rc = _bash(
            'd=$(mktemp -d); echo old > "$d/dest"; echo new > "$d/src"; '
            'rc=0; copy_if_missing "$d/dest" "$d/src" || rc=$?; '
            'test "$rc" = "1" && test "$(cat "$d/dest")" = "old"'
        )
        self.assertEqual(rc, 0)

    def test_copy_if_missing_src_missing(self):
        _, _, rc = _bash(
            'd=$(mktemp -d); '
            'rc=0; copy_if_missing "$d/dest" "$d/nope" || rc=$?; '
            'test "$rc" = 1'
        )
        self.assertEqual(rc, 0)

    def test_update_symlinks(self):
        stdout, _, rc = _bash(
            'd=$(mktemp -d); '
            'mkdir -p "$d/.local/bin"; '
            'echo "fake" > "$d/src.py"; '
            'SCRIPT_DIR="$d" LOCAL_BIN="$d/.local/bin" CLAUDEX_SRC="$d/src.py" update; '
            'test -L "$d/.local/bin/claudex"'
        )
        self.assertEqual(rc, 0)

    @unittest.skipUnless(os.path.exists(INSTALL_SH), "install.sh not found")
    def test_install_sh_exists(self):
        self.assertTrue(os.path.exists(INSTALL_SH))

    # -- piped mode: _is_piped --

    def test_is_piped_true_when_src_missing(self):
        stdout, _, rc = _bash(
            'd=$(mktemp -d); '
            'CLAUDEX_SRC="$d/nope.py"; '
            '_is_piped && echo "PIPED" || true'
        )
        self.assertEqual(rc, 0)
        self.assertIn("PIPED", stdout)

    def test_is_piped_false_when_src_exists(self):
        _, _, rc = _bash(
            'd=$(mktemp -d); touch "$d/src.py"; '
            'CLAUDEX_SRC="$d/src.py"; '
            '_is_piped || exit 1'
        )
        self.assertEqual(rc, 1)

    # -- piped mode: _download --

    def test_download_fetches_file(self):
        _, _, rc = _bash(
            'd=$(mktemp -d); '
            'echo "hello" > "$d/remote.txt"; '
            'REPO_BASE="file://$d"; '
            '_download "remote.txt" "$d/local.txt"; '
            'test -f "$d/local.txt" && test "$(cat "$d/local.txt")" = "hello"'
        )
        self.assertEqual(rc, 0)

    # -- piped mode: install / update flows --

    def test_install_piped_mode_creates_symlink(self):
        stdout, _, rc = _bash(
            'd=$(mktemp -d); '
            'mkdir -p "$d/.local/bin" "$d/.config/claudex"; '
            'echo "x" > "$d/prov.example"; '
            'echo "x" > "$d/cred.example"; '
            'SCRIPT_DIR="$d"; CONFIG_DIR="$d/.config/claudex"; LOCAL_BIN="$d/.local/bin"; '
            'CLAUDEX_SRC="$d/nope.py"; '  # nonexistent → triggers piped mode
            'PROVIDERS_EXAMPLE="$d/prov.example"; CREDENTIALS_EXAMPLE="$d/cred.example"; '
            '_download() { touch "$2"; }; '
            'install; '
            'test -L "$d/.local/bin/claudex"'
        )
        self.assertEqual(rc, 0)

    def test_update_piped_mode_redownloads(self):
        stdout, _, rc = _bash(
            'd=$(mktemp -d); '
            'mkdir -p "$d/.local/bin" "$d/.config/claudex"; '
            'echo "old" > "$d/.config/claudex/claudex.py"; '
            'SCRIPT_DIR="$d"; CONFIG_DIR="$d/.config/claudex"; LOCAL_BIN="$d/.local/bin"; '
            'CLAUDEX_SRC="$d/nope.py"; '  # nonexistent → triggers piped mode
            '_download() { echo "new" > "$2"; }; '
            'update; '
            'test "$(cat "$d/.config/claudex/claudex.py")" = "new" && '
            'test -L "$d/.local/bin/claudex"'
        )
        self.assertEqual(rc, 0)
