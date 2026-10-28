# Security Policy / Kebijakan Keamanan

## English

multi-plc-agent drives engineering software on the user's own workstation. It never connects to a PLC by itself, and the router withholds tools that go online, download, force values or delete project content.

Report a vulnerability privately through GitHub: **Security → Report a vulnerability** on this repository (private advisory). Do not open a public issue. Include the backend, versions, steps and impact. We aim to answer within 7 days.

In scope: a way for an MCP client to reach a withheld tool, write outside the requested path, run arbitrary commands through a backend, or leak secrets. Out of scope: weaknesses in the vendor software itself (report those to the vendor) and the correctness of generated PLC logic, which always needs human review.

## Bahasa Indonesia

multi-plc-agent mengendalikan software engineering di komputer pengguna sendiri. Proyek ini tidak pernah terhubung ke PLC dengan sendirinya, dan router menahan tool yang online, download, force nilai, atau menghapus isi proyek.

Laporkan kerentanan secara privat lewat GitHub: **Security → Report a vulnerability** di repositori ini (private advisory). Jangan membuka issue publik. Sertakan backend, versi, langkah, dan dampaknya. Kami usahakan menjawab dalam 7 hari.

Termasuk cakupan: cara agar client MCP bisa memanggil tool yang ditahan, menulis di luar path yang diminta, menjalankan perintah sembarang lewat backend, atau membocorkan rahasia. Di luar cakupan: kelemahan software vendor itu sendiri (laporkan ke vendor) dan kebenaran logika PLC yang dihasilkan, yang selalu butuh review manusia.
