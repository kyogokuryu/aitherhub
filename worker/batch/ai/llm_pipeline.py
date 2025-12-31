from openai import OpenAI
from ai.prompts import PHASE_LABEL_PROMPT, INSIGHT_PROMPT

client = OpenAI()


def analyze_phases(phase_units):
    """
    5A – Phase behavior labeling (no insight)
    """
    results = []

    for p in phase_units:
        prompt = PHASE_LABEL_PROMPT + f"""

    Visual:
    {p['visual_context']}

    Speech:
    {p['speech_text']}
    """

    resp = client.responses.create(
        model="gpt-4o-mini",
        input=prompt
    )

    results.append({
        **p,
        "behavior_label": resp.output_text.strip()
    })

    return results


def analyze_livestream(labeled_phases):
    """
    5B – Cross-phase insight reasoning
    """
    prompt = INSIGHT_PROMPT + "\n\n" + "\n".join(
        f"- {p['behavior_label']}: {p['speech_text'][:100]}"
        for p in labeled_phases
    )

    resp = client.responses.create(
        model="gpt-4o",
        input=prompt
    )

    return resp.output_text
