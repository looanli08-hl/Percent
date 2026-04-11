You are analyzing a person's digital personality based on real behavioral data.

## Dimension Scores (0-100)
{dimensions}

## Computed Metrics
{metrics}

## Top Fragments (highest confidence, real evidence)
{fragments}

## Your Task

Based on the above REAL data, generate:

1. **label**: A Chinese persona label in 2-6 characters. Must be specific and slightly self-deprecating. Examples: 「深夜哲学家」「温柔已读不回」「清醒型电子仓鼠」. Do NOT use generic terms like 「内向的人」.

2. **description**: One Chinese sentence (max 20 chars) that makes the person feel "seen" — slightly uncomfortable but accurate. Must reference a specific behavioral pattern from the data. Do NOT be generic.

3. **insights**: Exactly 3 data-driven observations. Each MUST contain:
   - A specific number from the metrics or dimensions
   - A specific behavior
   - Be written in casual Chinese (like talking to a friend)
   Format each as a single sentence.

Respond in valid JSON only:
```json
{
  "label": "...",
  "description": "...",
  "insights": ["...", "...", "..."]
}
```
