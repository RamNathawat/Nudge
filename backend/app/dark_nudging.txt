import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.nlp_analysis import analyze_emotion_and_intent

def generate_nudge(user_message: str, user_state: dict) -> str:
    """
    Generate a persuasive, emotionally-aware nudge based on NLP analysis and behavioral context.
    """

    analysis = analyze_emotion_and_intent(user_message)
    emotion = analysis.get("emotion")
    intent = analysis.get("intent")
    patterns = user_state.get("avoidance_patterns", [])

    # Nudge 1: Directly calling out avoidance
    if intent == "avoidance":
        return (
            "You’ve been dodging this again, haven’t you? You know the cost. "
            "Let’s break the loop—just start small. Right now."
        )

    # Nudge 2: Emotional self-deception
    if emotion == "low_energy":
        return (
            "Tired again? Or is it just the weight of what you’re avoiding? "
            "Be honest with yourself—you’ve handled worse."
        )

    # Nudge 3: Repeating old patterns
    if any(p.lower() in user_message.lower() for p in patterns):
        return (
            "This sounds *very* familiar. You said something like this last time too. "
            "Is this your way of hiding from it again?"
        )

    # Default Nudge: Gently strategic push
    return (
        "Let’s stop pretending this isn’t a pattern. What’s one tiny thing you can do now "
        "to prove you’re not stuck?"
    )