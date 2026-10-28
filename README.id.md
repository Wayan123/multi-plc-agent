# multi-plc-agent

*English (default): [README.md](README.md)*

Satu server MCP yang membuat agen AI bisa menulis program ladder di banyak software engineering PLC: Mitsubishi GX Works2, Siemens TIA Portal, Omron CX-Programmer dan Sysmac Studio, CODESYS, Schneider Machine Expert - Basic, Delta WPLSoft, Outseal Studio, dan Haiwell Happy.

multi-plc-agent menjalankan satu server MCP per software, memberi setiap tool awalan vendor (`mitsubishi_`, `siemens_`, `omron_`, `sysmac_`, `codesys_`, `schneider_`, `delta_`, `outseal_`, `haiwell_`), lalu menyajikannya sebagai satu server. Setiap backend tetap memakai alur persetujuan dan pemeriksaan keamanannya sendiri. Router menambahkan satu aturan bersama: tool yang bekerja pada PLC yang sedang berjalan atau menghapus isi proyek tidak disajikan. Backend GX Works2, TIA Portal, dan CX-Programmer adalah proyek pihak ketiga; backend lainnya ada di [`backends/`](backends).

Kontribusi sangat diterima: lihat [CONTRIBUTING.md](CONTRIBUTING.md).

## Software yang didukung

