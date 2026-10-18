import os
import httpx

API_KEY = os.environ.get("LLM_API_KEY","")
API_URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-chat"

def ask(question: str, history: list) -> str:

    messages = history + [{"role": "user", "content": question}]

    response = httpx.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL,
            "messages": messages,
        },
        timeout=60,
    )

    data = response.json()
    answer = data["choices"][0]["message"]["content"]

    history.append({"role": "user", "content": question})
    history.append({"role": "assistant", "content": answer})

    return answer

def main():
    if not API_KEY:
        print("没找到LLM_API_KEY,请先设置环境变量")
        print(" Powershell: $env:LLM_API_KEY = 'sk-你的key'")
        return

    history = []

    print("=" * 40)
    print("  AI对话(输入exit退出)")
    print("=" * 40)

    while True:
        question = input("\n你: ").strip()

        if question == "exit":
            print("再见喵")
            break

        if not question:
            continue

        answer = ask(question, history)

        print(f"AI: {answer}")

if __name__ == "__main__":
    main()