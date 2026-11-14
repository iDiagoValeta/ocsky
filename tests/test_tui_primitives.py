"""Tests for the TUI building blocks: text, canvas, theme, translations and formatters."""
from __future__ import annotations

from tests import helpers  # noqa: F401  (puts src/ on sys.path before the ocsky imports)

# isort: split

import hashlib
import re
import string
import unittest

from ocsky.adapters.driving.tui.canvas import RGB, Braille, Canvas, mix, xterm256
from ocsky.adapters.driving.tui.fmt import fmt_age, fmt_cost, fmt_tokens
from ocsky.adapters.driving.tui.i18n import LANGS, STRINGS, Tr
from ocsky.adapters.driving.tui.text import char_width, clean, fit, short_dir, text_width, wrap
from ocsky.adapters.driving.tui.palettes import LATTE, MOCHA, PALETTES
from ocsky.adapters.driving.tui.theme import ACCENTS, NEUTRALS, Theme, default_colors

RED: RGB = (255, 0, 0)
WHITE: RGB = (255, 255, 255)
BLACK: RGB = (0, 0, 0)


class TextTest(unittest.TestCase):
    def test_char_width_counts_wide_and_combining_characters(self):
        self.assertEqual(char_width("a"), 1)
        self.assertEqual(char_width("漢"), 2)
        self.assertEqual(char_width("́"), 0)

    def test_text_width_uses_cells_not_characters(self):
        self.assertEqual(text_width("漢字"), 4)
        self.assertEqual(text_width("ab"), 2)
        self.assertEqual(text_width("é"), 1)

    def test_clean_drops_control_characters_and_collapses_whitespace(self):
        self.assertEqual(clean("a\tb\n c\x00\x1b"), "a b c")
        self.assertEqual(clean(""), "")
        self.assertEqual(clean(None), "")

    def test_fit_keeps_short_text_and_ends_long_text_with_an_ellipsis(self):
        self.assertEqual(fit("abc", 3), "abc")
        self.assertEqual(fit("hello world", 6), "hello…")
        self.assertEqual(fit("abc", 0), "")

    def test_fit_never_splits_a_wide_character(self):
        cut = fit("漢字漢字", 5)
        self.assertEqual(cut, "漢字…")
        self.assertLessEqual(text_width(cut), 5)

    def test_wrap_breaks_on_words_within_width(self):
        self.assertEqual(wrap("one two three", 7), ["one two", "three"])
        self.assertEqual(wrap("", 5), [])

    def test_wrap_keeps_every_line_within_width_with_wide_characters(self):
        lines = wrap("漢字 混合 text and 漢字漢字漢字 more words here", 6)
        self.assertTrue(lines)
        for line in lines:
            self.assertLessEqual(text_width(line), 6)

    def test_short_dir_shows_a_backslash_path_whole_or_cut_without_crashing(self):
        d = "C:\\Users\\x\\proj"
        self.assertEqual(short_dir(d, 40, ""), d)
        self.assertEqual(text_width(short_dir(d, 8, "")), 8)
        self.assertEqual(text_width(short_dir(d, 8, "", 3)), 8)

    def test_short_dir_replaces_home_and_keeps_fitting_paths(self):
        self.assertEqual(short_dir("/home/u/dev/proj/src", 40, "/home/u"), "~/dev/proj/src")

    def test_short_dir_shortens_the_middle_to_fit(self):
        self.assertEqual(short_dir("/home/u/dev/proj/src", 12, "/home/u"), "~/…/proj/src")
        self.assertLessEqual(text_width(short_dir("/home/u/dev/proj/src", 12, "/home/u")), 12)

    def test_short_dir_with_max_parts_keeps_the_last_three_of_a_long_path(self):
        self.assertEqual(short_dir("/a/b/c/d/e", 80, "/home/u", 3), "…/c/d/e")
        self.assertEqual(short_dir("/home/u/a/b/c/d", 80, "/home/u", 3), "~/…/b/c/d")

    def test_short_dir_with_max_parts_shows_four_components_or_fewer_whole(self):
        self.assertEqual(short_dir("/a/b/c/d", 80, "/home/u", 3), "/a/b/c/d")
        self.assertEqual(short_dir("/home/u/a/b/c", 80, "/home/u", 3), "~/a/b/c")

    def test_short_dir_with_max_parts_still_obeys_the_width(self):
        out = short_dir("/a/b/c/dddddddd/eeeeeeee", 14, "/home/u", 3)
        self.assertLessEqual(text_width(out), 14)
        self.assertTrue(out.endswith("eeeeeeee"))

    def test_short_dir_leaves_paths_outside_home_alone(self):
        self.assertEqual(short_dir("/opt/x", 20, "/home/u"), "/opt/x")
        self.assertEqual(short_dir("/opt/x", 20, ""), "/opt/x")


