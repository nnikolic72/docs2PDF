from pathlib import Path

from docs2pdf.tui import Docs2PDFApp


def main():
    db_path = Path("docs2pdf.db")
    app = Docs2PDFApp(db_path)
    app.run()

if __name__ == "__main__":
    main()
