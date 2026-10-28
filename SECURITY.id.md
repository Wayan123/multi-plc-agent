# Kebijakan Keamanan

*English (default): [SECURITY.md](SECURITY.md)*

multi-plc-agent mengendalikan software engineering di komputer pengguna sendiri. Proyek ini tidak pernah terhubung ke PLC dengan sendirinya, dan router menahan tool yang online, download, force nilai, atau menghapus isi proyek.

Laporkan kerentanan secara privat lewat GitHub: **Security → Report a vulnerability** di repositori ini (private advisory). Jangan membuka issue publik. Sertakan backend, versi, langkah, dan dampaknya. Kami usahakan menjawab dalam 7 hari.

Termasuk cakupan: cara agar client MCP bisa memanggil tool yang ditahan, menulis di luar path yang diminta, menjalankan perintah sembarang lewat backend, atau membocorkan rahasia. Di luar cakupan: kelemahan software vendor itu sendiri (laporkan ke vendor) dan kebenaran logika PLC yang dihasilkan, yang selalu butuh review manusia.