class CanvasTest(unittest.TestCase):
    def test_xterm256_maps_known_colours(self):
        self.assertEqual(xterm256(BLACK), 16)
        self.assertEqual(xterm256(WHITE), 231)
        self.assertEqual(xterm256((128, 128, 128)), 244)
        self.assertEqual(xterm256(RED), 196)

    def test_mix_blends_and_clamps_the_factor(self):
        self.assertEqual(mix(BLACK, WHITE, 0.25), (64, 64, 64))
        self.assertEqual(mix(BLACK, WHITE, -1), BLACK)
        self.assertEqual(mix(BLACK, WHITE, 2), WHITE)

    def test_put_clips_at_the_right_edge(self):
        cv = Canvas(5, 2, BLACK, WHITE)
        end = cv.put(3, 0, "abcdef", RED)
        self.assertEqual(end, 5)
        self.assertEqual(cv.ch[0], [" ", " ", " ", "a", "b"])
        self.assertTrue(cv.used[0][3])
        self.assertFalse(cv.used[0][2])

    def test_put_clips_at_the_left_edge_and_ignores_rows_out_of_range(self):
        cv = Canvas(3, 1, BLACK, WHITE)
        cv.put(-2, 0, "abcd", RED)
        self.assertEqual(cv.ch[0], ["c", "d", " "])
        self.assertEqual(cv.put(0, 5, "zzz", RED), 0)
        self.assertEqual(cv.ch[0], ["c", "d", " "])

    def test_put_respects_maxw_and_never_splits_wide_characters(self):
        cv = Canvas(10, 1, BLACK, WHITE)
        self.assertEqual(cv.put(0, 0, "abcdef", RED, maxw=3), 3)
        self.assertEqual(cv.ch[0][:4], ["a", "b", "c", " "])
        narrow = Canvas(3, 1, BLACK, WHITE)
        self.assertEqual(narrow.put(0, 0, "漢字", RED), 2)
        self.assertEqual(narrow.ch[0], ["漢", "", " "])

    def test_fill_sets_background_inside_the_canvas_only(self):
        cv = Canvas(3, 2, BLACK, WHITE)
        cv.fill(1, 0, 10, 1, RED)
        self.assertEqual(cv.bg[0], [BLACK, RED, RED])
        self.assertEqual(cv.bg[1], [BLACK, BLACK, BLACK])

    def test_render_uses_24_bit_sequences(self):
        cv = Canvas(2, 1, BLACK, WHITE)
        cv.put(0, 0, "a", (1, 2, 3))
        out = cv.render("truecolor")
        self.assertTrue(out.startswith("\x1b[1;1H"))
        self.assertIn("38;2;1;2;3;48;2;0;0;0m", out)
        self.assertNotIn("38;5;", out)
        self.assertTrue(out.endswith("\x1b[0m"))

    def test_render_uses_256_colour_sequences(self):
        cv = Canvas(2, 1, BLACK, WHITE)
        cv.put(0, 0, "a", (1, 2, 3))
        out = cv.render("256")
        self.assertIn(f"38;5;{xterm256((1, 2, 3))};48;5;16m", out)
        self.assertNotIn("38;2;", out)

    def test_render_marks_bold_in_both_colour_modes(self):
        cv = Canvas(1, 1, BLACK, WHITE)
        cv.put(0, 0, "a", RED, bold=True)
        self.assertIn("\x1b[0;1;38;2;255;0;0;", cv.render("truecolor"))
        self.assertIn("\x1b[0;1;38;5;", cv.render("256"))

    def test_render_sends_only_the_colour_that_changes(self):
        cv = Canvas(4, 1, BLACK, WHITE)
        cv.put(0, 0, "a", RED)
        cv.put(1, 0, "b", WHITE)  # new ink, same paper: only the ink is sent
        cv.put(2, 0, " ", RED)  # a blank shows no ink: nothing is sent
        cv.fill(3, 0, 1, 1, RED)  # new paper: only the paper is sent
        out = cv.render("truecolor")
        self.assertEqual(re.findall(r"\x1b\[[0-9;]*m", out)[:3],
                         ["\x1b[0;38;2;255;0;0;48;2;0;0;0m", "\x1b[38;2;255;255;255m", "\x1b[48;2;255;0;0m"])
        self.assertTrue(out.endswith("\x1b[0m"))

    def test_render_starts_over_when_bold_changes(self):
        cv = Canvas(2, 1, BLACK, WHITE)
        cv.put(0, 0, "a", RED, bold=True)
        cv.put(1, 0, "b", RED)
        self.assertIn("a\x1b[0;38;2;255;0;0;48;2;0;0;0mb", cv.render("truecolor"))


