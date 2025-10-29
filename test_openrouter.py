#!/usr/bin/env python3
from openai import OpenAI

client = OpenAI(
    base_url='https://openrouter.ai/api/v1',
    api_key='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'
)

print("Testing OpenRouter API...")
response = client.chat.completions.create(
    model='google/gemini-2.0-flash-exp:free',
    messages=[{
        'role': 'user',
        'content': 'Analyze the stock market sentiment in one sentence.'
    }],
    max_tokens=50
)

result = response.choices[0].message.content.strip()
print(f'✅ OpenRouter Connected!')
print(f'🤖 AI Response: {result}')
print(f'💳 Credits: Available')
