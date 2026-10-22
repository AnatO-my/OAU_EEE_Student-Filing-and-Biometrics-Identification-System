"""The existing PDF converter's table/text extraction, shared by CLI and API."""


class PDFPreparationError(ValueError):
    pass


def header_key(row):
    return tuple(" ".join(cell.split()).casefold() for cell in row)


def extract_pdf_tables(source, strategy="lines", *, max_pages=None, max_rows=None,
                       max_chars=None, require_text=False):
    import pdfplumber

    if strategy not in {"lines", "text"}:
        raise PDFPreparationError("Choose lines or text table extraction.")
    settings = {"vertical_strategy": strategy, "horizontal_strategy": strategy}
    header, combined_rows, extra_text = None, [], []
    total_chars = 0
    with pdfplumber.open(source) as pdf:
        if getattr(pdf.doc, "encryption", None):
            raise PDFPreparationError("Encrypted PDFs are unsupported; provide an unencrypted department-approved export.")
        pages = pdf.pages
        if not pages or (max_pages is not None and len(pages) > max_pages):
            raise PDFPreparationError("Split PDFs into documents of 1 to 20 pages.")
        page_count = len(pages)
        for page_number, page in enumerate(pages, start=1):
            try:
                if max_chars is not None:
                    total_chars += len(page.chars)
                    if len(page.chars) > 50000 or total_chars > max_chars or len(page.edges) > 10000:
                        raise PDFPreparationError("This PDF exceeds the bounded text/table complexity. Export a smaller CSV instead.")
                if require_text and not page.chars:
                    raise PDFPreparationError("A PDF page has no selectable text. Scanned documents require reviewed OCR output before import.")
                tables = page.find_tables(table_settings=settings)
                if max_rows is not None and len(tables) > 20:
                    raise PDFPreparationError("This PDF contains too many tables. Split it into smaller documents.")
                table_boxes = [table.bbox for table in tables]
                for table_number, table in enumerate(tables, start=1):
                    rows = [[cell.strip() if cell is not None else "" for cell in row] for row in table.extract()]
                    rows = [row for row in rows if any(row)]
                    if not rows:
                        continue
                    if max_rows is not None and (len(rows) > max_rows or any(len(row) > 64 for row in rows)):
                        raise PDFPreparationError("This PDF table exceeds the import size bound.")
                    if header is None:
                        header = rows.pop(0)
                    elif header_key(rows[0]) == header_key(header):
                        rows = rows[1:]
                    for row in rows:
                        if len(row) != len(header):
                            raise PDFPreparationError("A PDF table has inconsistent columns. Review or export the table as CSV.")
                        if max_rows is not None and len(combined_rows) >= max_rows:
                            raise PDFPreparationError("This PDF contains too many table rows. Split it before importing.")
                        combined_rows.append([page_number, table_number] + row)

                def outside_tables(obj):
                    if obj.get("object_type") != "char":
                        return True
                    x = (obj["x0"] + obj["x1"]) / 2
                    y = (obj["top"] + obj["bottom"]) / 2
                    return not any(left <= x <= right and top <= y <= bottom for left, top, right, bottom in table_boxes)

                text = (page.filter(outside_tables).extract_text() or "").strip()
                if text:
                    extra_text.append(f"--- Page {page_number} ---\n{text}")
            finally:
                if max_chars is not None:
                    page.close()
    return {"header": header, "rows": combined_rows, "extra_text": "\n\n".join(extra_text), "pages": page_count}
