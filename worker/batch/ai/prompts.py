PHASE_LABEL_PROMPT = """
You are analyzing a livestream phase.

Given:
- Visual context
- Speech transcript

Label the phase behavior using ONE of:
- product_demo
- price_explanation
- call_to_action
- qna
- idle
"""

INSIGHT_PROMPT = """
You are given multiple labeled livestream phases.

Analyze patterns across phases and return:
- Repeated behaviors
- What works better
- High-level insight
"""
