import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("GATEWAY_API_KEY"),
    base_url="https://llm-gateway-5q22j.ondigitalocean.app",
)


def vision_extract(image_b64: str, response_model: type, system_prompt: str, model: str = "claude-3-5-sonnet"):
    completion = client.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extract data from this page."},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                ],
            },
        ],
        response_format=response_model,
    )
    return completion.choices[0].message.parsed
