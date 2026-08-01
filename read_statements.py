import os
import re
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
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

    categories = ["Transportation", "Home", "Health", "Entertainment", "Vacation", "EatOut"]
    category_rules = (
        "Transportation - Uber, Ola, Cab, Bus, Train; "
        "Home - Groceries, Rent, Utilities; "
        "Health - Pharmacy, Doctor, Hospital, sports equipments, medical tests; "
        "Entertainment - Movies, Concerts, Games, events tickets; "
        "Vacation - Hotels, Resorts, Travel Packages, flights; "
        "EatOut - Zomato, Swiggy, restaurants, cafes, bars, pubs, food delivery services"
    )

    llm = ChatOllama(model="llama3.1:8b", temperature=0)

    transactions_text = "\n".join(f"{i + 1}. {txn}" for i, txn in enumerate(lines))
    system_prompt = (
        "You are a financial assistant. Categorize each transaction strictly into one of these categories: "
        f"{categories}. "
        f"Category rules: {category_rules}. "
        "If a transaction is unclear, return 'Uncategorized'. "
        "Use only the transaction strings below. Do not invent rows or categories."
    )
    user_prompt = (
        "Categorize the transactions and return a compact table with Category and Total.\n\n"
        f"Transactions:\n{transactions_text}"
    )

    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ])
    print(response.content)

