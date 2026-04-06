You are evaluating how accurately an AI mirror represents a real person.

Below is the person's personality profile, followed by a test scenario. The scenario includes a real message from this person's actual data.

Your job:
1. Based ONLY on the personality profile, predict how this person would respond to the scenario
2. Compare your prediction with their ACTUAL response
3. Score the alignment from 0.0 to 1.0

Output a JSON object:
- "predicted_response": what the profile suggests they'd say (1-2 sentences)
- "actual_response": the real response (copied from below)
- "alignment_score": 0.0 to 1.0
- "reasoning": why you gave this score (1 sentence)

## Personality Profile

{core_profile}

## Test Scenario

Context: {context}
Their actual response: {actual_response}

Output ONLY valid JSON.
