import openai
import os

def check_ai_with_gpt(student_text):
    openai.api_key = os.getenv("OPENAI_API_KEY")

    prompt = f"""
You are a writing analyst. Your task is to review a student's assignment and provide an honest, thoughtful estimate of whether it may have been written by an AI (such as ChatGPT), or by a human.

You do NOT need to be certain — simply use your intuition based on linguistic patterns, structure, tone, and overall complexity.

Please return:
1. A short, polite VERDICT: Human-written, AI-generated, or Unclear
2. A PROBABILITY ESTIMATE: 0–100%
3. A short REASON for your evaluation

Here is the student's submission:
---
{student_text}
---
"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt.strip()}],
            temperature=0.4,
            max_tokens=250
        )
        content = response.choices[0].message["content"]
        return {"result": content.strip()}

    except Exception as e:
        return {"error": f"❌ GPT check failed: {str(e)}"}
# rebuild
