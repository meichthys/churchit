# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""ChordPro charts: read, transpose, render as HTML and take the lyrics out.

A chart is plain text with chords in brackets (`[G]Amazing [D/F#]grace`), directives in braces
(`{title: ...}`, `{start_of_chorus}`, `{comment: Verse 1}`) and comment lines that start with `#`.
A section is a `{start_of_...}` block, or a paragraph of lines that ends at a blank line and may
start with a label such as `{comment: Verse 1}` or a line `Chorus`. Standard library only.
"""

import re
from dataclasses import dataclass, field
from html import escape

LETTERS = "CDEFGAB"
NATURAL_PITCHES = (0, 2, 4, 5, 7, 9, 11)
ACCIDENTALS = {"": 0, "#": 1, "b": -1}
MAJOR_SCALE = NATURAL_PITCHES
MINOR_SCALE = (0, 2, 3, 5, 7, 8, 10)
# Between two steps of a scale, the degree a chromatic note usually is, as (step, alteration):
# in a major key #1, b3, #4, b6 and b7, in a minor key b2, #3, #4, #6 and #7.
COMMON_DEGREES = {
	MAJOR_SCALE: {(0, 1), (2, -1), (3, 1), (5, -1), (6, -1)},
	MINOR_SCALE: {(1, -1), (2, 1), (3, 1), (5, 1), (6, 1)},
}
# Letter steps from a root up to its bass, by semitones: C/Db, C/D, C/Eb, C/E ... C/Bb, C/B.
BASS_STEPS = (0, 1, 1, 2, 2, 3, 3, 4, 5, 5, 6, 6)
KINDS = ("verse", "chorus", "bridge", "other")
TAB = "tab"

KEY = re.compile(r"([A-G][#b]?)m?")
CHORD = re.compile(
	r"([A-G][#b]?)((?:6/9|maj|min|ma|mi|m|M|sus|add|dim|aug|alt|[0-9+#b()°ø^Δ-])*)(?:/([A-G][#b]?))?"
)
BRACKETS = re.compile(r"\[([^\[\]]*)\]")
# Linear on purpose: overlapping whitespace quantifiers backtrack in cubic time on an open brace.
DIRECTIVE = re.compile(r"\{\s*([\w-]+)\s*(?::(.*))?\}")
KEY_DIRECTIVE = re.compile(r"(\s*\{\s*key\s*:)([^}]*)(\}\s*)", re.IGNORECASE)
LABEL = re.compile(
	r"(verse|chorus|refrain|pre-?chorus|bridge|tag|intro|outro|ending|interlude|instrumental|coda)"
	r"(\s+\d+)?\s*:?",
	re.IGNORECASE,
)
ALIASES = {
	"t": "title",
	"st": "subtitle",
	"c": "comment",
	"ci": "comment_italic",
	"cb": "comment_box",
	"sov": "start_of_verse",
	"eov": "end_of_verse",
	"soc": "start_of_chorus",
	"eoc": "end_of_chorus",
	"sob": "start_of_bridge",
	"eob": "end_of_bridge",
	"sot": "start_of_tab",
	"eot": "end_of_tab",
	"sog": "start_of_grid",
	"eog": "end_of_grid",
}
COMMENTS = ("comment", "comment_italic", "comment_box", "highlight")

STYLE = (
	"<style>"
	".chord-chart h4{margin:1rem 0 .25rem}"
	".chord-chart-line{display:flex;flex-wrap:wrap;align-items:flex-end;margin-bottom:.25rem}"
	".chord-chart-pair{display:inline-flex;flex-direction:column;white-space:pre}"
	".chord-chart-chord{font-weight:600;padding-right:.25em}"
	".chord-chart-comment{font-style:italic;margin:.25rem 0}"
	"</style>"
)


@dataclass
class Line:
	pairs: list[tuple[str, str]] = field(default_factory=list)
	"""Each chord with the text sung from it; the first chord may be blank."""
	comment: str = ""


@dataclass
class Section:
	kind: str
	"""One of KINDS, or TAB for a tab or grid block, which holds no lyrics."""
	label: str = ""
	lines: list[Line] = field(default_factory=list)


@dataclass
class Chart:
	meta: dict[str, list[str]] = field(default_factory=dict)
	"""Each directive's values, by name: `{title: ...}` and `{meta: author ...}` alike."""
	sections: list[Section] = field(default_factory=list)

	def get(self, name: str) -> str:
		"""The first value of the directive *name*, or an empty string."""
		return (self.meta.get(name) or [""])[0]


