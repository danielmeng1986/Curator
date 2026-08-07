# Local configuration

Committed files in this directory are examples and documentation. Local
configuration is created by copying an example without the `.example` suffix:

```text
config/ai.toml.example -> config/ai.toml
tools/web_ui/app_config.example.json -> tools/web_ui/app_config.json
```

The local copies are ignored by Git. They may contain machine-specific paths,
but must not be committed. Device tokens, registration secrets, credentials,
and other secrets are supplied through the local environment or protected
deployment configuration, never through an example file or source code.

The AI example deliberately retains the versioned prompt profile. Only the
runtime executable and model locations are local overrides. MT-004 later moves
that profile to the AI Worker's owned source/configuration boundary.

`tools/web_ui` and `workspace/curator_base_app` are transitional locations.
Their examples preserve the current legacy startup path only until the later
migration tasks relocate the active applications.
