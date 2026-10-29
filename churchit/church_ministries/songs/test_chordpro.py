# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import itertools
import time

from frappe.tests.utils import FrappeTestCase

from churchit.church_ministries.songs import chordpro

CHART = """{title: Amazing Grace}
{key: G}
# arranged for the morning service
{comment: Verse 1}
[G]Amazing [G7]grace, how [C]sweet the [G]sound
That [G]saved a [Em]wretch like [D/F#]me

{start_of_chorus}
[C]My chains are [Dsus4]gone, [Bm7]I've been set [N.C.]free
{end_of_chorus}

Bridge
[Am7]The earth shall [Bb]soon dissolve like [D]snow

{start_of_tab}
e|--3--2--0--|
{end_of_tab}
"""
MAJOR_KEYS = ("C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B")
MINOR_KEYS = ("Cm", "C#m", "Dm", "Ebm", "Em", "Fm", "F#m", "Gm", "G#m", "Am", "Bbm", "Bm")
CHROMATIC_CHARTS = (
	("[G]Then sings my [B/D#]soul [Eb]a [C/E]b [E/G#]c [A/C#]d [F]e [Bb]f", "G", MAJOR_KEYS),
	("[D]How great [Bb]thou art [F#/A#]x [C]y", "D", MAJOR_KEYS),
	("[C]Holy [E/G#]holy [Ab/C]x [C#dim]y [F#m7b5]z", "C", MAJOR_KEYS),
	("[Bb]x [D/F#]y [Gb]z", "Bb", MAJOR_KEYS),
	("[Am]x [E/G#]y [Bb]z [Dm/F]w [E7]v", "Am", MINOR_KEYS),
)


def step_up_twelve_times(text, key, keys):
	for _ in range(12):
		next_key = keys[(keys.index(key) + 1) % 12]
		text, key = chordpro.transpose(text, key, next_key), next_key
	return text


class TestTranspose(FrappeTestCase):
	def test_a_chord_and_its_bass_move_to_the_new_key(self):
		self.assertEqual(chordpro.transpose("[G]Amazing [D/F#]grace", "G", "A"), "[A]Amazing [E/G#]grace")

	def test_a_flat_key_gets_flats_and_a_sharp_key_gets_sharps(self):
		self.assertEqual(chordpro.transpose("[D/F#] [Bm]", "G", "F"), "[C/E] [Am]")
		self.assertEqual(chordpro.transpose("[C] [F] [G]", "C", "Eb"), "[Eb] [Ab] [Bb]")
		self.assertEqual(chordpro.transpose("[C] [F] [G]", "C", "E"), "[E] [A] [B]")
		self.assertEqual(chordpro.transpose("[E/G#] [Bb]", "C", "F"), "[A/C#] [Eb]")

	def test_a_minor_key_moves_by_its_root(self):
		self.assertEqual(chordpro.transpose("[Em] [C] [D] [B7]", "Em", "Am"), "[Am] [F] [G] [E7]")
		self.assertEqual(chordpro.transpose("[Am] [E7]", "Am", "C#m"), "[C#m] [G#7]")

	def test_twelve_semitones_up_return_the_original_text(self):
		self.assertEqual(step_up_twelve_times(CHART, "G", MAJOR_KEYS), CHART)
		for text, key, keys in CHROMATIC_CHARTS:
			with self.subTest(text):
				self.assertEqual(step_up_twelve_times(text, key, keys), text)

	def test_a_chord_never_needs_a_double_sharp_or_flat_or_mixes_them(self):
		self.assertEqual(chordpro.transpose("[C]Holy [E/G#]holy", "C", "F#"), "[F#]Holy [Bb/D]holy")
		self.assertEqual(chordpro.transpose("[G]x [B/D#]y", "G", "B"), "[B]x [Eb/G]y")
		self.assertEqual(chordpro.transpose("[Am]x [E/G#]y", "Am", "G#m"), "[G#m]x [Eb/G]y")
		self.assertEqual(chordpro.transpose("[D]x [Bb]y", "D", "Db"), "[Db]x [A]y")
		notes = [letter + accidental for letter in "CDEFGAB" for accidental in ("", "#", "b")]
		chords = " ".join(f"[{root}/{bass}]" for root in notes for bass in notes)
		for keys in (MAJOR_KEYS, MINOR_KEYS):
			for from_key, to_key in itertools.product(keys, keys):
				for chord in chordpro.BRACKETS.findall(chordpro.transpose(chords, from_key, to_key)):
					root, bass = chord.split("/")
					self.assertNotRegex(chord, r"##|.bb")
					self.assertFalse("#" in root + bass and "b" in root[1:] + bass[1:], chord)

	def test_the_key_directive_moves_and_other_brackets_stay(self):
		text = chordpro.transpose(CHART, "G", "A")

		self.assertIn("{key: A}\n", text)
		self.assertIn("[N.C.]free", text)
		self.assertIn("# arranged for the morning service", text)
		self.assertIn("e|--3--2--0--|", text)
		self.assertEqual(
			chordpro.transpose("[Chorus]x [Bridge] [Ending] [Amaj7/C#] [C6/9]", "G", "A"),
			"[Chorus]x [Bridge] [Ending] [Bmaj7/D#] [D6/9]",
		)

	def test_a_long_line_with_an_open_brace_or_bracket_reads_at_once(self):
		started = time.monotonic()
		for line in ("{a: " + " " * 100_000, "{key: " + " " * 100_000 + "x", "[" * 100_000):
			chordpro.to_html(line)
			chordpro.transpose(line, "G", "A")

		self.assertLess(time.monotonic() - started, 1)

	def test_a_word_that_is_no_key_is_refused(self):
		with self.assertRaises(ValueError):
			chordpro.transpose(CHART, "G", "H")

	def test_a_key_in_the_other_mode_is_refused(self):
		for from_key, to_key in (("G", "Em"), ("Em", "G")):
			with self.assertRaises(ValueError):
				chordpro.transpose(f"{{key: {from_key}}}\n[{from_key}]x", from_key, to_key)


