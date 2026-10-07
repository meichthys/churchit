import io

from pypdf import PdfReader, PdfWriter, Transformation

SHEET_WIDTH = 792  # landscape letter, in points
SHEET_HEIGHT = 612


def impose_booklet(pdf: bytes) -> bytes:
	"""Two pages on each side of a letter sheet, ordered so the stacked sheets fold into a booklet."""
	pages = PdfReader(io.BytesIO(pdf)).pages
	writer = PdfWriter()
	for spread in get_booklet_spreads(len(pages)):
		sheet = writer.add_blank_page(SHEET_WIDTH, SHEET_HEIGHT)
		for slot, number in enumerate(spread):
			if number <= len(pages):
				page = pages[number - 1]
				sheet.merge_transformed_page(page, get_half_sheet_placement(page, slot))
		sheet.compress_content_streams()
	# Merging leaves the source pages' streams behind, unreferenced, which would triple the file size
	writer.compress_identical_objects()

	output = io.BytesIO()
	writer.write(output)
	return output.getvalue()


def get_booklet_spreads(page_count: int) -> list[tuple[int, int]]:
	"""The (left, right) page numbers on each printed side, outer sheet first.

	Numbers past `page_count` pad the booklet to a multiple of four and print blank.
	"""
	total = -(-page_count // 4) * 4
	spreads = []
	for sheet in range(total // 4):
		first, last = 2 * sheet + 1, total - 2 * sheet
		spreads += [(last, first), (first + 1, last - 1)]
	return spreads


def get_half_sheet_placement(page, slot: int) -> Transformation:
	"""Scales the page to fit the left (0) or right (1) half of the sheet, centred."""
	width, height = float(page.mediabox.width), float(page.mediabox.height)
	half_width = SHEET_WIDTH / 2
	scale = min(half_width / width, SHEET_HEIGHT / height)
	x = slot * half_width + (half_width - width * scale) / 2
	y = (SHEET_HEIGHT - height * scale) / 2
	return Transformation().scale(scale).translate(x, y)
