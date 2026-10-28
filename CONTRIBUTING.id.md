# Berkontribusi

*English (default): [CONTRIBUTING.md](CONTRIBUTING.md)*

Terima kasih sudah membantu. multi-plc-agent hanya berguna kalau benar-benar jalan di software engineering aslinya, jadi setiap klaim dukungan harus berasal dari uji coba yang benar-benar Anda jalankan.

## Kontribusi yang paling membantu

| Kontribusi | Yang perlu disertakan |
| --- | --- |
| Backend baru untuk software PLC | Lihat [Menambah backend](#menambah-backend) |
| Verifikasi di versi, CPU, atau bahasa UI lain | Versi software, CPU, bahasa UI, pemanggilan tool persisnya, dan output compile/build |
| Laporan bug | Langkah, hasil yang diharapkan vs. yang terjadi, backend dan versi software. Hapus data pelanggan |
| Dokumentasi dan terjemahan | Bahasa Inggris adalah bahasa utama (`README.md`, `CONTRIBUTING.md`). Terjemahan ada di file `*.id.md` dan boleh tertinggal; jika berbeda, versi Inggris yang berlaku |

Buka issue dulu sebelum pekerjaan besar, supaya cara menulis ke software vendor disepakati lebih dulu.

## Aturan dasar

1. **Hanya karya sendiri.** Kirim kode, teks, dan file yang Anda tulis sendiri atau yang lisensinya cocok dengan Apache-2.0, dan sebutkan asal kode pihak ketiga.
2. **Tanpa materi vendor.** Jangan commit manual vendor, file help, DLL, installer, contoh proyek, kunci lisensi, atau screenshot konten berlisensi. Fakta singkat boleh: nama menu, nama field format file, ID perintah numerik, teks error yang perlu dibaca.
3. **Template.** Template proyek hanya boleh berupa proyek kosong yang Anda simpan sendiri dengan software vendor. Sebutkan versi software di PR.
4. **Tanpa data pelanggan.** Proyek uji harus buatan sendiri.
5. **Tanpa reverse engineering yang dilarang lisensi.** Kalau ketentuan vendor melarang dekompilasi atau membobol proteksi, jangan dilakukan. Utamakan API resmi (Openness, ScriptEngine, import PLCopen XML, import CSV/teks) dan format file publik.
6. **Tanpa menulis ke PLC yang sedang berjalan.** Backend tidak boleh download, online, force I/O, atau menulis ke controller. Router menahan tool seperti itu; backend sebaiknya tidak menyediakannya.
7. **Keselamatan.** Ladder hasil AI adalah draf. Jangan menyebut backend cocok untuk fungsi safety.

## Developer Certificate of Origin (DCO)

Setiap commit harus diberi sign-off:

```
git commit -s -m "codesys: dukung TOF"
```

Perintah ini menambahkan `Signed-off-by: Nama Anda <anda@contoh.com>` dan menyatakan [Developer Certificate of Origin 1.1](https://developercertificate.org/): Anda menulis perubahan itu atau berhak mengirimkannya di bawah lisensi proyek. Kontribusi diterima di bawah Apache-2.0. Hak cipta tetap milik Anda.

## Menambah backend

Backend adalah server MCP stdio di `backends/<vendor>/<vendor>_mcp/`. Ikuti bentuk `backends/outseal` (menulis file) atau `backends/codesys` (memakai API scripting resmi):

- Nama tool tanpa prefix vendor; router menambahkan `<vendor>_`. Minimal: `validate`, tool tulis, tool compile/build yang mengembalikan jumlah error, dan read-back untuk memverifikasi hasil tulis.
- Bentuk JSON rung sama dengan backend lain (`{"comment", "elements": [kontak | {"branch": [...]}, ..., output]}`).
- Menulis butuh `--allow-write`. Jangan menimpa file tanpa flag eksplisit; simpan `.bak`.
- Test di `backends/<vendor>/tests/` yang jalan tanpa software vendor dan memeriksa perilaku (batas validasi, round-trip codec, perbandingan read-back).
- Bukti di PR: spesifikasi demo conveyor (start/stop dengan seal-in, E-stop, start delay 3 detik dengan horn, counter 10 dengan reset, lampu batch) ditulis, di-compile 0 error di software aslinya, dan read-back cocok. Tempel outputnya.
- Daftarkan backend di `multiplc/config.py` (`VENDOR_DEFAULTS`), `config.example.json`, tabel dukungan di `README.md` (dan `README.id.md` jika bisa) dan `ROADMAP.md`. Cantumkan di "Verified on" hanya yang benar-benar Anda jalankan.

## Pemeriksaan sebelum PR

```
py -3 -m pytest tests backends -q
```

Tambahkan hanya test yang bisa menangkap bug nyata. Satu topik per PR.

## Etika dan keamanan

Bersikap saling menghormati; lihat [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Laporkan masalah keamanan secara privat sesuai [SECURITY.md](SECURITY.md), bukan lewat issue publik.