class TestReadingCharts(FrappeTestCase):
	def test_parse_reads_the_directives_and_sections(self):
		chart = chordpro.parse(CHART)

		self.assertEqual(chart.get("title"), "Amazing Grace")
		self.assertEqual(chart.get("key"), "G")
		self.assertEqual(
			[(section.kind, section.label) for section in chart.sections],
			[("verse", "Verse 1"), ("chorus", "Chorus"), ("bridge", "Bridge"), ("tab", "Tab")],
		)
		self.assertEqual(chart.sections[0].lines[1].pairs[-1], ("D/F#", "me"))

	def test_meta_directives_keep_every_value(self):
		chart = chordpro.parse("{meta: author John Newton}\n{meta: author Edwin Excell}\n")

		self.assertEqual(chart.meta["author"], ["John Newton", "Edwin Excell"])

	def test_lyrics_are_the_sections_without_chords(self):
		self.assertEqual(
			chordpro.lyrics(CHART),
			[
				{
					"kind": "verse",
					"label": "Verse 1",
					"lines": ["Amazing grace, how sweet the sound", "That saved a wretch like me"],
				},
				{"kind": "chorus", "label": "Chorus", "lines": ["My chains are gone, I've been set free"]},
				{"kind": "bridge", "label": "Bridge", "lines": ["The earth shall soon dissolve like snow"]},
			],
		)

	def test_unlabelled_paragraphs_are_other_sections(self):
		sections = chordpro.lyrics("[G]One line\n\n\n[C]Two [D]li[G]nes\n{chorus}\n")

		self.assertEqual(
			[(section["kind"], section["lines"]) for section in sections],
			[("other", ["One line"]), ("other", ["Two lines"])],
		)

	def test_a_directive_value_loses_its_spaces(self):
		chart = chordpro.parse("{title:  Amazing Grace  }\n{key:G}\n")

		self.assertEqual((chart.get("title"), chart.get("key")), ("Amazing Grace", "G"))

	def test_a_refrain_label_is_a_chorus(self):
		self.assertEqual(chordpro.lyrics("Refrain:\nLift high the cross")[0]["kind"], "chorus")


class TestChordChartHtml(FrappeTestCase):
	def test_every_lyric_chord_label_and_comment_is_escaped(self):
		html = chordpro.to_html(
			"{comment: <i>soft</i>}\n{start_of_verse: <b>One</b>}\n[<script>]Hold <img src=x> fast\n"
			"{end_of_verse}\n{start_of_tab}\n<tab>\n{end_of_tab}\n"
		)

		for raw in ("<script>", "<img", "<b>", "<i>", "<tab>"):
			self.assertNotIn(raw, html)
		self.assertIn("&lt;script&gt;", html)
		self.assertIn("Hold &lt;img src=x&gt; fast", html)

	def test_a_comment_in_a_tab_block_is_part_of_the_tab(self):
		html = chordpro.to_html("{start_of_tab}\ne|--0--|\n{comment: slow}\n{end_of_tab}")

		self.assertIn("<pre>e|--0--|\nslow</pre>", html)

	def test_each_chord_sits_over_its_words(self):
		html = chordpro.to_html("[G]Amazing [D/F#]grace")

		self.assertIn('<span class="chord-chart-chord">D/F#</span><span>grace</span>', html)