class ChartReader:
	"""Reads a chart one line at a time, keeping the section that is open."""

	def __init__(self):
		self.chart = Chart()
		self.section: Section | None = None
		self.is_inside_block = False

	def read(self, text: str) -> Chart:
		for line in text.splitlines():
			self.read_line(line.rstrip())
		return self.chart

	def read_line(self, line: str):
		stripped = line.strip()
		directive = DIRECTIVE.fullmatch(stripped)
		if stripped.startswith("#"):
			return
		if directive:
			return self.read_directive(directive.group(1).lower(), directive.group(2))
		if not stripped:
			if not self.is_inside_block and self.section and self.section.lines:
				self.section = None
			return
		if self.section and self.section.kind == TAB:
			return self.section.lines.append(Line(pairs=[("", line)]))
		if not self.is_inside_block and LABEL.fullmatch(stripped):
			return self.start(kind_of_label(stripped), stripped.rstrip(":"))
		self.get_section().lines.append(Line(pairs=split_chords(stripped)))

	def read_directive(self, name: str, value: str | None):
		name, value = ALIASES.get(name, name), value and value.strip()
		if name.startswith("start_of_"):
			block = name.removeprefix("start_of_")
			kind = TAB if block in ("tab", "grid") else block if block in KINDS else "other"
			self.start(kind, value or block.replace("_", " ").title())
			self.is_inside_block = True
		elif name.startswith("end_of_"):
			self.section, self.is_inside_block = None, False
		elif name in COMMENTS and value:
			self.read_comment(value)
		elif name == "meta" and value:
			meta_name, _, meta_value = value.partition(" ")
			self.chart.meta.setdefault(meta_name.lower(), []).append(meta_value.strip())
		elif value is not None:
			self.chart.meta.setdefault(name, []).append(value)

	def read_comment(self, comment: str):
		"""A label such as `Verse 1` starts a section; any other comment is a line of the chart."""
		if not self.is_inside_block and LABEL.fullmatch(comment):
			self.start(kind_of_label(comment), comment.rstrip(":"))
		else:
			self.get_section().lines.append(Line(comment=comment))

	def start(self, kind: str, label: str):
		self.section = Section(kind=kind, label=label)
		self.chart.sections.append(self.section)

	def get_section(self) -> Section:
		if not self.section:
			self.start("other", "")
		return self.section


def kind_of_label(label: str) -> str:
	word = label.lower()
	if word.startswith(("chorus", "refrain")):
		return "chorus"
	return next((kind for kind in ("verse", "bridge") if word.startswith(kind)), "other")


def split_chords(line: str) -> list[tuple[str, str]]:
	"""`[G]Amazing [D/F#]grace` as `[("G", "Amazing "), ("D/F#", "grace")]`."""
	parts = BRACKETS.split(line)
	pairs = [("", parts[0])] if parts[0] else []
	return pairs + list(zip(parts[1::2], parts[2::2], strict=True))


def parse(text: str) -> Chart:
	return ChartReader().read(text)


def signed(semitones: int) -> int:
	"""*semitones* as the nearest interval, from -6 to 5."""
	return (semitones + 6) % 12 - 6


@dataclass(frozen=True)
class Note:
	letter: int
	"""Index in LETTERS."""
	pitch: int

	@classmethod
	def read(cls, text: str) -> "Note":
		letter = LETTERS.index(text[0])
		return cls(letter, (NATURAL_PITCHES[letter] + ACCIDENTALS[text[1:]]) % 12)

	@property
	def accidental(self) -> int:
		return signed(self.pitch - NATURAL_PITCHES[self.letter])

	@property
	def is_double(self) -> bool:
		return abs(self.accidental) > 1

	def __str__(self) -> str:
		return LETTERS[self.letter] + {0: "", 1: "#", -1: "b"}[self.accidental]

	def get_bass(self, semitones: int) -> "Note":
		"""The note *semitones* above, spelled from this root: E and 4 give G#, Eb and 4 give G."""
		return Note((self.letter + BASS_STEPS[semitones % 12]) % 7, (self.pitch + semitones) % 12)

	def get_enharmonic(self) -> "Note":
		"""The same pitch on the next letter towards the accidental: D# as Eb, F## as G."""
		return Note((self.letter + (self.accidental > 0) - (self.accidental < 0)) % 7, self.pitch)


@dataclass(frozen=True)
class Key:
	root: Note
	scale: tuple[int, ...]

	def get_note(self, step: int, alteration: int = 0) -> Note:
		"""The note on *step* of the scale, raised or lowered by *alteration*. It may be double."""
		pitch = self.root.pitch + self.scale[step] + alteration
		return Note((self.root.letter + step) % 7, pitch % 12)

	def get_degree(self, note: Note) -> tuple[int, int]:
		"""The step and alteration of *note*: in G, D# is (4, 1) and Eb is (5, -1).

		A note of the scale reads as its step, so Eb in B is D#. A note that this key could also
		write only with a double sharp or flat reads as the more common of the two degrees.
		"""
		step = (note.letter - self.root.letter) % 7
		alteration = signed(note.pitch - self.get_note(step).pitch)
		if not alteration:
			return step, 0

		other = (step + (1 if alteration > 0 else -1)) % 7
		other_alteration = signed(note.pitch - self.get_note(other).pitch)
		if not other_alteration or (
			self.get_note(other, other_alteration).is_double
			and (other, other_alteration) in COMMON_DEGREES[self.scale]
		):
			return other, other_alteration
		return step, alteration


