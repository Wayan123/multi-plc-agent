# Contributing / Berkontribusi

[English](#english) · [Bahasa Indonesia](#bahasa-indonesia)

---

## English

Thanks for helping. multi-plc-agent is useful only if it is correct on real engineering software, so every claim of support must come from a run you actually did.

### What helps most

| Contribution | What to include |
| --- | --- |
| New backend for a PLC tool | See [Adding a backend](#adding-a-backend) |
| Verification on another version, CPU or UI language | Tool version, CPU, UI language, the exact tool calls, and the compile/build output |
| Bug report | Steps, expected vs. actual result, backend and tool version. Strip customer data |
| Docs and translations | English and Indonesian are kept in sync in `README.md` and this file |

Open an issue before large work so we can agree on the write path first.

### Ground rules

1. **Only your own work.** Submit code, text and files that you wrote or that are under a license compatible with Apache-2.0, and say where third-party code came from.
2. **No vendor material.** Do not commit vendor manuals, help files, DLLs, installers, sample projects, licence keys or screenshots of licensed content. Short facts are fine: menu names, file-format field names, numeric command IDs, error texts needed to parse results.
3. **Templates.** A project template may only be an empty project that you saved yourself with the vendor tool. State the tool version in the PR.
4. **No customer data.** Test projects must be synthetic.
5. **No reverse engineering that a licence forbids.** If the vendor's terms prohibit decompiling or bypassing a protection, don't. Prefer official APIs (Openness, ScriptEngine, PLCopen XML import, CSV/text import) and public file formats.
6. **No live-PLC writes.** Backends must not download, go online, force I/O or write to a running controller. The router withholds such tools; backends should not expose them.
7. **Safety.** Generated ladder is a draft. Do not describe a backend as suitable for safety functions.

### Developer Certificate of Origin (DCO)

Every commit must be signed off:

```
git commit -s -m "codesys: support TOF"
```

This adds `Signed-off-by: Your Name <you@example.com>` and certifies the [Developer Certificate of Origin 1.1](https://developercertificate.org/): you wrote the change or have the right to submit it under the project's licence. Contributions are accepted under Apache-2.0 (inbound = outbound). You keep your copyright.

### Adding a backend

A backend is a stdio MCP server under `backends/<vendor>/<vendor>_mcp/`. Copy the shape of `backends/outseal` (writes a file) or `backends/codesys` (drives an official scripting API):

- Tools without the vendor prefix; the router adds `<vendor>_`. Minimum: `validate`, a write tool, a compile/build tool that returns error counts, and a read-back used to verify the write.
- Same rung JSON shape as the other backends (`{"comment", "elements": [contacts | {"branch": [...]}, ..., output]}`).
- Writing requires `--allow-write`. Never overwrite a file without an explicit flag; keep a `.bak`.
- Tests in `backends/<vendor>/tests/` that run without the vendor software and check behaviour (validation boundaries, codec round-trip, read-back comparison). Don't test wiring or copy strings.
- Proof in the PR: the conveyor demo spec (start/stop with seal-in, E-stop, 3 s start delay with horn, counter of 10 with reset, batch lamp) written, compiled with 0 errors in the real tool, and read back matching. Paste the outputs.
- Add the backend to `multiplc/config.py` (`VENDOR_DEFAULTS`), `config.example.json`, the support tables in `README.md` (both languages) and `ROADMAP.md`. List the tool only under "Verified on" for what you actually ran.

### Checks before a PR

```
py -3 -m pytest tests backends -q
```

Add only tests that would catch a real bug. One topic per PR.

### Conduct and security

Be respectful; see [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Report security problems privately as described in [SECURITY.md](SECURITY.md), not in a public issue.

---

## Bahasa Indonesia

Terima kasih sudah membantu. multi-plc-agent hanya berguna kalau benar-benar jalan di software engineering aslinya, jadi setiap klaim dukungan harus berasal dari uji coba yang benar-benar Anda jalankan.

### Kontribusi yang paling membantu

| Kontribusi | Yang perlu disertakan |
| --- | --- |
| Backend baru untuk software PLC | Lihat [Menambah backend](#menambah-backend) |
| Verifikasi di versi, CPU, atau bahasa UI lain | Versi software, CPU, bahasa UI, pemanggilan tool persisnya, dan output compile/build |
| Laporan bug | Langkah, hasil yang diharapkan vs. yang terjadi, backend dan versi software. Hapus data pelanggan |
| Dokumentasi dan terjemahan | Bahasa Inggris dan Indonesia dijaga tetap sama di `README.md` dan file ini |

Buka issue dulu sebelum pekerjaan besar, supaya cara menulis ke software vendor disepakati lebih dulu.

### Aturan dasar

1. **Hanya karya sendiri.** Kirim kode, teks, dan file yang Anda tulis sendiri atau yang lisensinya cocok dengan Apache-2.0, dan sebutkan asal kode pihak ketiga.
2. **Tanpa materi vendor.** Jangan commit manual vendor, file help, DLL, installer, contoh proyek, kunci lisensi, atau screenshot konten berlisensi. Fakta singkat boleh: nama menu, nama field format file, ID perintah numerik, teks error yang perlu dibaca.
3. **Template.** Template proyek hanya boleh berupa proyek kosong yang Anda simpan sendiri dengan software vendor. Sebutkan versi software di PR.
4. **Tanpa data pelanggan.** Proyek uji harus buatan sendiri.
5. **Tanpa reverse engineering yang dilarang lisensi.** Kalau ketentuan vendor melarang dekompilasi atau membobol proteksi, jangan dilakukan. Utamakan API resmi (Openness, ScriptEngine, import PLCopen XML, import CSV/teks) dan format file publik.
6. **Tanpa menulis ke PLC yang sedang berjalan.** Backend tidak boleh download, online, force I/O, atau menulis ke controller. Router menahan tool seperti itu; backend sebaiknya tidak menyediakannya.
7. **Keselamatan.** Ladder hasil AI adalah draf. Jangan menyebut backend cocok untuk fungsi safety.

### Developer Certificate of Origin (DCO)

Setiap commit harus diberi sign-off:

```
git commit -s -m "codesys: dukung TOF"
```

Perintah ini menambahkan `Signed-off-by: Nama Anda <anda@contoh.com>` dan menyatakan [Developer Certificate of Origin 1.1](https://developercertificate.org/): Anda menulis perubahan itu atau berhak mengirimkannya di bawah lisensi proyek. Kontribusi diterima di bawah Apache-2.0. Hak cipta tetap milik Anda.

### Menambah backend

Backend adalah server MCP stdio di `backends/<vendor>/<vendor>_mcp/`. Ikuti bentuk `backends/outseal` (menulis file) atau `backends/codesys` (memakai API scripting resmi):

- Nama tool tanpa prefix vendor; router menambahkan `<vendor>_`. Minimal: `validate`, tool tulis, tool compile/build yang mengembalikan jumlah error, dan read-back untuk memverifikasi hasil tulis.
- Bentuk JSON rung sama dengan backend lain (`{"comment", "elements": [kontak | {"branch": [...]}, ..., output]}`).
- Menulis butuh `--allow-write`. Jangan menimpa file tanpa flag eksplisit; simpan `.bak`.
- Test di `backends/<vendor>/tests/` yang jalan tanpa software vendor dan memeriksa perilaku (batas validasi, round-trip codec, perbandingan read-back).
- Bukti di PR: spesifikasi demo conveyor (start/stop dengan seal-in, E-stop, start delay 3 detik dengan horn, counter 10 dengan reset, lampu batch) ditulis, di-compile 0 error di software aslinya, dan read-back cocok. Tempel outputnya.
- Daftarkan backend di `multiplc/config.py` (`VENDOR_DEFAULTS`), `config.example.json`, tabel dukungan di `README.md` (dua bahasa) dan `ROADMAP.md`. Cantumkan di "Verified on" hanya yang benar-benar Anda jalankan.

### Pemeriksaan sebelum PR

```
py -3 -m pytest tests backends -q
```

Tambahkan hanya test yang bisa menangkap bug nyata. Satu topik per PR.

### Etika dan keamanan

Bersikap saling menghormati; lihat [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Laporkan masalah keamanan secara privat sesuai [SECURITY.md](SECURITY.md), bukan lewat issue publik.