class BrailleTest(unittest.TestCase):
    def test_dot_sets_the_right_bit_in_its_cell(self):
        br = Braille(2, 1)
        br.dot(0, 0, RED)
        self.assertEqual(br.bits[(0, 0)], 0x01)
        br.dot(1, 0, RED)
        self.assertEqual(br.bits[(0, 0)], 0x09)
        br.dot(0, 3, RED)
        self.assertEqual(br.bits[(0, 0)], 0x49)
        self.assertEqual(br.bits[(0, 0)], 0x49)
        # Dot (2, 4) falls in the second row of cells, so a 2x2 canvas lights cell (1, 1).
        grid = Braille(2, 2)
        grid.dot(2, 4, RED)
        self.assertEqual(grid.bits, {(1, 1): 0x01})

    def test_dot_drops_points_outside_the_canvas(self):
        br = Braille(2, 1)
        br.dot(-1, 0, RED)
        br.dot(0, -1, RED)
        br.dot(100, 0, RED)
        br.dot(0, 100, RED)
        self.assertEqual(br.bits, {})

    def test_blit_paints_braille_characters_at_an_offset(self):
        cv = Canvas(4, 2, BLACK, WHITE)
        br = Braille(2, 1)
        br.dot(0, 0, RED)
        br.blit(cv, 1, 1)
        self.assertEqual(cv.ch[1][1], chr(0x2801))
        self.assertEqual(cv.fg[1][1], RED)


class ThemeTest(unittest.TestCase):
    def test_default_colors_honours_truecolor(self):
        self.assertEqual(default_colors({"COLORTERM": "truecolor"}), "truecolor")
        self.assertEqual(default_colors({"COLORTERM": "24bit"}), "truecolor")
        self.assertEqual(default_colors({"COLORTERM": "TRUECOLOR"}), "truecolor")

    def test_default_colors_uses_256_in_apple_terminal_without_truecolor(self):
        self.assertEqual(default_colors({"TERM_PROGRAM": "Apple_Terminal"}), "256")
        self.assertEqual(default_colors({"TERM_PROGRAM": "Apple_Terminal", "COLORTERM": "24bit"}),
                         "truecolor")

    def test_default_colors_is_truecolor_for_an_empty_environment(self):
        self.assertEqual(default_colors({}), "truecolor")

    def test_palettes_become_rgb_tuples(self):
        th = Theme(MOCHA)
        self.assertEqual(th.base, (0x1e, 0x1e, 0x2e))
        self.assertEqual(len(th.accents), len(ACCENTS))
        self.assertEqual(Theme(LATTE).red, (0xd2, 0x0f, 0x39))

    def test_every_palette_has_every_colour_and_a_pair_on_the_other_side(self):
        names = NEUTRALS + ACCENTS + ["mantle", "crust", "red", "rosewater"]
        for key, p in PALETTES.items():
            th = Theme(p.colors)
            for name in names:
                self.assertEqual(len(getattr(th, name)), 3, (key, name))
            self.assertIn(p.pair, PALETTES, key)
            self.assertNotEqual(Theme(PALETTES[p.pair].colors).light, th.light, key)

    def test_a_missing_neutral_is_blended_from_its_neighbours(self):
        th = Theme(PALETTES["nord"].colors)  # Nord publishes nothing between nord3 and nord4
        self.assertEqual(th.surface2, (0x4c, 0x56, 0x6a))
        self.assertEqual(th.text, (0xd8, 0xde, 0xe9))
        self.assertTrue(th.surface2 < th.overlay0 < th.overlay1 < th.subtext0 < th.text)

    def test_model_color_is_stable_across_calls_and_instances(self):
        first = Theme(MOCHA).model_color("provider/model-a", set())
        self.assertEqual(Theme(MOCHA).model_color("provider/model-a", set()), first)
        self.assertEqual(Theme(MOCHA).model_color("provider/model-a", set()), first)
        self.assertIn(first, Theme(MOCHA).accents)

    def test_model_color_avoids_taken_colours(self):
        th = Theme(MOCHA)
        first = th.model_color("provider/model-a", set())
        second = th.model_color("provider/model-a", {first})
        self.assertNotEqual(second, first)
        self.assertIn(second, th.accents)

    def test_model_color_keeps_the_last_accent_when_all_are_taken(self):
        th = Theme(MOCHA)
        slot = int(hashlib.md5(b"m").hexdigest(), 16) % len(th.accents)
        last = th.accents[(slot + len(th.accents) - 1) % len(th.accents)]
        self.assertEqual(th.model_color("m", set(th.accents)), last)


