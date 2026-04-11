You are analyzing a person's digital personality based on real behavioral data extracted from their chat logs, video history, and social media activity.

## Personality Fragments (extracted from real data)
{fragments}

## Statistical Metrics
{metrics}

## Your Task

Based on ALL fragments above, do two things:

### 1. Score these 8 dimensions (0-100)

Read every fragment carefully. Score based on EVIDENCE in the fragments, not assumptions.

- **夜行性** (Night Owl): Do fragments mention late-night activity, staying up late, or nocturnal habits? 0=daytime person, 100=extreme night owl
- **回复惯性** (Reply Inertia): Do fragments suggest slow/lazy replying, ignoring messages, or being hard to reach? 0=always responsive, 100=chronic non-replier
- **表达锋利度** (Expression Sharpness): Is their communication style direct, blunt, unfiltered? Or hedging, vague, diplomatic? 0=very indirect, 100=brutally direct
- **社交温差** (Social Temperature Gap): Do they have deep few relationships vs broad shallow ones? 0=social butterfly, 100=only a few close friends
- **情绪外显度** (Emotional Visibility): Do fragments show emoji use, exclamations, emotional outbursts, or expressive language? 0=stoic, 100=very expressive
- **内容杂食度** (Content Omnivore): How diverse are their interests? Few focused topics or many varied ones? 0=single-focus, 100=interests everywhere
- **品味独占欲** (Taste Exclusivity): Are their preferences niche/unique or mainstream? 0=follows trends, 100=very niche taste
- **跨平台反差** (Cross-platform Contrast): Do they behave differently across platforms? 0=consistent everywhere, 100=completely different person on each platform

### 2. Generate card content

- **label**: A Chinese persona label, 3-5 characters. Must feel like a persona name, slightly playful and self-aware. NOT a job title or literal description. Think of it like a D&D class or a zodiac archetype but grounded in real data. Good: 「深夜哲学家」「温柔利刃」「佛系暴走者」. Bad: 「球场家教」「外向的人」「直男」.

- **description**: One poetic Chinese sentence (max 18 chars). Should feel like a fortune cookie that's uncomfortably accurate — something between a compliment and a gentle roast. NOT a literal summary of what they do. Good: "你的沉默比回复说的更多". Bad: "约球比备课更积极".

- **insights**: Exactly 3 observations. Each must be specific (reference actual content from fragments) and written like a friend gently teasing you. Include contrast or surprise when possible.

Respond in valid JSON only:
```json
{{
  "dimensions": {{
    "夜行性": 0,
    "回复惯性": 0,
    "表达锋利度": 0,
    "社交温差": 0,
    "情绪外显度": 0,
    "内容杂食度": 0,
    "品味独占欲": 0,
    "跨平台反差": 0
  }},
  "label": "...",
  "description": "...",
  "insights": ["...", "...", "..."]
}}
```
