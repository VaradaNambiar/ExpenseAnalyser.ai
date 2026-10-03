from langchain_ollama import ChatOllama
from dotenv import load_dotenv
from pathlib import Path
from pdf2csv import convert_transactions_pdf_to_csv


if __name__ == "__main__":
    print("enter pdf path ")
    pdf_path = Path(input().strip())

    load_dotenv(dotenv_path=Path(__file__).resolve().parent / "passwords.env")

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found at {pdf_path}")


    convert_transactions_pdf_to_csv(pdf_path)