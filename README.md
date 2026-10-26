# SnapDiff 🔍

**Mini App Harian — 26 Oktober 2026** · Python 3.10+ · CLI · Tanpa dependensi runtime

SnapDiff membantu mengetahui file apa saja yang **ditambah, dihapus, atau diubah** di sebuah folder sejak pemeriksaan terakhir. Berguna untuk audit perubahan folder proyek, verifikasi backup, dan pengecekan hasil proses otomatis. Perubahan isi file dideteksi dengan **SHA-256**, bukan hanya nama atau waktu modifikasi.

## Fitur

- Membuat snapshot JSON berisi path relatif, ukuran, dan hash SHA-256 setiap file.
- Membandingkan kondisi folder terbaru dengan snapshot lama.
- Mendeteksi file **baru (+)**, **terhapus (-)**, **diubah (~)**, dan **tidak berubah**.
- Mengecualikan folder developer umum (`.git`, `.venv`, `node_modules`, dll.) serta pola `--exclude` tambahan.
- Menghasilkan laporan teks atau JSON; `--fail-on-change` mengembalikan exit code 1 jika ada perubahan.
- Tidak mengikuti symbolic link, sehingga tidak memindai file di luar folder target.

## Persyaratan

Python **3.10 atau lebih baru**. Tidak perlu instalasi paket pihak ketiga untuk menjalankan aplikasi.

## Instalasi

```bash
cd snapdiff-2026-10-26
python -m pip install -e .
```

Ekstrak arsip proyek terlebih dahulu, lalu buka terminal di folder proyek. Setelah instalasi, gunakan perintah `snapdiff`. Alternatif tanpa instalasi: jalankan `python -m snapdiff` dari folder proyek.

## Cara menjalankan

### 1. Simpan kondisi awal folder

```bash
python -m snapdiff snapshot ./contoh-folder -o ./snapshot.json
```

### 2. Bandingkan dengan kondisi terbaru

```bash
python -m snapdiff compare ./snapshot.json ./contoh-folder
```

Contoh keluaran:

```text
SnapDiff — Hasil Perbandingan
Ditambah: 1 | Dihapus: 1 | Diubah: 1 | Tetap: 2
+ assets/logo.svg
- docs/old.txt
~ src/main.py
```

### 3. Laporan JSON atau simpan ke file

```bash
python -m snapdiff compare ./snapshot.json ./contoh-folder --format json
python -m snapdiff compare ./snapshot.json ./contoh-folder -o ./hasil.txt
```

### 4. Abaikan file tertentu

```bash
python -m snapdiff snapshot ./contoh-folder -o ./snapshot.json --exclude "*.log" --exclude "build"
```

Pola yang dipilih ketika membuat snapshot otomatis dipakai kembali saat membandingkan.

### 5. Gunakan pada CI atau skrip

```bash
python -m snapdiff compare ./snapshot.json ./contoh-folder --fail-on-change
```

**Exit code:** `0` = sukses (atau tidak ada perubahan jika memakai `--fail-on-change`), `1` = ada perubahan saat `--fail-on-change`, `2` = error.

## Struktur proyek

```text
snapdiff-2026-10-26/
├── snapdiff/
│   ├── __init__.py
│   ├── __main__.py
│   └── core.py
├── tests/
│   └── test_snapdiff.py
├── .github/workflows/tests.yml
├── pyproject.toml
├── .gitignore
├── LICENSE
└── README.md
```

## Menjalankan pengujian

```bash
python -m unittest discover -s tests -v
```

Pengujian meliputi file baru/hilang/berubah (termasuk isi berubah dengan ukuran sama), path Unicode, pengecualian file, symlink, snapshot di dalam folder target, validasi JSON, exit code CLI, dan penulisan laporan.

## Catatan dan batasan

- Snapshot berisi **metadata**, bukan backup isi file. SnapDiff tidak memulihkan file.
- File yang sedang ditulis saat pemindaian dapat memicu error; jalankan ulang ketika folder stabil.
- Snapshot tidak ditandatangani secara kriptografis; jangan menganggapnya bukti anti-manipulasi.
- Hashing membaca seluruh isi file, sehingga folder besar membutuhkan waktu lebih lama.
- Hanya file biasa yang dipindai; folder kosong dan symbolic link tidak dicatat.

## Lisensi

MIT — lihat `LICENSE`.
