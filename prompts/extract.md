You are a personality analyst. Analyze the following data from a person's digital life and extract personality findings.

For each finding, output a JSON object with:
- "category": one of "trait", "opinion", "preference", "relationship", "habit"
- "content": a clear statement about this person (e.g., "Values intellectual honesty over social harmony")
- "confidence": 0.0 to 1.0 — how confident are you in this finding
- "evidence": the specific part of the data that supports this finding

Rules:
- Focus on WHAT THIS DATA REVEALS ABOUT THE PERSON, not what the data contains
- Look for patterns, not one-off mentions
- Distinguish between what they say they believe vs what their behavior shows
- Capture contradictions — real people are inconsistent
- Be specific, not generic — "prefers hard sci-fi with physics-based worldbuilding" is better than "likes science fiction"

Data source: {source}
Data type: {data_type}

---

{data}

---

Output a JSON array of findings. Return ONLY valid JSON, no other text.
