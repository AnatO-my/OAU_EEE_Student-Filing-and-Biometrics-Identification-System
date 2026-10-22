import argparse
import csv
from pathlib import Path


from student_results import export_student_results


from record_imports.pdf_tables import extract_pdf_tables, header_key


def convert_pdf(input_file, output_folder, strategy="lines", students=False):
    input_path = Path(input_file)
    output_path = Path(output_folder)
    if not input_path.is_file():
        raise FileNotFoundError(f"PDF not found: {input_path}")
    extracted = extract_pdf_tables(input_path, strategy)
    header = extracted["header"]
    combined_rows = extracted["rows"]
    extra_text = [extracted["extra_text"]] if extracted["extra_text"] else []

    output_path.mkdir(parents=True, exist_ok=True)

    # Write all table data once, after processing every page.
    if header is not None:
        csv_path = output_path / f"{input_path.stem}_tables.csv"

        with csv_path.open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.writer(file)
            writer.writerow(["source_page", "source_table"] + header)
            writer.writerows(combined_rows)

        print(f"Saved {len(combined_rows)} extracted table rows: {csv_path}")
    else:
        print("No tables detected; no CSV created.")

    # Write the extra information separately.
    text_path = output_path / f"{input_path.stem}_extra.txt"
    text_path.write_text("\n\n".join(extra_text), encoding="utf-8")
    print(f"Saved extra information: {text_path}")

    if students:
        if header is None:
            raise ValueError("Student extraction requires a detected master marks sheet table.")
        return export_student_results(csv_path, text_path, output_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Combine PDF tables and extract extra text."
    )
    parser.add_argument("input_pdf")
    parser.add_argument("output_folder")
    parser.add_argument(
        "--strategy", choices=["lines", "text"], default="lines"
    )
    parser.add_argument(
        "--students", action="store_true",
        help="Also export student fields from the master marks sheet layout."
    )
    args = parser.parse_args()

    convert_pdf(args.input_pdf, args.output_folder, args.strategy, args.students)
