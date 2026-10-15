import os
import re
from pathlib import Path
from sys import prefix

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

import pdfplumber
from dotenv import load_dotenv

def parse_signed_amount(transaction: str) -> float:
    amount_match = re.search(r"[₹]\s*([\d,]+(?:\.\d{1,2})?)", transaction)
    if not amount_match:
        # Some statements omit the currency symbol. Prefer decimal values so
        # dates and trailing reference or reward-point values are not selected.
        amount_matches = list(re.finditer(r"(?<![\d/-])[+\-]?\s*([\d,]+\.\d{1,2})(?!\d)", transaction))
        amount_match = amount_matches[-1] if amount_matches else None
    if not amount_match:
        raise ValueError(f"No amount found in transaction: {transaction}")

    amount = float(amount_match.group(1).replace(",", ""))
    prefix = transaction[:amount_match.end()].lower()
    suffix_c = transaction[amount_match.end():].strip().lower().startswith("c")
    is_prev_bill_payment = ("billpayment" in prefix and "+" in prefix ) or ("debit payment" in prefix)
    if is_prev_bill_payment:
        return 0.0 # skip previous bill payments as they are not actual expenses
    is_credit = "refund" in prefix and "+" in prefix or suffix_c
    return amount if is_credit else -amount


def sum(transactions : list[str]) -> float:
    total = 0.0
    for transaction in transactions:
        amount = parse_signed_amount(transaction)
        total += amount
    return total

def normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()

def classify_by_merchant(transaction: str) -> str | None:
    text = normalize_text(transaction)
    if not text:
        return None

    eat_out_markers = [
        "zomato", "swiggy", "uber eats", "foodpanda", "dominos", "pizza hut",
        "mcdonalds", "kfc", "subway", "restaurant", "restaurants", "cafe", "cafes",
        "coffee", "bakery", "bar", "pub", "lounge", "food delivery",
        "hospitality", "hospitality services", "dining", "tandoor", "bistro"
    ]
    health_markers = [
        "pharmacy", "chemist", "doctor", "clinic", "hospital", "medical", "diagnostic",
        "pathology", "lab test", "optical", "dentist"
    ]
    transportation_markers = [
        "uber", "ola", "cab", "bus", "train", "metro", "airport taxi",
        "railway", "auto"
    ]
    entertainment_markers = [
        "movie", "movies", "cinema", "theatre", "concert", "tickets", "game",
        "streaming", "spotify", "netflix", "bookmyshow", "event"
    ]
    home_markers = [
        "rent", "electricity", "gas", "airtel", "wifi", "snabbit", "urbancompany",
        "rentomojo", "maintenance", "apartment"
    ]
    vacation_markers = [
        "hotel", "resort", "travel", "flight", "airline", "booking", "staycation"
    ]

    # Exact merchant matches override fuzzy semantic guesses.
    if any(marker in text for marker in eat_out_markers):
        return "EatOut"
    if any(marker in text for marker in health_markers):
        # Avoid false positives like 'hospitality' which contains 'hospital' as a substring.
        if "hospitality" in text:
            return "EatOut"
        return "Health"
    if any(marker in text for marker in transportation_markers):
        return "Transportation"
    if any(marker in text for marker in entertainment_markers):
        return "Entertainment"
    if any(marker in text for marker in home_markers):
        return "Home"
    if any(marker in text for marker in vacation_markers):
        return "Vacation"
    return None
    
def get_transatctions_from_pdf(pdf_path: Path, password: str, is_sbi = False) -> list[str]:
    date_pattern ='' # Regex: Starts with a date 
    if not is_sbi:
        #(e.g., 01/15/2024 or 15-Jan-2024)
        date_pattern = re.compile(
            r"^(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}-[A-Za-z]{3}-\d{2,4})"
        )
    else:
        # e.g. 15 Jan 2024
        date_pattern = re.compile(r"\d{1,2}\s+[A-Za-z]{3}\s+\d{2,4}")
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

    return lines


