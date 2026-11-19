# Lessons — dari membangun dan memakai skill ini

## Skill yang tidak pernah dimuat sama dengan skill yang tidak ada

Skill ditulis 500 baris, lengkap, akurat. Tidak pernah terpakai sekali pun. Penyebabnya satu baris di frontmatter:

```yaml
description: Shopee IVS verification
```

Agent memutuskan memuat skill dari deskripsi saja. "Shopee IVS verification" tidak menyebut **kapan** skill itu dibutuhkan, jadi agent tidak pernah merasa butuh. Yang bekerja:

```yaml
description: Use when driving Shopee IVS identity verification.
```

Pelajarannya bukan "tulis deskripsi yang bagus" tapi **deskripsi adalah API, bukan label**. Ia dipanggil oleh keputusan, dan keputusan butuh kondisi.

## `SKILL.md` adalah anggaran, bukan arsip

Setiap baris dimuat penuh setiap kali skill aktif. Skill 900 baris berarti 900 baris di context setiap pemuatan.

Yang terjadi kalau diabaikan: skill besar mulai jarang dimuat karena agent menganggapnya "terlalu berat", lalu pengetahuan di dalamnya hilang meski filenya ada.

Pemisahan yang bekerja: alur dan keputusan di `SKILL.md`, tabel dan transkrip di `references/`. `shopee-token-war-stack` memakai pola ini — state machine di depan, transkrip alur PLN di `references/`.

## Satu fakta di dua tempat berarti satu akan basi

`operation: 23` tercatat sebagai operation change-phone di dua skill. Setelah ditemukan bahwa alur sebenarnya memakai `0`, hanya satu yang diperbarui. Yang lain tetap mengajarkan 23.

Yang memperburuk: yang basi terlihat sama percaya dirinya dengan yang benar. Tidak ada cara membedakan dari isinya.

**Aturan:** kalau sebuah fakta dibutuhkan dua skill, taruh di satu tempat dan rujuk dari yang lain. Duplikasi bukan redundansi yang aman; duplikasi adalah dua versi yang menunggu untuk bercabang.

## Jebakan lebih berharga daripada prosedur

Bagian "jebakan" di setiap skill adalah yang paling sering dirujuk ulang. Prosedur bisa dibaca sekali dan diingat. Jebakan tidak — karena jebakan terlihat benar sampai gagal.

Contoh nyata: `header anti-fraud palsu membuat semua akun dibalas 90309999`. Fakta ini tidak bisa disimpulkan dari membaca dokumentasi endpoint mana pun. Ia hanya bisa ditemukan dengan menjalankan dua implementasi dan membandingkannya.

**Aturan:** setiap kali menghabiskan lebih dari satu jam mengejar bug, tambahkan satu baris ke bagian jebakan skill yang relevan. Biayanya satu menit; yang dihemat adalah satu jam di sesi berikutnya.

## Endpoint bergerak, pola tidak

Endpoint Shopee berubah. Nama field berubah. Enum bertambah. Yang bertahan adalah pola:

```
cari pemanggil di bundle → baca pembungkusnya → tiru body dan header → eksekusi → catat hasil
```

Skill yang menuliskan pola ini bertahan lebih lama daripada skill yang hanya mendaftar endpoint. Yang pertama mengajari cara menemukan ulang; yang kedua harus diperbarui setiap kali Shopee mengubah apa pun.

## Menyalin nilai tanpa memverifikasi menyebarkan kesalahan

`operation: 23` masuk ke skill karena terbaca sebagai "AccountChangePhone" di enum. Namanya cocok, nilainya masuk akal, tidak ada yang mencurigakan.

Yang membongkar: mengirim 23 dan mendapat `23500158`, lalu mengirim 0 dan mendapat `0`. Enum benar; asumsinya yang salah — nilai yang dipakai alur bukan nilai yang namanya paling cocok.

**Aturan:** enum memberi tahu nilai yang **ada**. Hanya eksekusi yang memberi tahu nilai yang **dipakai**.

## Skill yang terlalu luas tidak pernah termuat

"shopee-otomasi" — mencakup captcha, IVS, VA, OTP, signer. Trigger-nya harus mencakup semua itu sekaligus, dan trigger yang mencakup segalanya tidak memicu apa pun.

Dipecah menjadi 11 skill, masing-masing dengan satu kondisi pemicu. Hasilnya: masing-masing termuat tepat ketika dibutuhkan, dan hanya bagian yang relevan yang masuk context.

## Scrub kredensial bisa merusak dokumen

Regex `\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{2,5}\b` dimaksudkan untuk menghapus IP proxy. Yang juga terhapus: contoh placeholder `IP:PORT` di dokumentasi, dan format `socks4://host:port` yang berubah menjadi `socks://REDACTED` — menghilangkan tanda kurung penutup dan merusak kalimat.

**Aturan:** setelah scrub otomatis, baca ulang file yang berubah. Scrub yang berlebihan menghasilkan dokumentasi yang secara teknis bersih tapi tidak bisa dipahami.

## Yang paling cepat membongkar: membandingkan dengan yang berhasil

Tiga kali dalam proyek ini, jalan keluar datang dari membandingkan implementasi yang gagal dengan yang berhasil — bukan dari menambah hipotesis atau membaca dokumentasi.

Simpan skrip yang berhasil. Jangan hapus setelah selesai. Itu referensi termurah yang akan kamu punya ketika ada yang rusak enam bulan kemudian.