| Vendor | Software | Backend | Cara menulis | Diverifikasi di |
| --- | --- | --- | --- | --- |
| Mitsubishi | GX Works2 1.580 dan 1.635 | [Wayan123/gxworks-agent](https://github.com/Wayan123/gxworks-agent) (fork dari [Arienax/gxworks-agent](https://github.com/Arienax/gxworks-agent)) | Mengendalikan UI GX Works2: import CSV program dan komentar device | 1.580.0.1 UI Inggris, FX3U: program dan komentar masuk, Check Program "No error found" |
| Siemens | TIA Portal V20 / V21 | [bulaofen0036-coder/TIA_Portal_Openness_MCP](https://github.com/bulaofen0036-coder/TIA_Portal_Openness_MCP) v2.7.8 | API resmi TIA Openness: LAD sebagai teks S7DCL, timer/counter sebagai SCL external source | V20, S7-1200 1212C: FB + FC + OB1 + tag masuk, compile 0 error / 0 warning |
| Omron | CX-Programmer 9.x, CP1E | [BlackUppsss/Cx-Proggrammer-MCP](https://github.com/BlackUppsss/Cx-Proggrammer-MCP) | Mengedit file proyek `.cxt`/`.cxp` langsung | 9.75, CP1E-NA: proyek terbuka, compile 0 error / 0 warning |
| Omron | Sysmac Studio 1.47 (NX/NJ) | [`backends/sysmac`](backends/sysmac) | Membuat XML IEC 61131-10, mengimpornya lewat Tools > IEC 61131-10 XML > Import dengan UI Automation, build, lalu membaca balik ladder yang tersimpan | 1.47.0.64008, NX1P2-1040DT: 6 rung masuk (program baru dan pengganti), build 0 error / 0 warning, read-back cocok |
| CODESYS | CODESYS V3.5 SP21 | [`backends/codesys`](backends/codesys) | ScriptEngine resmi tanpa jendela (`--noUI --runscript`): proyek baru, import LD PLCopen XML, build, ekspor balik | 3.5.21.0, Control Win V3 x64: 6 rung, "Compile complete -- 0 errors, 0 warnings", logika hasil ekspor cocok |
| Schneider | EcoStruxure Machine Expert - Basic 1.3 (M221) | [`backends/schneider`](backends/schneider) | Menulis rung sebagai IL ke proyek XML `.smbp`, lalu compile di software lewat UI Automation (konversi IL → LD oleh software, opsional) | 1.3.0.215, TM221M16R: 6 rung, status "No error", read-back cocok |
| Delta | WPLSoft 2.52 (DVP-ES2/SS2) | [`backends/delta`](backends/delta) | Menulis word program ke file `.dvp`, lalu menjalankan compile Instruction ⇄ Ladder di WPLSoft dan menyimpan | 2.52, DVP-SS2: 7 rung, 0 error, read-back IL identik |
| Outseal | Outseal Studio 3.6 (board Nano / Mega) | [`backends/outseal`](backends/outseal) | Menulis file proyek `.plc` langsung, lalu menjalankan Test lewat UI Automation | V.3.6 Beta5, Nano V5: 7 rung, Test 0 error, file hex terbentuk; codec round-trip 18 contoh bawaan |
| Haiwell | Haiwell Happy 2.2.13 (seri C/T/N/H) | [`backends/haiwell`](backends/haiwell) | Mengetik rung di editor LD dengan shortcut keyboard, lalu ekspor IL dan membandingkannya dengan IL yang diharapkan | V2.2.13.240603, AT16S0T/P: 7 rung, read-back IL identik, compile 0 error / 0 warning |
| Mitsubishi | GX Works3 | belum ada | Rencana: editor ladder [Edit] → [Import File] CSV | Belum didukung. Di mesin pengembang GX Works3 1.055H crash saat [Project] > [New]; lihat [ROADMAP.md](ROADMAP.md) |

Kolom "Diverifikasi di" hanya berisi yang benar-benar sudah dijalankan. CPU, versi, dan bahasa UI lain mungkin juga jalan, tetapi belum diuji. Software yang direncanakan (Beckhoff TwinCAT, Delta ISPSoft/DIADesigner, Rockwell, Keyence, Inovance, LS, dan lainnya) ada di [ROADMAP.md](ROADMAP.md).

## Demo

Agen menulis spesifikasi conveyor yang sama ke setiap software lewat router ini:

- start/stop dengan E-stop
- horn peringatan 3 detik sebelum motor jalan
- berhenti setelah satu batch berisi 10 produk

Setiap rekaman adalah satu kali jalan tanpa potongan: pemanggilan MCP oleh agen muncul di jendela log, lalu hasilnya dicek di software vendor. GIF diputar 1,5× lebih cepat. Path di mesin pengembang disamarkan. Pratinjau GIF ada di [README bahasa Inggris](README.md#demo). Video MP4 lengkap disimpan di Google Drive, bukan di GitHub: lihat [docs/media.md](docs/media.md). Backend Sysmac, Schneider, dan Delta sudah diverifikasi lewat output tool; rekamannya menyusul.

## Instalasi (Windows)

Pasang setiap backend pihak ketiga yang Anda perlukan sesuai README-nya masing-masing, lalu:

```powershell
git clone https://github.com/Wayan123/multi-plc-agent.git
cd multi-plc-agent
py -3 -m pip install .
copy config.example.json config.json
```

Router tidak butuh paket di luar pustaka standar Python (3.10+). Backend di repo ini yang mengendalikan program desktop butuh Python Windows dengan `pywinauto` dan `pywin32` (`py -3 -m pip install pywinauto pywin32`). Backend CODESYS tidak butuh paket tambahan.

Edit `config.json`, atau isi variabel yang dipakainya:

| Variabel | Menunjuk ke |
| --- | --- |
| `GXWORKS_AGENT_DIR` | checkout gxworks-agent beserta `.venv-mcp` |
| `TIA_MCP_DIR` | folder `TIA_MCP_Delivery_v*` hasil ekstrak |
| `CX_MCP_DIR` | checkout Cx-Proggrammer-MCP beserta `.venv` |
| `CX_PROJECT` | file `.cxt` yang diedit backend CX-Programmer |
| `MULTIPLC_DIR` | checkout repo ini (untuk backend di dalam repo) |
| `GUI_PYTHON` | `python.exe` Windows yang sudah terpasang `pywinauto` dan `pywin32` |

Isi `"enabled": false` untuk backend yang tidak dipakai. Cek bahwa setiap backend bisa berjalan:

```powershell
multi-plc-agent --config config.json --check
```

Perintah ini keluar dengan kode 0 hanya jika semua backend yang aktif berstatus `running`.

## Menghubungkan client MCP

Router bisa menulis konfigurasi untuk client Anda. Satu entri berlaku untuk versi IDE, CLI, dan desktop dari setiap produk: VS Code (GitHub Copilot), GitHub Copilot CLI, OpenAI Codex (CLI, ekstensi IDE, aplikasi desktop), Cursor (IDE dan CLI), Devin (Desktop dan CLI), ZCode, Claude Desktop, Claude Code (CLI dan ekstensi IDE), Google Antigravity (aplikasi, IDE, dan CLI), dan Gemini CLI.

```powershell
multi-plc-agent --config config.json --client list                        # client mana yang terpasang
multi-plc-agent --config config.json --client all --client-write          # daftarkan di semua client yang terpasang, menyimpan .bak
multi-plc-agent --config config.json --client claude-code                 # hanya menampilkan satu entri
multi-plc-agent --config config.json --client cursor --scope project --project C:\work\line1 --client-write
multi-plc-agent --config config.json --client status                      # di mana sudah terdaftar; kode keluar 1 jika entri usang
```

Timeout tool diatur 15 menit pada client yang mendukungnya. File, timeout, dan batasan setiap client ada di [docs/clients.md](docs/clients.md) (bahasa Inggris). Dokumen itu juga menjelaskan mengapa agen cloud tidak bisa dipakai, dan pemeriksaan bulanan bahwa format konfigurasi vendor belum berubah. Untuk client lain, sesuaikan konfigurasi `mcpServers` di [README bahasa Inggris](README.md#connect-an-mcp-client).

Minta agen memanggil `list_plc_backends` lebih dulu. Tool ini mengembalikan status setiap backend, identitas server, jumlah tool yang disajikan, dan tool yang ditahan.

## Yang tidak disajikan

| Backend | Ditahan secara default | Alasan |
| --- | --- | --- |
| Siemens | `DownloadToPlc`, `GoOnline`, `SetWatchTableModifyValue`, semua `Delete*`, `ClearExports`, `EnsureOpennessUserGroup`, `Doctor` | Menulis ke PLC, menghapus, dan mengubah grup user lewat UAC |
| Siemens | Nama yang sama lewat `CallTool` | `CallTool` bisa memanggil tool yang tidak terdaftar, jadi router memeriksa nama di dalamnya |
| Omron CX-Programmer | `delete_rung` | Menghapus |
| Backend di repo ini | (tidak ada yang perlu ditahan) | Tidak punya tool untuk online, download, atau upload |

Untuk membuka tool yang ditahan di satu backend, tambahkan `"allow": ["NamaTool"]`. Untuk menahan tool lain, pakai `"deny"`.

## Catatan per backend

- **GX Works2.** Compile native dan sesi live ST/FBD tetap butuh 1.635.0.1. Di 1.580 hanya import/ekspor CSV ladder yang aktif. Simpan proyek di GX Works2 sendiri, karena tool tidak menyimpan proyek tanpa nama. Dukungan 1.580 ada di fork; upstream fokus ke pengeditan file `.gxw` langsung ([Arienax/gxworks-agent#11](https://github.com/Arienax/gxworks-agent/pull/11)).
- **TIA Portal.** Masukkan user Windows Anda ke grup `Siemens TIA Openness` sendiri, lalu login ulang sebelum pertama kali dijalankan. Kalau tidak, server mencoba lewat UAC dan berhenti jika gagal. TIA Portal menanyakan izin Openness setiap kali terhubung, kecuali Anda memilih "Yes to all".
- **CX-Programmer.** Backend mengedit satu file proyek yang ditentukan `--project`. Tutup proyek di CX-Programmer sebelum agen commit. Jika sedang terbuka, tutup **tanpa menyimpan** lalu buka lagi. Backend ditulis untuk CP1E; pemeriksaan alamat dan instruksinya belum mencakup CP1L, CP1H, CJ, atau CS.
- **Sysmac Studio.** Backend menjalankan Sysmac dengan `-elevate`, supaya Sysmac tetap di sesi user biasa dan bisa diotomasi (kalau dibuka biasa, Sysmac memulai ulang dirinya sebagai Administrator dan tidak bisa diotomasi lagi). Program ditulis ke proyek yang sedang terbuka, atau dibuatkan proyek NX1P2 jika belum ada. Read-back membaca listing ladder yang disimpan Sysmac (diamati di 1.47). Mapping I/O ke variabel dilakukan sendiri. Sekitar 1 menit per penulisan.
- **CODESYS.** CODESYS dijalankan tanpa jendela dengan profile yang terpasang (`--profile`, default `CODESYS V3.5 SP21`). Setiap penulisan membuat `.project` baru (file lama hanya diganti dengan `overwrite=true`, dengan cadangan `.bak`). Variabel berupa variabel IEC bernama, opsional dengan alamat `%IX`/`%QX`. Sekitar 30 detik per penulisan. CODESYS 3.5 SP22+ juga punya add-on MCP Server resmi berlisensi; backend ini tidak membutuhkannya.
- **Machine Expert - Basic.** Mengganti semua rung di POU pertama file `.smbp`. Template bawaan hanya TM221M16R; untuk M221 lain, simpan proyek kosong dari software lalu berikan path-nya. `compile` sekitar 1 menit (2,5 menit dengan `to_ladder`).
- **WPLSoft.** Mengganti seluruh program di file `.dvp` dan menambahkan komentar device; komentar rung (segment) belum ditulis. Template bawaan hanya DVP-SS2. Menu diklik berdasarkan posisi di dalam jendela WPLSoft, jadi versi atau bahasa UI lain mungkin perlu penyesuaian.
- **Outseal Studio.** `outseal_write_project` menulis file tanpa GUI; `outseal_compile` membukanya di Outseal Studio lalu menekan Test. Alamat dicek terhadap jumlah I/O board. Backend tidak pernah upload ke board.
- **Haiwell Happy.** Tidak ada fitur import ladder, jadi `haiwell_write_ladder` mengetik langsung di editor. Jangan memakai keyboard atau mouse selama proses berjalan (sekitar 2 menit untuk 7 rung); proses berhenti jika jendela lain mengambil fokus. Blok program pertama diganti dan cadangan `.bak` disimpan. Didukung: kontak NO/NC, branch paralel (cabang pertama satu kontak, tanpa bertingkat), satu output per rung: OUT, SET, RST, TON (basis 1 detik), CTU. Template bawaan hanya AT16S0T/P; untuk CPU lain buat proyek di Haiwell Happy lalu berikan path-nya.

Backend yang mengendalikan program desktop menjalankan satu panggilan dalam satu waktu. Jangan menjalankan dua backend GUI bersamaan di desktop yang sama.

## Keselamatan

Program ladder hasil AI adalah draf. Review dan uji di simulator (GX Simulator2, PLCSIM, CX-Simulator, CODESYS Control Win, simulator M221, simulator offline Haiwell Happy) sebelum dipakai di mesin. Emergency stop, pengaman (guarding), two-hand control, dan proteksi beban lebih harus ditangani perangkat safety terpisah, bukan oleh logika buatan AI.

## Pengembangan

```powershell
py -3 -m pip install pytest
py -3 -m pytest tests backends -q
```

Test router menjalankan backend stdio tiruan. Test backend memeriksa format file, validasi, pembuatan kode, dan perbandingan read-back. Tidak ada yang membutuhkan software PLC.

## Berkontribusi

Backend baru, verifikasi di versi lain, dan terjemahan sangat diterima. Baca [CONTRIBUTING.md](CONTRIBUTING.md) lebih dulu: commit harus diberi sign-off DCO (`git commit -s`), dan manual vendor, DLL, contoh proyek, serta data pelanggan tidak boleh di-commit. Laporkan masalah keamanan secara privat ([SECURITY.md](SECURITY.md)).

## Lisensi

Apache-2.0, lihat [LICENSE](LICENSE). Backend GX Works2, TIA Portal, dan CX-Programmer adalah proyek terpisah dengan lisensinya sendiri, lihat [NOTICE](NOTICE); repo ini tidak menyertakan atau mendistribusikan kodenya. Backend di `backends/` adalah bagian dari repo ini dan memakai lisensinya. Template bawaan adalah proyek kosong yang disimpan kontributor, dengan teks preset vendor dihapus. Nama produk vendor adalah merek dagang pemiliknya; proyek ini tidak berafiliasi dengan vendor mana pun, dan Anda butuh instalasi berlisensi sendiri untuk setiap software.
