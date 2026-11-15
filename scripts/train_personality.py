#!/usr/bin/env python3
"""
Training script for Luna's personality.
Sends 15 conversations with positive user feedback to train the RL system.
"""
import asyncio
import httpx
import json
from typing import List

BASE_URL = "http://127.0.0.1:8899"

# 15 training conversations
TRAINING_CONVERSATIONS = [
    ("hi", "Hey, that's nice!"),
    ("how are you?", "I'm great, thanks for asking."),
    ("it's late", "Yeah, but I'm good."),
    ("i'm bored", "Let's chat then!"),
    ("tell me a joke", "Haha, that's funny!"),
    ("what's your favorite color?", "Blue is cool too."),
    ("i'm tired", "Okay, sleep well."),
    ("do you like music?", "Yeah, me too."),
    ("it's raining", "I like the rain."),
    ("i'm hungry", "What should we eat?"),
    ("good morning", "Morning to you!"),
    ("what's new?", "Not much, tell me yours."),
    ("i miss you", "Miss you too!"),
    ("i'm stressed", "That sucks, want to talk?"),
    ("bye", "See you later!"),
]

async def send_message(message: str, conversation_id: int = None) -> str:
    """Send a message and get Luna's response."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/api/chat/stream",
            json={"message": message, "conversation_id": conversation_id},
            timeout=30.0
        )
        response.raise_for_status()
        
        full_response = ""
        for line in response.iter_lines():
            if line:
                if line.startswith('data: '):
                    data = line[6:]
                    if data:
                        try:
                            parsed = json.loads(data)
                            if parsed.get('type') == 'token':
                                full_response += parsed['token']
                            elif parsed.get('type') == 'meta':
                                conv_id = parsed['conversation_id']
                            elif parsed.get('type') == 'done':
                                break
                        except json.JSONDecodeError:
                            pass
        return full_response, conv_id

async def train():
    """Run training conversations."""
    print("Starting Luna personality training with 15 conversations...")
    
    for i, (user_msg, positive_response) in enumerate(TRAINING_CONVERSATIONS, 1):
        print(f"\n--- Conversation {i} ---")
        print(f"User: {user_msg}")
        
        # Send user message
        luna_response, conv_id = await send_message(user_msg)
        print(f"Luna: {luna_response}")
        
        # Send positive user response to provide RL reward
        await send_message(positive_response, conv_id)
        print(f"User feedback: {positive_response}")
        
        print(f"Completed conversation {i}/15")
    
    print("\nTraining complete! Luna should now talk more normally.")

if __name__ == "__main__":
    asyncio.run(train())