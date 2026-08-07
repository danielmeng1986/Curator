# Local configuration

Committed files in this directory are examples and documentation. Local
configuration is created by copying an example without the `.example` suffix:

```text
config/ai.toml.example -> config/ai.toml
config/backend.example.json -> config/backend.json
```

The local copies are ignored by Git. They may contain machine-specific paths,
but must not be committed. Device tokens, registration secrets, credentials,
and other secrets are supplied through the local environment or protected
deployment configuration, never through an example file or source code.

The AI example retains the versioned prompt profile. Only the runtime
executable and model locations are local overrides.
