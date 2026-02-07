---
trigger: always_on
---

1. Economy of Mechanism (Simplicity)

The "One Hop" Limit: Minimize indirection. A reader should not have to jump through more than two files or definitions to find the source of truth for a value.

Lean Interfaces: Components should only ask for the data they strictly need, not the entire environment context.

Constraint: “Is this feature utilizing the standard library/existing constructs? If yes, do not build a custom wrapper.”

2. Building for Modularity

Separation of Concerns: Distinct files/blocks for distinct environments (e.g., prod, stage) and distinct services (e.g., database, frontend).

DRY (Don't Repeat Yourself) via Import: Define common variables in a shared/ or base/ module and import them. Never copy-paste logic; reference it.

Atomic Commits: Structure the config so that adding a feature usually involves adding a file/block, not editing a massive central list.

3. Easy Addition & Maintenance

Self-Documenting Structure: Directory and file names must describe their contents explicitly (e.g., use payment_gateway_config.py instead of utils.py).

Open/Closed Principle: The system should be open for extension (adding new plugins/configs) but closed for modification (not touching the core loader logic).