# OPERO decision and data notes

## Decision, reasoning, and how it decides

OPERO uses the user's request and the active tool descriptions to determine which action is relevant, then routes developer requests through the native Brahma Dev loop with a legacy project-generation fallback if that loop raises an error. The developer loop sends the request and tool observations to Gemini when a configured API key is available, parses requested tool calls, executes them, and returns the model's final response; it does not use a deterministic policy engine to independently verify the model's reasoning.

## Data source, input, and data used

The developer agent receives the user's task text and workspace path, and reads or changes project files only through its workspace tools; command output and file contents returned by those tools are added to the conversation history. Its model credentials are read from the local `config/api_keys.json` file, and configured workspace settings may be read from `config/app_settings.json`; these local files should not be committed or shared.

## Limitation, constraint, and known issue

The agent requires a reachable configured model service and may return an inference error when Gemini or the configured fallback is unavailable or rate-limited. Workspace tools are not a security sandbox: shell commands can affect the workspace and the machine under the current user's permissions, while tool output truncation and the finite turn limit can prevent complete inspection or verification.
