# <implementation-name>

One capability implementation, copied from `implementation-template/`.
Replace this README's body with the implementation's documentation: what it
does, its tradeoffs (size/speed/performance), how it compares to sibling
implementations of the same capability, and anything the installer needs
to know that isn't a declaration fact.

- **Capability:** `<capability>` (declared in the parent service's
  `service.toml`)
- **Declaration:** `implementation.toml` (ADR-0031 §3/§4) — validated by the
  service template's `contract/declaration/load_implementation_toml`
- **Install recipe:** `install/` (the installer contract is the lifecycle
  spec's concern, #65)

See the parent service's `CONTRIBUTING.md` for the contribution ritual and
the inherited contract rules (ADR-0001).