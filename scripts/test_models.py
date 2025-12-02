import os

import anthropic

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

models_to_try = [
    "claude-3-5-sonnet-20240620",
    "claude-3-5-sonnet-20241022",
    "claude-3-sonnet-20240229",
    "claude-3-opus-20240229",
    "claude-3-haiku-20240307",
]

print("Testing Anthropic Models...")
for model in models_to_try:
    try:
        print(f"Testing {model}...")
        message = client.messages.create(
            model=model, max_tokens=10, messages=[{"role": "user", "content": "Hello"}]
        )
        print(f"✅ {model} WORKS!")
        break
    except Exception as e:
        print(f"❌ {model} FAILED: {e}")
