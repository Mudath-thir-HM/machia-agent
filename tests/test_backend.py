"""Quick sanity check that LocalLlamaServer can talk to the running server."""
from machia import LocalLlamaServer, Message

def main():
    backend = LocalLlamaServer()

    tools = [{
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Get the current time in a specific timezone",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone": {"type": "string", "description": "e.g. Africa/Lagos"}
                },
                "required": ["timezone"],
            },
        },
    }]

    messages = [
        Message(role="system", content="You are a helpful assistant."),
        Message(role="user", content="What time is it in Lagos right now?"),
    ]

    print("Calling N-ATLAS via LocalLlamaServer...")
    resp = backend.chat(messages, tools=tools, max_tokens=150)

    print("\n--- Response ---")
    print(f"Content: {resp.content!r}")
    print(f"Tool calls: {len(resp.tool_calls)}")
    if resp.tool_calls:
        tc = resp.tool_calls[0]
        print(f"  name: {tc['function']['name']}")
        print(f"  args (raw string): {tc['function']['arguments']!r}")
        # This is the crucial step your agent will do:
        import json
        args = json.loads(tc["function"]["arguments"])
        print(f"  args (parsed dict): {args}")
    print(f"Tokens: prompt={resp.prompt_tokens} completion={resp.completion_tokens}")


if __name__ == "__main__":
    main()