import os
import re
from pathlib import Path
from langchain_ollama import ChatOllama

import pdfplumber
from dotenv import load_dotenv



if __name__ == "__main__":
    load_dotenv(dotenv_path=Path(__file__).resolve().parent / "passwords.env")

    pdf_path = Path(__file__).resolve().parent / "icici_cc_statement.pdf"
    password = os.getenv("ICICI_SAPHIRO_CC")

    if not password:
        raise RuntimeError("ICICI_SAPHIRO_CC was not loaded. Check passwords.env.")

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found at {pdf_path}")

    # Regex: Starts with a date (e.g., 01/15/2024 or 15-Jan-2024)
    date_pattern = re.compile(
        r"^(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}-[A-Za-z]{3}-\d{2,4})"
    )
    lines = []
    with pdfplumber.open(str(pdf_path), password=password) as pdf:
        for page in pdf.pages:
            # extract_text(layout=True) preserves exact horizontal spacing
            text = page.extract_text(layout=True)

            if text:
                for line in text.split("\n"):
                    clean_line = line.strip()

                    # Ignore headers, footers, and noise; only keep transaction lines
                    if date_pattern.match(clean_line):
                        lines.append(clean_line)

    llm = ChatOllama(model="llama3.1:8b", temperature=0)
    system_msg = "You are a financial assistant. Categorize the following transactions into one of the following categories: Travel, Home essentials, or Health. Only respond with the category name and the amount. The provided line could contain other details too like date, transaction number, points in addition to rate."

    for t in lines:
        input = f"{system_msg}\n\nTransaction: {t}"
        response = llm.invoke(input)
        print(response.content)


