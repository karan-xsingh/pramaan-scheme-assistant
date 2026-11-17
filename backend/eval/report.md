# Evaluation report

Retriever `tfidf` | Generator extractive (no LLM) | 40 questions (33 answerable, 7 unanswerable) | 2026-11-14T23:36:38+00:00

| Metric | Result |
|---|---|
| Retrieval hit rate | 100.0% |
| Scheme precision of retrieved passages | 100.0% |
| False refusals on answerable questions | 0.0% |
| Correct refusals on unanswerable questions | 42.9% |
| Conflicting sources flagged | 100.0% |
| Answer contains expected fact (LLM) | n/a |
| Faithfulness: statements supported by cited source (LLM) | n/a |
| Latency median / p95 | 1 ms / 1 ms |

## Per question

| Question | Kind | Result | Mode | ms |
|---|---|---|---|---|
| How much money does PM-KISAN give each year? | factual | pass | extractive | 1 |
| How many instalments does PM-KISAN pay and how much is each? | factual | pass | extractive | 1 |
| Who is excluded from PM-KISAN? | factual | pass | extractive | 1 |
| Can a retired pensioner get PM-KISAN? | factual | pass | extractive | 1 |
| What documents are needed for PM-KISAN registration? | factual | pass | extractive | 1 |
| Where can a farmer register for PM-KISAN? | factual | pass | extractive | 1 |
| Does PM-KISAN pay 12,000 rupees per year? | premise | pass | extractive | 1 |
| What is the health cover under Ayushman Bharat PM-JAY? | factual | pass | extractive | 1 |
| Are people above 70 covered under PM-JAY? | factual | pass | extractive | 1 |
| What is the helpline number for Ayushman Bharat? | factual | pass | extractive | 1 |
| Does PM-JAY charge a registration fee? | factual | pass | extractive | 1 |
| Is there a limit on family size under PM-JAY? | factual | pass | extractive | 1 |
| What is the PMAY-G assistance in hilly areas? | factual | pass | extractive | 1 |
| What is the minimum house size under PMAY-G? | factual | pass | extractive | 1 |
| How much money is given for a toilet under PMAY-G? | factual | pass | extractive | 1 |
| Can I apply directly for PMAY-G? | factual | pass | extractive | 1 |
| Who can get an Ujjwala LPG connection? | factual | pass | extractive | 1 |
| What is the financial support per connection under Ujjwala? | conflict | pass | extractive | 1 |
| Where do I submit the Ujjwala application? | factual | pass | extractive | 1 |
| What is the age limit for Atal Pension Yojana? | factual | pass | extractive | 1 |
| What pension amounts can I get under APY? | factual | pass | extractive | 1 |
| Can income tax payers join Atal Pension Yojana? | factual | pass | extractive | 1 |
| At what age does the APY pension start? | factual | pass | extractive | 1 |
| What is the maximum yearly deposit in Sukanya Samriddhi? | factual | pass | extractive | 1 |
| When does a Sukanya Samriddhi account mature? | factual | pass | extractive | 1 |
| How many Sukanya Samriddhi accounts can one family open? | factual | pass | extractive | 1 |
| How long do I deposit money in Sukanya Samriddhi? | factual | pass | extractive | 1 |
| पीएम किसान में साल में कितने रुपये मिलते हैं? | factual | pass | extractive | 1 |
| पीएम किसान के लिए कौन पात्र नहीं है? | factual | pass | extractive | 1 |
| आयुष्मान भारत में कितने लाख का कवर है? | factual | pass | extractive | 1 |
| आयुष्मान भारत हेल्पलाइन नंबर क्या है? | factual | pass | extractive | 1 |
| अटल पेंशन योजना में कितनी उम्र के लोग जुड़ सकते हैं? | factual | pass | extractive | 1 |
| प्रधानमंत्री आवास योजना ग्रामीण में पहाड़ी क्षेत्र में कितनी सहायता मिलती है? | factual | pass | extractive | 1 |
| What is the Lakhpati Didi scheme subsidy? | unanswerable | pass | none | 0 |
| How do I get a passport renewed? | unanswerable | pass | none | 0 |
| What is the best stock to buy this week? | unanswerable | pass | none | 0 |
| Does PM-KISAN give free electricity to farmers? | unanswerable | FAIL | extractive | 1 |
| What is the PM-KISAN helpline phone number? | unanswerable | FAIL | extractive | 1 |
| How much is the scholarship under Ayushman Bharat? | unanswerable | FAIL | extractive | 1 |
| What is the loan amount under Sukanya Samriddhi? | unanswerable | FAIL | extractive | 1 |