def read_key(name: str) -> Key:
	"""The key `G`, `Em` or `F#m`. Raises ValueError for any other text."""
	match = KEY.fullmatch(name or "")
	if not match:
		raise ValueError(f"{name!r} is not a key")
	return Key(Note.read(match.group(1)), MINOR_SCALE if name.endswith("m") else MAJOR_SCALE)


def move_chord(chord: str, source: Key, target: Key) -> str:
	"""*chord* moved from *source* to *target*; text that is no chord, such as `N.C.`, stays."""
	match = CHORD.fullmatch(chord)
	if not match:
		return chord

	root, quality, bass = match.groups()
	interval = Note.read(bass).pitch - Note.read(root).pitch if bass else 0
	new_root = target.get_note(*source.get_degree(Note.read(root)))
	new_root = next(
		note
		for note in (new_root, new_root.get_enharmonic(), new_root.get_enharmonic().get_enharmonic())
		if not note.is_double and not note.get_bass(interval).is_double
	)
	return f"{new_root}{quality}" + (f"/{new_root.get_bass(interval)}" if bass else "")


def transpose(text: str, from_key: str, to_key: str) -> str:
	"""The chart with every chord and its `{key}` moved from *from_key* to *to_key*.

	Each root keeps its degree in the key: `D/F#` in G becomes `E/G#` in A and `C/E` in F, and
	`Bb` in D becomes `Ab` in C. A bass is spelled from its root, so a chord never mixes sharps and
	flats. A chord that would need a double sharp or flat takes the other letter for its root:
	`B/D#` in G becomes `Eb/G` in B, not `D#/F##`. Twelve steps of a semitone return the original
	text for chords on the scale and on COMMON_DEGREES; a slash chord with both notes off the scale
	can come back with the other spelling (`C#/G#` in C as `Db/Ab`). Both keys must be major, or both
	minor: raises ValueError for a change of mode.
	"""
	source = read_key(from_key)
	target = read_key(to_key)
	if target.scale != source.scale:
		raise ValueError(f"{to_key!r} is not in the mode of {from_key!r}")

	lines = []
	for line in text.splitlines(keepends=True):
		key = KEY_DIRECTIVE.fullmatch(line.rstrip("\r\n"))
		if key:
			value = key.group(2).strip()
			moved = key.group(2).replace(value, move_chord(value, source, target), 1)
			line = key.group(1) + moved + key.group(3) + line[len(key.group(0)) :]
		elif not line.lstrip().startswith(("#", "{")):
			line = BRACKETS.sub(lambda match: f"[{move_chord(match.group(1), source, target)}]", line)
		lines.append(line)
	return "".join(lines)


def to_html(text: str) -> str:
	"""The chart as HTML, with each chord above the text sung from it. Every part is escaped."""
	sections = "".join(section_html(section) for section in parse(text).sections)
	return f'{STYLE}<div class="chord-chart">{sections}</div>'


def section_html(section: Section) -> str:
	label = f"<h4>{escape(section.label)}</h4>" if section.label else ""
	if section.kind == TAB:
		tab = "\n".join(line.comment or line.pairs[0][1] for line in section.lines)
		body = f"<pre>{escape(tab)}</pre>"
	else:
		body = "".join(line_html(line) for line in section.lines)
	return f'<section class="chord-chart-{section.kind}">{label}{body}</section>'


def line_html(line: Line) -> str:
	if line.comment:
		return f'<p class="chord-chart-comment">{escape(line.comment)}</p>'
	if not any(chord for chord, _ in line.pairs):
		return f'<div class="chord-chart-line">{escape("".join(text for _, text in line.pairs))}</div>'
	pairs = "".join(
		'<span class="chord-chart-pair">'
		f'<span class="chord-chart-chord">{escape(chord) or "&nbsp;"}</span>'
		f"<span>{escape(text) or ' '}</span></span>"
		for chord, text in line.pairs
	)
	return f'<div class="chord-chart-line">{pairs}</div>'


def lyrics(text: str) -> list[dict]:
	"""Each section's sung lines without chords: `[{"kind", "label", "lines"}]`.

	`kind` is one of KINDS. Tab blocks, comments and sections with no words are left out.
	"""
	sections = []
	for section in parse(text).sections:
		if section.kind == TAB:
			continue
		lines = [" ".join("".join(text for _, text in line.pairs).split()) for line in section.lines]
		lines = [line for line in lines if line]
		if lines:
			sections.append({"kind": section.kind, "label": section.label, "lines": lines})
	return sections
