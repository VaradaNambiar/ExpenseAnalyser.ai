import os
import re
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

import pdfplumber
from dotenv import load_dotenv

def sum(transactions : list[str]) -> float:
    total = 0.0
    for transaction in transactions:
        system_prompt = (
            "You are a financial assistant. Extract the amount spent from the transaction string. Put + for credits and - for debits and return only the amount as a float. Do not include any other text or explanation. ")
        user_prompt = (
            f"Transaction: {transaction}\n")
        llm = ChatOllama(model="llama3.1:8b", temperature=0)
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ])
        amount = float(response.content.strip().strip("`\n\r").strip())
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


if __name__ == "__main__":
    load_dotenv(dotenv_path=Path(__file__).resolve().parent / "passwords.env")

    pdf_path = Path(__file__).resolve().parent / "Scapia_July.pdf"
    password = os.getenv("SCAPIA")

    if not password:
        raise RuntimeError("SCAPIA was not loaded. Check passwords.env.")

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

    eat_out_transactions = []
    health_transactions = []
    transportation_transactions = []
    entertainment_transactions = []
    home_transactions = []
    shopping_transactions = []
    groceries_transactions = []
    vacation_transactions = []
    uncategorized_transactions = []
    for transaction in lines:
        override = classify_by_merchant(transaction)
        if override:
            if override == "EatOut":
                eat_out_transactions.append(transaction)
            elif override == "Health":
                health_transactions.append(transaction)
            elif override == "Transportation":
                transportation_transactions.append(transaction)
            elif override == "Entertainment":
                entertainment_transactions.append(transaction)
            elif override == "Home":
                home_transactions.append(transaction)
            elif override == "Groceries":
                groceries_transactions.append(transaction)
            elif override == "Shopping":
                shopping_transactions.append(transaction)
            elif override == "Vacation":
                vacation_transactions.append(transaction)
            continue
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Categorize this single transaction strictly to one category: {transaction}\nReturn only the category name."),
        ])
        category = response.content.strip().strip("`\n\r").strip()
        if category == "EatOut":
            eat_out_transactions.append(transaction)
        elif category == "Health":
            health_transactions.append(transaction)
        elif category == "Transportation":
            transportation_transactions.append(transaction)
        elif category == "Entertainment":
            entertainment_transactions.append(transaction)
        elif category == "Home":
            home_transactions.append(transaction)
        elif category == "Groceries":
            groceries_transactions.append(transaction)
        elif category == "Shopping":
            shopping_transactions.append(transaction)
        elif category == "Vacation":
            vacation_transactions.append(transaction)
        elif category == "Uncategorized":
            uncategorized_transactions.append(transaction)


    print("EatOut Transactions:")
    for transaction in eat_out_transactions:
        print(transaction)

    print("\nHealth Transactions:")
    for transaction in health_transactions:
        print(transaction)

    print("\nTransportation Transactions:")
    for transaction in transportation_transactions:
        print(transaction)  

    print("\nEntertainment Transactions:")
    for transaction in entertainment_transactions:
        print(transaction)

    print("\nHome Transactions:")
    for transaction in home_transactions:
        print(transaction)

    print("\nGroceries Transactions:")
    for transaction in groceries_transactions:
        print(transaction)

    print("\nShopping Transactions:")
    for transaction in shopping_transactions:
        print(transaction)

    print("\nVacation Transactions:")
    for transaction in vacation_transactions:   
        print(transaction) 

    print("\nUncategorized Transactions:")
    for transaction in uncategorized_transactions:
        print(transaction)

    print("\nSummary of Total Amounts Spent in Each Category:")

    total_eat_out = sum(eat_out_transactions)
    total_health = sum(health_transactions)
    total_transportation = sum(transportation_transactions) 
    total_entertainment = sum(entertainment_transactions)
    total_home = sum(home_transactions)
    total_groceries = sum(groceries_transactions)
    total_shopping = sum(shopping_transactions)
    total_vacation = sum(vacation_transactions)
    total_uncategorized = sum(uncategorized_transactions)
    print(f"Total EatOut: {total_eat_out}") 
    print(f"Total Health: {total_health}")
    print(f"Total Transportation: {total_transportation}")      
    print(f"Total Entertainment: {total_entertainment}")
    print(f"Total Home: {total_home}")
    print(f"Total Groceries: {total_groceries}")
    print(f"Total Shopping: {total_shopping}")
    print(f"Total Vacation: {total_vacation}")
    print(f"Total Uncategorized: {total_uncategorized}")

    print("\nOverall Total Amount Spent: " , total_eat_out + total_health + total_transportation + total_entertainment + total_home + total_groceries + total_shopping + total_vacation + total_uncategorized)



