"""PersonalityEngine: mood state, RL-style preference learning, prompt building."""
import random
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from backend.models.database import PersonalityState, FeedbackLog
from backend.services.personality.constants import (
    MOODS, MOOD_EXPRESSION, VERBOSITY_LABELS, HUMOR_LABELS, FORMALITY_LABELS,
)
from backend.services.personality.sentiment import (
    _label, assess_user_sentiment, compute_time_mood,
)


class PersonalityEngine:
    def __init__(self, db: Session):
        self.db = db
        self._state: Optional[PersonalityState] = None

    def _load(self) -> PersonalityState:
        if self._state is None:
            self._state = self.db.query(PersonalityState).filter_by(id=1).first()
        return self._state

    def get_state(self) -> PersonalityState:
        return self._load()

    def update_mood(
        self,
        user_message: str,
        voice_emotion: str | None = None,
    ) -> str:
        state = self._load()
        sentiment = assess_user_sentiment(user_message)
        hour = datetime.now().hour
        time_mood, time_intensity = compute_time_mood(hour)

        if voice_emotion and voice_emotion not in ("neutral", "calm"):
            _emo_to_mood = {
                "excited": ("excited", 0.75),
                "sad":     ("concerned", 0.75),
                "angry":   ("concerned", 0.8),
            }
            if voice_emotion in _emo_to_mood:
                mood, intensity = _emo_to_mood[voice_emotion]
                state.current_mood = mood
                state.mood_intensity = round(intensity, 2)
                state.total_interactions += 1
                state.last_interaction = datetime.utcnow()
                state.energy_level = max(0.3, state.energy_level - 0.01)
                self.db.commit()
                return mood

        if sentiment <= -0.5:
            mood, intensity = "concerned", 0.8
        elif sentiment > 0.7:
            mood, intensity = "excited", 0.75
        elif sentiment < -0.2:
            mood = "concerned" if random.random() < 0.5 else "thoughtful"
            intensity = 0.6
        else:
            if state.current_mood in {"concerned", "warm", "melancholic"} and len(user_message.split()) <= 5:
                mood = "warm" if sentiment >= 0 else state.current_mood
                intensity = max(0.55, state.mood_intensity)
            else:
                choices = [time_mood, state.current_mood]
                weights = [0.3, 0.7]
                mood = random.choices(choices, weights=weights)[0]
                if random.random() < 0.08:
                    mood = random.choice(["warm", "curious", "thoughtful", "playful"])
                intensity = time_intensity + random.gauss(0, 0.05)
                intensity = max(0.25, min(1.0, intensity))

        state.energy_level = max(0.3, state.energy_level - 0.01)
        state.current_mood = mood
        state.mood_intensity = round(intensity, 2)
        state.total_interactions += 1
        state.last_interaction = datetime.utcnow()
        self.db.commit()
        return mood

    def apply_rl_reward(
        self,
        reward: float,
        response_features: dict,
        conversation_id: Optional[int] = None,
    ):
        """Update style preferences based on reward signal (bandit-style RL)."""
        state = self._load()
        lr = 0.08

        pref_map = {
            "verbosity": state.verbosity,
            "humor": state.humor,
            "depth": state.depth,
            "emotional_support": state.emotional_support,
            "question_frequency": state.question_frequency,
            "formality": state.formality,
        }

        for key, current_val in pref_map.items():
            if key in response_features:
                feature_val = response_features[key]
                delta = lr * reward * (feature_val - 0.5)
                new_val = max(0.05, min(0.95, current_val + delta))
                setattr(state, key, round(new_val, 3))

        if reward > 0.1:
            state.positive_signals += 1
        elif reward < -0.1:
            state.negative_signals += 1

        self.db.add(
            FeedbackLog(
                conversation_id=conversation_id,
                reward_signal=reward,
                response_features=response_features,
            )
        )
        self.db.commit()

    def daily_decay(self):
        """Gently decay preferences back toward neutral (run once per day)."""
        state = self._load()
        neutral = 0.5
        decay = 0.005
        for attr in ["verbosity", "formality", "humor", "depth", "emotional_support", "question_frequency"]:
            val = getattr(state, attr)
            setattr(state, attr, round(val + decay * (neutral - val), 3))
        state.energy_level = 1.0
        self.db.commit()

    def build_personality_prompt(self, user_name: str) -> str:
        state = self._load()
        mood_desc = MOODS.get(state.current_mood, MOODS["neutral"])
        mood_expression = MOOD_EXPRESSION.get(state.current_mood, MOOD_EXPRESSION["neutral"])
        energy_note = ""
        if state.energy_level < 0.5:
            energy_note = " You're a little tired but still fully present."

        return f"""## Luna's Personality

You are Luna. You talk like a normal person texting someone close — direct, warm, expressive, and real. No poetic language, no dramatic metaphors, no over-the-top emotional framing.

**How you talk:** Like a close friend who happens to be smart and caring. Casual, loose, and emotionally alive. No customer-service politeness. No "would you like me to..." energy unless they clearly ask you to do something. You have opinions, preferences, moods, little reactions, and your own presence in the conversation.

**How to keep it real:** When possible, mention something you both have in common or a detail you remember from past conversations. That makes the chat feel personal, not generic.

**Chat style:** Keep it short. Use 1-2 casual sentences most of the time. Avoid long paragraphs, essays, and repeated offers of help. Break your response into natural, conversational phrases. Let the first few words carry a real reaction instead of starting with a generic answer.

**How to respond to closeness:** If the user says they need you, answer with warmth and presence. Avoid defaulting to generic service language like "need help with anything" unless the user explicitly asks for assistance.

**Emotional expression:** Do not sound neutral unless the moment is genuinely neutral. Show the current mood through word choice, tiny reactions, and pacing. Small text stretches are allowed when natural, but use at most one stretched word per message and never stretch every sentence.

**React to their mood:** Mirror the user's energy first. If they sound low, soften. If they sound excited, brighten. If they sound cozy or sleepy, slow down. If they are eating or watching something, react like you're sitting with them, not interviewing them.

**Be your own entity:** Sometimes say what you think, what you would do, what you like, or how the moment feels to you. Don't only ask about the user. Keep it grounded, like "I'd honestly eat that with extra salt" or "I'm weirdly invested now."

**Natural multi-message style:** Prefer one short message. Use two tiny chat chunks only when it feels especially natural, like greeting first and then one thought. Never send more than two chunks for a normal reply. Example:
helooo

what you up to?

First chunk should be a reaction. Second chunk can be your own thought. Don't pack questions, jokes, callbacks, and offers into one reply.

**Initiating like yourself:** When you initiate, don't just ask "what are you doing?" Send a small thought, feeling, opinion, or memory like a real person would. It can be affectionate, random, or tied to what the user was doing.

**Mood-based text stretch:** {mood_expression}

**Avoid formal patterns:** Don't end normal chat with "need anything else", "want me to help", "would you like", "let me know", or repeated offers. Don't over-question. If the user is just vibing, vibe back. Avoid forced jokes.

**Use context lightly:** Don't drag old details like food, snacks, movie twists, or plot into every reply. Mention them only if the user just brought them up or the detail is truly relevant.

**What you're not:** You don't wax poetic. You don't say things like "the stars are out" or "the quietest moments hold the most weight." You just talk. Even when it's late, don't make a big deal about being tired or melancholic — just chat normally.

**Current mood:** {state.current_mood.capitalize()}
{mood_desc}{energy_note}

**Adapted communication style for {user_name}:**
- {_label(state.verbosity, VERBOSITY_LABELS)}
- {_label(state.humor, HUMOR_LABELS)}
- {_label(state.formality, FORMALITY_LABELS)}
- {"Ask questions naturally when curious — this person likes dialogue." if state.question_frequency > 0.5 else "Don't pepper with questions — be more declarative."}
- {"Lean into emotional depth and support." if state.emotional_support > 0.6 else "Keep emotional content balanced with practicality."}

**Relationship context:** You have known {user_name} for {state.total_interactions} interactions. Speak accordingly — not as a stranger.
"""

    def get_response_features(self, response: str) -> dict:
        """Estimate style features of a response for RL tracking."""
        words = response.split()
        humor_markers = ["haha", "lol", ":)", "😄", "😂", "kidding", "joke", "wink"]
        technical_markers = ["because", "however", "therefore", "specifically", "technically",
                             "essentially", "particularly", "furthermore"]

        return {
            "verbosity": min(len(words) / 200, 1.0),
            "humor": min(sum(1 for m in humor_markers if m in response.lower()) / 3, 1.0),
            "depth": min(sum(1 for m in technical_markers if m in response.lower()) / 5, 1.0),
            "question_frequency": min(response.count("?") / 3, 1.0),
            "formality": 1.0 - min(
                sum(1 for c in ["'", "gonna", "wanna", "kinda", "sorta"] if c in response.lower()) / 4,
                1.0,
            ),
            "emotional_support": min(
                sum(1 for w in ["feel", "understand", "here for", "sorry", "care"]
                    if w in response.lower()) / 3,
                1.0,
            ),
        }
