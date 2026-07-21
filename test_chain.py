"""Quick manual test for chain.py -- run with: python test_chain.py

Prereqs:
  - ollama serve running
  - pip install langchain-ollama (if not already in the venv)
"""
from chain import answer

print("--- In-context question ---")
print(answer("What was Apple's revenue in FY2024?"))

print()
print("--- Out-of-context question (should refuse, not fabricate) ---")
print(answer("What is the weather today?"))