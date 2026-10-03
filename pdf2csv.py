from read_statements import get_transatctions_from_pdf, classify_by_merchant, parse_signed_amount
import csv
import os
from pathlib import Path
import pdfplumber


bank =""

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
def get_password(pdf_path : str)-> str:
    password = ""
    print("Enter bank: ")
    global bank
    bank = input().lower()

    try:
        pdfplumber.open(str(pdf_path))
    except Exception as e:
        print("Trying to get passwrod from env")
        bank_password_dict = {
            "sbi": "SBICARD_CC", "icici": "ICICI_SAPHIRO_CC", "scapia": "SCAPIA"}

        if bank not in bank_password_dict:
            raise ValueError(f"Bank '{bank}' not recognized. Please enter a valid bank name.")

        password_key = bank_password_dict[bank]
        password = os.getenv(password_key)

        if not password:
             raise RuntimeError("password was not loaded. Check passwords.env.")
    return password


def convert_transactions_pdf_to_csv(pdf_path: str):
    password = get_password(pdf_path)
    is_sbi = "sbi" in bank
    lines = get_transatctions_from_pdf(pdf_path, password, is_sbi)
    categories = ["Transportation", "Home", "Groceries", "Health", "Entertainment", "Vacation", "EatOut", "Uncategorized"]
    local_grocery_merchants = (
        "transactions that have indian people names such as Nandkishor, ParmeshwarGupta, Bherulal"
    )
    category_rules = (
        "Transportation - Uber, Ola, Cab, Bus, Train; "
        "Home -  Rent, Electricity, Gas, Airtel(wifi), snabbit, urbancompany, Rentomojo; "
        f"Groceries - local grocery merchant {local_grocery_merchants}, Dmart, BigBasket, AmazonFresh, FlipkartGrocery; "
        "Shopping - Amazon, Flipkart, Myntra, Ajio, Nykaa, TataCliq, Snapdeal;"
        "Health - Pharmacy, Doctor, Hospital, sports equipments, medical tests; "
        "Entertainment - Movies, Concerts, Games, events tickets; "
        "Vacation - Hotels, Resorts, Travel Packages, flights, indigo; "
        "EatOut - Zomato, Swiggy, restaurants, cafes, bars, pubs, food delivery services, hospitality services; "
        "Uncategorized - Any transaction that does not fit into the above categories and/or unknown transactions"
    )

    llm = ChatOllama(model="llama3.1:8b", temperature=0)

    transactions_text = "\n".join(f"{i + 1}. {txn}" for i, txn in enumerate(lines))
    system_prompt = (
        "You are a financial assistant. Categorize each transaction strictly into one of these categories: "
        f"{categories}. "
        f"Category rules: {category_rules}. "
        "Critical precedence rules: exact merchant names override semantic guesses. "
        "If a transaction contains a known food/delivery/hospitality merchant such as Zomato, Swiggy, restaurant, cafe, bar, pub, food delivery, or hospitality services, classify it as 'EatOut' even if the word 'hospital' appears inside a larger word like 'hospitality'. "
        "Health only applies to actual medical merchants such as pharmacy, doctor, clinic, hospital, diagnostic, lab test. Do not classify 'hospitality' as Health. "
        "If a transaction is unclear, put them under 'Uncategorized'. "
        "Use only the transaction strings below. Do not invent rows or categories."
        "Do not double count transactions in multiple categories."
        "Create a note on credits separately. Create another note on Uncategorized transactions separately.  "
        "Also give a split up of what transactions were categorized under each category and the total amount spent in each category. "
    )
    user_prompt = (
        "Categorize the transactions and return a compact table with Category and Total.\n\n"
        f"Transactions:\n{transactions_text}"
    )

    csv_file = Path(__file__).resolve().parent / "categorized_transactions.csv"
    with open(csv_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Transaction", "Cost", "Category"])
        for transaction in lines:
            category = classify_by_merchant(transaction)
            if not category:
                response = llm.invoke([
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=f"Categorize this single transaction strictly to one category: {transaction}\nReturn only the category name."),
                ])
                category = response.content.strip().strip("`\n\r").strip()
            cost = parse_signed_amount(transaction)
            writer.writerow([transaction, cost, category])

    
           