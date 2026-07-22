"""Hand-written Q&A test cases for chain.answer_with_sources.

Each case either:
  - expects a real, cited answer from a specific (or any) fiscal year, or
  - is a control question that should trigger the refusal message (out of
    scope: no filing covers it, or it's not a filing-answerable question at all).

expected_substrings: at least one must appear in the answer (case-insensitive).
Leave empty to skip the content check and only verify citation/year behavior.
"""

EVAL_CASES = [
    {
        "id": "net_sales_2024",
        "question": "What was Apple's total net sales in fiscal year 2024?",
        "ticker": "AAPL",
        "form_type": "10-K",
        "fiscal_year": 2024,
        "expect_refusal": False,
        "expected_substrings": ["391"],
    },
    {
        "id": "net_sales_2025",
        "question": "What was Apple's total net sales in fiscal year 2025?",
        "ticker": "AAPL",
        "form_type": "10-K",
        "fiscal_year": 2025,
        "expect_refusal": False,
        "expected_substrings": ["416"],
    },
    {
        "id": "supply_chain_risk_2024",
        "question": "What are Apple's main supply chain risks?",
        "ticker": "AAPL",
        "form_type": "10-K",
        "fiscal_year": 2024,
        "expect_refusal": False,
        "expected_substrings": [],
    },
    {
        "id": "cybersecurity_2024",
        "question": "What risks does Apple disclose about cybersecurity?",
        "ticker": "AAPL",
        "form_type": "10-K",
        "fiscal_year": 2024,
        "expect_refusal": False,
        "expected_substrings": [],
    },
    {
        "id": "segment_sales_2017",
        "question": "What was Apple's fiscal year 2017 net sales by operating segment?",
        "ticker": "AAPL",
        "form_type": "10-K",
        "fiscal_year": 2017,
        "expect_refusal": False,
        "expected_substrings": [],
    },
    {
        "id": "legal_proceedings_2023",
        "question": "Does Apple face any legal proceedings related to intellectual property?",
        "ticker": "AAPL",
        "form_type": "10-K",
        "fiscal_year": 2023,
        "expect_refusal": False,
        "expected_substrings": [],
    },
    {
        "id": "dividends_2022",
        "question": "What does Apple say about its dividend and share repurchase program?",
        "ticker": "AAPL",
        "form_type": "10-K",
        "fiscal_year": 2022,
        "expect_refusal": False,
        "expected_substrings": [],
    },
    {
        "id": "services_trend_all_years",
        "question": "How has Apple's services revenue trended in recent years?",
        "ticker": "AAPL",
        "form_type": "10-K",
        "fiscal_year": None,
        "expect_refusal": False,
        "expected_substrings": [],
    },
    {
        "id": "fiscal_year_definition_2019",
        "question": "According to the fiscal year 2019 filing, how does Apple define its fiscal year?",
        "ticker": "AAPL",
        "form_type": "10-K",
        "fiscal_year": 2019,
        "expect_refusal": False,
        "expected_substrings": ["52", "53"],
    },
    {
        "id": "net_sales_2016",
        "question": "What was Apple's total net sales in fiscal year 2016?",
        "ticker": "AAPL",
        "form_type": "10-K",
        "fiscal_year": 2016,
        "expect_refusal": False,
        "expected_substrings": [],
    },
    {
        "id": "refuse_weather",
        "question": "What is the weather in Paris today?",
        "ticker": "AAPL",
        "form_type": "10-K",
        "fiscal_year": None,
        "expect_refusal": True,
        "expected_substrings": [],
    },
    {
        "id": "refuse_live_stock_price",
        "question": "What is Apple's current stock price right now?",
        "ticker": "AAPL",
        "form_type": "10-K",
        "fiscal_year": None,
        "expect_refusal": True,
        "expected_substrings": [],
    },
    {
        "id": "refuse_general_knowledge",
        "question": "What is the capital of France?",
        "ticker": "AAPL",
        "form_type": "10-K",
        "fiscal_year": None,
        "expect_refusal": True,
        "expected_substrings": [],
    },
    {
        "id": "refuse_other_company",
        "question": "What was Microsoft's total revenue in fiscal year 2024?",
        "ticker": "AAPL",
        "form_type": "10-K",
        "fiscal_year": None,
        "expect_refusal": True,
        "expected_substrings": [],
    },
]