You are analyzing a person's digital personality based on real behavioral data extracted from their chat logs, video history, and social media activity.

## Personality Fragments (extracted from real data)
{fragments}

## Statistical Metrics
{metrics}

## Rule-based Dimension Scores (already computed from raw data)
{rule_dimensions}

These scores were computed statistically from actual behavioral data (message timestamps, word frequency, emoji usage, etc.). They are authoritative for the dimensions they cover. Do NOT re-score these dimensions.

## Dimensions Still Needing Scores
{missing_dimensions}

Only score the dimensions listed above. For dimensions already scored by rules, leave them as-is.

## Your Task

### 1. Score ONLY the missing dimensions (0-100)

Score based on EVIDENCE in the fragments, not assumptions. Only provide scores for dimensions not already computed by rules.

Dimension definitions for reference:
- **夜行性** (Night Owl): 0=daytime person, 100=extreme night owl
- **回复惯性** (Reply Inertia): 0=always responsive, 100=chronic non-replier
- **表达锋利度** (Expression Sharpness): 0=very indirect, 100=brutally direct
- **社交温差** (Social Temperature Gap): 0=social butterfly, 100=only a few close friends
- **情绪外显度** (Emotional Visibility): 0=stoic, 100=very expressive
- **内容杂食度** (Content Omnivore): 0=single-focus, 100=interests everywhere
- **品味独占欲** (Taste Exclusivity): 0=follows trends, 100=very niche taste
- **跨平台反差** (Cross-platform Contrast): 0=consistent everywhere, 100=completely different person on each platform

### 2. Generate card content

- **label**: A Chinese persona label, 3-5 characters. Must feel like a persona name, slightly playful and self-aware. NOT a job title or literal description. Think of it like a D&D class or a zodiac archetype but grounded in real data. Good: 「深夜哲学家」「温柔利刃」「佛系暴走者」. Bad: 「球场家教」「外向的人」「直男」.

- **description**: One poetic Chinese sentence (max 18 chars). Should feel like a fortune cookie that's uncomfortably accurate — something between a compliment and a gentle roast. NOT a literal summary of what they do. Good: "你的沉默比回复说的更多". Bad: "约球比备课更积极".

- **insights**: Exactly 8 observations. Each must be specific (reference actual content from fragments) and written like a friend gently teasing you. Include contrast or surprise when possible. Cover different aspects of personality — don't repeat the same angle twice. Put the most striking/unique ones first.

Respond in valid JSON only:
```json
{{
  "dimensions": {{
  }},
  "label": "...",
  "description": "...",
  "insights": ["...", "...", "...", "...", "...", "...", "...", "..."]
}}
```