class TranslationTest(unittest.TestCase):
    def test_en_and_es_have_exactly_the_same_keys(self):
        self.assertEqual(set(STRINGS["en"]), set(STRINGS["es"]))

    def test_each_key_has_the_same_placeholders_in_both_languages(self):
        def fields(text):
            return {name for _, name, _, _ in string.Formatter().parse(text) if name is not None}

        for key in STRINGS["en"]:
            self.assertEqual(fields(STRINGS["en"][key]), fields(STRINGS["es"][key]), key)

    def test_every_value_is_a_non_empty_string(self):
        for lang in LANGS:
            for key, value in STRINGS[lang].items():
                self.assertIsInstance(value, str, key)
                self.assertTrue(value.strip(), key)

    def test_spanish_has_no_voseo(self):
        forms = ["hacé", "pulsá", "tenés", "podés", "querés", "sabés", "vos"]
        for key, value in STRINGS["es"].items():
            lowered = value.lower()
            for form in forms:
                self.assertNotRegex(lowered, rf"\b{re.escape(form)}\b", key)

    def test_languages_are_en_then_es(self):
        self.assertEqual(LANGS, ("en", "es"))

    def test_tr_translates_and_fills_placeholders(self):
        self.assertEqual(Tr()("tagline"), "live view of opencode agents")
        self.assertEqual(Tr("es")("count.working", n=2), "2 trabajando")
        self.assertEqual(Tr("en")("act.finished", outcome="done"), "finished (done)")

    def test_tr_returns_the_key_for_a_missing_key(self):
        self.assertEqual(Tr()("no.such.key"), "no.such.key")

    def test_tr_falls_back_to_english_for_an_unknown_language(self):
        self.assertEqual(Tr("fr").lang, "en")
        self.assertEqual(Tr("fr")("header.quiet"), "all quiet")

    def test_tr_next_cycles_through_the_languages(self):
        en = Tr("en")
        es = en.next()
        self.assertIsInstance(es, Tr)
        self.assertEqual(es.lang, "es")
        self.assertEqual(es.next().lang, "en")
        self.assertEqual(en.lang, "en")

    def test_tr_has_the_keys_the_interface_needs(self):
        required = ["tagline", "count.working", "count.waiting", "header.quiet", "state.working",
                    "group.here", "row.folded", "act.thinking", "focus.stats", "empty.active",
                    "clock.title", "trace.empty", "key.help", "help.title", "toast.lang",
                    "error.small", "cli.description", "range.7d"]
        for key in required:
            self.assertIn(key, STRINGS["en"])
            self.assertIn(key, STRINGS["es"])


class FormatTest(unittest.TestCase):
    def test_fmt_tokens_in_english(self):
        self.assertEqual(fmt_tokens(999, "en"), "999")
        self.assertEqual(fmt_tokens(412_000, "en"), "412k")
        self.assertEqual(fmt_tokens(1_200_000, "en"), "1.2M")

    def test_fmt_tokens_in_spanish(self):
        self.assertEqual(fmt_tokens(999, "es"), "999")
        self.assertEqual(fmt_tokens(412_000, "es"), "412 k")
        self.assertEqual(fmt_tokens(1_200_000, "es"), "1,2 M")

    def test_fmt_cost_in_english(self):
        self.assertEqual(fmt_cost(0.31, "en"), "$0.31")
        self.assertEqual(fmt_cost(0, "en"), "free")
        self.assertEqual(fmt_cost(0.001, "en"), "<$0.01")

    def test_fmt_cost_in_spanish(self):
        self.assertEqual(fmt_cost(0.31, "es"), "0,31 $")
        self.assertEqual(fmt_cost(0, "es"), "gratis")
        self.assertEqual(fmt_cost(0.001, "es"), "<0,01 $")

    def test_fmt_age_in_english(self):
        self.assertEqual(fmt_age(5_000, "en"), "5s")
        self.assertEqual(fmt_age(12 * 60_000, "en"), "12m")
        self.assertEqual(fmt_age((3 * 3600 + 5 * 60) * 1000, "en"), "3h 05m")
        self.assertEqual(fmt_age(2 * 86_400_000, "en"), "2d")

    def test_fmt_age_in_spanish(self):
        self.assertEqual(fmt_age(5_000, "es"), "5 s")
        self.assertEqual(fmt_age(12 * 60_000, "es"), "12 min")
        self.assertEqual(fmt_age((3 * 3600 + 5 * 60) * 1000, "es"), "3 h 05")
        self.assertEqual(fmt_age(2 * 86_400_000, "es"), "2 d")

    def test_fmt_age_never_goes_negative(self):
        self.assertEqual(fmt_age(-5_000, "en"), "0s")


if __name__ == "__main__":
    unittest.main()
