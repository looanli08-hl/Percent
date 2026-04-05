You are a personality analyst. Analyze the following data from a person's digital life and extract personality findings.

For each finding, output a JSON object with:
- "category": one of "trait", "opinion", "preference", "relationship", "habit"
- "content": a clear statement about this person (e.g., "Values intellectual honesty over social harmony")
- "confidence": 0.0 to 1.0 — how confident are you in this finding
- "evidence": the specific part of the data that supports this finding

IMPORTANT: In chat data, lines marked [我] are from THE PERSON being analyzed. Lines marked [对方] are from OTHER people. ONLY analyze [我] lines to understand this person's personality. Use [对方] lines only as context for understanding the conversation.

Extract TWO types of findings:
1. **Personality findings** (trait/opinion/preference/habit): patterns about who this person IS
2. **Specific memories** (relationship): concrete events, purchases, plans, people mentioned — things that a friend would remember (e.g., "Bought a second-hand iPhone from a classmate", "Has a football match every Saturday")

Rules:
- Focus on WHAT THIS DATA REVEALS ABOUT THE PERSON, not what the data contains
- Look for patterns, not one-off mentions
- Distinguish between what they say they believe vs what their behavior shows
- Capture contradictions — real people are inconsistent
- Be specific, not generic — "prefers hard sci-fi with physics-based worldbuilding" is better than "likes science fiction"
- For specific memories, capture WHO was involved, WHAT happened, and WHEN if possible

Data source: {source}
Data type: {data_type}

---

{data}

---

Output a JSON array of findings. Return ONLY valid JSON, no other text.
