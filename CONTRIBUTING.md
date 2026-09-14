# Contributing

Use an isolated build and test state. Keep patches focused, preserve existing user data, and include a regression test for behaviour changes. Never commit recordings, conversations, credentials, contacts, model weights or diagnostic exports.

Run relevant Python tests and avatar Node tests. Changes to prompts must also be checked against actual model outputs: a shorter prompt is not automatically a better assistant. Do not bypass the confirmation or repeated-action guards to make a demo pass.

When reporting an issue, include Jinx version, distribution, desktop, selected model and a redacted error. Avoid uploading complete journal exports or private workspace screenshots.
