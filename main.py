from langchain_ollama import ChatOllama

# Connects to your local Ollama engine
llm = ChatOllama(model="llama3.1:8b", temperature=0)

response = llm.invoke("Categorize transaction: 'UBER *TRIP SAN FRANCISCO'")
print(response.content)