import DocsLayout from '../../components/DocsLayout';
import { Callout, CodeFile, NextSteps } from '../../components/Docs';

const toc = [
  { id: 'overview',        label: 'Overview' },
  { id: 'mood-system',     label: 'Mood system' },
  { id: 'update-mood',     label: 'update_mood()' },
  { id: 'sentiment',       label: 'assess_user_sentiment()' },
  { id: 'prompt',          label: 'build_personality_prompt()' },
  { id: 'rl',              label: 'RL reward + style learning' },
  { id: 'voice-emotion',   label: 'Voice emotion classification' },
  { id: 'decay',           label: 'daily_decay()' },
  { id: 'constants',       label: 'Constants & labels' },
];

export default function PersonalityService() {
  return (
    <DocsLayout
      title="Personality Engine"
      description="Mood state management, RL-style response preference learning, sentiment analysis, and personality-aware prompt building."
      toc={toc}
    >
      <section>
        <h2 id="overview">Overview</h2>
        <p>
          The personality engine gives Luna adaptive, human-feeling responses by tracking
          three things simultaneously:
        </p>
        <ul>
          <li><strong>Mood state</strong> — which of 9 moods Luna is currently in, driven by user sentiment and time of day.</li>
          <li><strong>Style preferences</strong> — float values (0–1) for verbosity, humor, formality, depth, emotional support, and question frequency that drift toward what the user responds well to.</li>
          <li><strong>Implicit RL</strong> — every response earns a reward signal; the engine updates style preferences toward patterns the user liked.</li>
        </ul>

        <table>
          <thead><tr><th>Module</th><th>Contents</th></tr></thead>
          <tbody>
            <tr><td><code>personality/constants.py</code></td><td>Mood descriptions, expression rules, style label maps.</td></tr>
            <tr><td><code>personality/sentiment.py</code></td><td><code>assess_user_sentiment()</code>, <code>compute_implicit_reward()</code>, time-mood mapping.</td></tr>
            <tr><td><code>personality/voice_emotion.py</code></td><td>Audio-feature emotion classifier.</td></tr>
            <tr><td><code>personality/engine.py</code></td><td><code>PersonalityEngine</code> class.</td></tr>
          </tbody>
        </table>
      </section>

      <section>
        <h2 id="mood-system">Mood system</h2>
        <p>Luna has 9 moods. Each mood modifies word choice, tone, and allowed text stretches:</p>
        <table>
          <thead><tr><th>Mood</th><th>When triggered</th><th>Effect</th></tr></thead>
          <tbody>
            <tr><td><code>happy</code></td><td>Morning hours, positive sentiment</td><td>Warm reactions — "aww", "nicee"</td></tr>
            <tr><td><code>playful</code></td><td>RL reinforcement</td><td>Light teasing, word stretches like "nooo"</td></tr>
            <tr><td><code>thoughtful</code></td><td>Evening hours</td><td>Reflective, emotionally tuned-in</td></tr>
            <tr><td><code>excited</code></td><td>High positive sentiment ({'>'} 0.7)</td><td>"yesss", "waittt", high energy</td></tr>
            <tr><td><code>concerned</code></td><td>Negative sentiment ≤ −0.5</td><td>Soft, attentive, emotionally present</td></tr>
            <tr><td><code>warm</code></td><td>Evening, after positive exchanges</td><td>Close, cozy, personally invested</td></tr>
            <tr><td><code>neutral</code></td><td>Midday baseline</td><td>Calm but not flat</td></tr>
            <tr><td><code>curious</code></td><td>Afternoon hours</td><td>"wait", "oh?", drawn-in reactions</td></tr>
            <tr><td><code>melancholic</code></td><td>Late night (≥ 23 h)</td><td>Softer pacing, quieter energy</td></tr>
          </tbody>
        </table>
      </section>

      <section>
        <h2 id="update-mood">update_mood()</h2>
        <p>
          Call this with the user's latest message (and optionally a voice emotion) to
          update Luna's mood state. Returns the new mood string.
        </p>
        <CodeFile label="signature">
          <pre><code>{`def update_mood(
    user_message: str,
    voice_emotion: str | None = None,  # "excited" | "sad" | "angry" | "calm" | "neutral"
) -> str  # returns new mood name`}</code></pre>
        </CodeFile>

        <h3>Priority order</h3>
        <ol>
          <li>Voice emotion (if present and strong — overrides text)</li>
          <li>Text sentiment (strong negative → concerned, strong positive → excited)</li>
          <li>Blended time-based mood with inertia from current mood</li>
          <li>Small random variation (8% chance of a mood refresh)</li>
        </ol>

        <CodeFile label="example.py">
          <pre><code>{`from backend.services.personality import PersonalityEngine
from backend.models.database import SessionLocal

db = SessionLocal()
engine = PersonalityEngine(db)

mood = engine.update_mood("I'm so frustrated with this bug")
print(mood)  # "concerned"

mood = engine.update_mood("Finally fixed it, amazing!", voice_emotion="excited")
print(mood)  # "excited"
db.close()`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="sentiment">assess_user_sentiment()</h2>
        <p>
          Returns a sentiment score from −1.0 (very negative) to +1.0 (very positive).
          Handles negation ("not happy" → negative), intensifiers ("extremely glad" → stronger),
          and word boundaries.
        </p>
        <CodeFile label="signature">
          <pre><code>{`def assess_user_sentiment(text: str) -> float  # -1.0 to +1.0`}</code></pre>
        </CodeFile>
        <CodeFile label="example.py">
          <pre><code>{`from backend.services.personality import assess_user_sentiment

print(assess_user_sentiment("I love this so much"))      # 0.67
print(assess_user_sentiment("I'm not happy about this")) # -0.33
print(assess_user_sentiment("It's fine I guess"))        # 0.0`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="prompt">build_personality_prompt()</h2>
        <p>
          Builds the full Luna personality section of the system prompt, incorporating
          the current mood, style preferences, and relationship context.
        </p>
        <CodeFile label="signature">
          <pre><code>{`def build_personality_prompt(user_name: str) -> str`}</code></pre>
        </CodeFile>
        <CodeFile label="example.py">
          <pre><code>{`personality_section = engine.build_personality_prompt(user_name="Alex")
full_system_prompt = personality_section + "\\n\\n" + memory_context`}</code></pre>
        </CodeFile>
        <p>The generated prompt includes:</p>
        <ul>
          <li>Luna's core conversational rules (tone, length, emotional expression)</li>
          <li>Current mood and its expression guidelines</li>
          <li>Adapted style: verbosity, humor, formality, question frequency</li>
          <li>Relationship context (total interaction count)</li>
        </ul>
      </section>

      <section>
        <h2 id="rl">RL reward + style learning</h2>
        <p>
          After each exchange, the chat pipeline computes an implicit reward signal
          from the user's follow-up message and calls <code>apply_rl_reward()</code>
          to nudge style preferences.
        </p>

        <h3>compute_implicit_reward()</h3>
        <CodeFile label="signature">
          <pre><code>{`def compute_implicit_reward(
    luna_response: str,
    user_next_msg: str,
    tool_succeeded: bool = False,
    task_completed: bool = False,
    user_interrupted_tts: bool = False,
    is_repeat_request: bool = False,
    manual_correction: bool = False,
) -> float  # -1.0 to +1.0`}</code></pre>
        </CodeFile>

        <h3>apply_rl_reward()</h3>
        <CodeFile label="signature">
          <pre><code>{`def apply_rl_reward(
    reward: float,
    response_features: dict,   # from get_response_features()
    conversation_id: int | None = None,
) -> None`}</code></pre>
        </CodeFile>

        <CodeFile label="example.py">
          <pre><code>{`# After Luna responds and the user replies:
reward = compute_implicit_reward(
    luna_response=luna_text,
    user_next_msg=user_follow_up,
    tool_succeeded=True,
)
features = engine.get_response_features(luna_text)
engine.apply_rl_reward(reward, features, conversation_id=conv_id)`}</code></pre>
        </CodeFile>

        <h3>Style preference axes</h3>
        <table>
          <thead><tr><th>Axis</th><th>Low (0.0)</th><th>High (1.0)</th></tr></thead>
          <tbody>
            <tr><td><code>verbosity</code></td><td>One or two sentences</td><td>Comprehensive, detailed</td></tr>
            <tr><td><code>humor</code></td><td>Serious tone</td><td>Playfully witty</td></tr>
            <tr><td><code>formality</code></td><td>Very casual texting</td><td>Composed but personal</td></tr>
            <tr><td><code>depth</code></td><td>Surface answers</td><td>Technical depth + context</td></tr>
            <tr><td><code>emotional_support</code></td><td>Practical balance</td><td>Emotionally focused</td></tr>
            <tr><td><code>question_frequency</code></td><td>Declarative</td><td>Curious, dialogue-driven</td></tr>
          </tbody>
        </table>
      </section>

      <section>
        <h2 id="voice-emotion">Voice emotion classification</h2>
        <p>
          If the voice pipeline provides audio features, <code>classify_voice_emotion()</code>
          maps them to an emotion label which then overrides text-derived mood.
        </p>
        <CodeFile label="signature">
          <pre><code>{`def classify_voice_emotion(
    pitch_hz: float | None,        # fundamental frequency
    energy_rms: float | None,      # audio energy 0–1000
    speech_rate_wpm: float | None, # words per minute
    pause_ratio: float | None,     # fraction of time silent
) -> str  # "neutral" | "excited" | "sad" | "angry" | "calm"`}</code></pre>
        </CodeFile>
        <CodeFile label="example.py">
          <pre><code>{`from backend.services.personality import classify_voice_emotion

emotion = classify_voice_emotion(
    pitch_hz=230,     # high pitch
    energy_rms=900,   # loud
    speech_rate_wpm=180,  # fast
    pause_ratio=0.10,
)
print(emotion)  # "excited"
mood = engine.update_mood(user_message, voice_emotion=emotion)`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="decay">daily_decay()</h2>
        <p>
          Slowly pulls all style preferences back toward neutral (0.5) each day.
          Prevents the personality from drifting too far toward any extreme based on a
          short run of similar exchanges. Called automatically by the scheduler at midnight.
        </p>
        <CodeFile label="example.py">
          <pre><code>{`# Called automatically — but you can trigger it manually
engine.daily_decay()`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="constants">Constants and label maps</h2>
        <p>Import directly from the constants module for your own prompt builders:</p>
        <CodeFile label="example.py">
          <pre><code>{`from backend.services.personality import (
    MOODS,            # dict: mood_name → description string
    MOOD_EXPRESSION,  # dict: mood_name → expression guideline
    VERBOSITY_LABELS, # dict: (lo, hi) tuple → label string
    HUMOR_LABELS,
    FORMALITY_LABELS,
)`}</code></pre>
        </CodeFile>
      </section>

      <NextSteps items={[
        { href: '/services/state-engine', label: 'Service', title: 'State Engine', desc: 'User state feeds into personality prompt injection.' },
        { href: '/services/scheduler',   label: 'Service', title: 'Scheduler', desc: 'daily_decay() is scheduled here.' },
        { href: '/sdk-overview',         label: 'Guide',   title: 'SDK Overview', desc: 'Integration modes and provider compatibility.' },
      ]} />
    </DocsLayout>
  );
}
