"""Patch mlx-openai-server refine_messages to parse stringified tool_call arguments.

OpenClaw (and other OpenAI API clients) send tool_call.arguments as a JSON string,
but the Qwen3.5 chat template expects a dict. This patch parses the string into a dict
before the template processes it.
"""
import sys

TARGET = "/Users/chanunc/mlx-openai-server-env/lib/python3.12/site-packages/app/handler/mlx_lm.py"

with open(TARGET) as f:
    content = f.read()

# Check if already patched
if "_parse_tool_call_arguments" in content:
    print("Already patched!")
    sys.exit(0)

old = '    def refine_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:\n        """\n        Refine the messages to be more suitable for the model.\n        """\n        if self.message_converter:\n            logger.debug("Message converter is enabled, converting messages")\n            messages = self.message_converter.convert_messages(messages)\n\n        return [{k: v for k, v in message.items() if v is not None} for message in messages]'

new = '''    @staticmethod
    def _parse_tool_call_arguments(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Parse stringified tool_call arguments into dicts.

        OpenAI API clients (e.g. OpenClaw) send tool_call.function.arguments
        as a JSON string, but Qwen3.5 chat templates expect a mapping.
        """
        import json as _json
        for msg in messages:
            tool_calls = msg.get("tool_calls")
            if not tool_calls:
                continue
            for tc in tool_calls:
                fn = tc.get("function") or tc
                args = fn.get("arguments")
                if isinstance(args, str):
                    try:
                        fn["arguments"] = _json.loads(args)
                    except (ValueError, TypeError):
                        pass
        return messages

    def refine_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Refine the messages to be more suitable for the model.
        """
        if self.message_converter:
            logger.debug("Message converter is enabled, converting messages")
            messages = self.message_converter.convert_messages(messages)

        messages = self._parse_tool_call_arguments(messages)
        return [{k: v for k, v in message.items() if v is not None} for message in messages]'''

if old not in content:
    print("ERROR: Could not find the expected code block to patch.")
    print("The server code may have been updated. Manual patching required.")
    sys.exit(1)

content = content.replace(old, new)

with open(TARGET, "w") as f:
    f.write(content)

print("Patched successfully!")
