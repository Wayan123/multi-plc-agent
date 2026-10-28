# Security Policy

*Bahasa Indonesia: [SECURITY.id.md](SECURITY.id.md)*


multi-plc-agent drives engineering software on the user's own workstation. It never connects to a PLC by itself, and the router withholds tools that go online, download, force values or delete project content.

Report a vulnerability privately through GitHub: **Security → Report a vulnerability** on this repository (private advisory). Do not open a public issue. Include the backend, versions, steps and impact. We aim to answer within 7 days.

In scope: a way for an MCP client to reach a withheld tool, write outside the requested path, run arbitrary commands through a backend, or leak secrets. Out of scope: weaknesses in the vendor software itself (report those to the vendor) and the correctness of generated PLC logic, which always needs human review.
