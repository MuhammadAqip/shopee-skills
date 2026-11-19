# AGENTS.md — konteks untuk AI agent

Kamu bekerja dengan 11 skill Hermes yang memetakan Shopee. Baca ini sebelum menyentuh apa pun.

## Apa yang ada di sini

Setiap folder di `skills/` adalah satu skill Hermes: `SKILL.md` + opsional `references/` dan `scripts/`. `SKILL.md` punya frontmatter YAML (`name`, `description`) dan isi markdown. Deskripsi di frontmatter adalah satu-satunya trigger — kalau deskripsinya tidak menyebut situasi yang sedang dihadapi, skill itu tidak akan dimuat.

## Aturan yang tidak boleh dilanggar

**1. Jangan mengarang endpoint.** Kalau kamu butuh endpoint yang tidak ada di skill, cari di bundle. Bundle adalah sumber kebenaran; skill hanyalah catatan tentang bundle itu. Menambahkan endpoint hasil tebakan ke skill membuat skill itu berbohong, dan kebohongan itu menyebar ke setiap sesi berikutnya yang memuatnya.

**2. Jangan menyalin nilai enum tanpa memverifikasi.** `operation: 23` adalah AccountChangePhone di enum, tapi alur change-phone yang sebenarnya memakai `operation: 0`. Contoh ini ada di `shopee-account-phone-change` justru karena sudah pernah salah.

**3. Deskripsi frontmatter harus diawali "Use when …".** Itu konvensi yang membuat skill bisa ditemukan. Deskripsi yang berbunyi "Shopee IVS" tidak akan pernah termuat; "Use when driving Shopee IVS identity verification" akan.

**4. Jangan menaruh kredensial, bahkan yang sudah mati.** Cookie kedaluwarsa tetap mengungkap ID akun dan pola pemakaian. Kalau perlu contoh, pakai `REDACTED` atau placeholder.

**5. Satu skill, satu tugas.** Kalau sebuah skill mulai mencakup dua hal yang berbeda (misalnya "captcha dan VA"), itu dua skill. Batas yang kabur membuat trigger jadi kabur, dan skill yang triggernya kabur tidak pernah dipakai.

## Peta cepat — tugas ke skill

| Tugas | Skill |
|---|---|
| Request ditolak `31600000` (butuh x-sap) | `shopee-antifraud-reversing` |
| Akun minta selfie/KTP | `shopee-ivs-flow` |
| Captcha muncul | `shopee-captcha-solver` → `sadcaptcha-shopee-api` |
| Cari tahu method captcha mana yang hidup | `solver-api-capability-probing` |
| Ganti nomor akun | `shopee-account-phone-change` |
| Daftar akun baru via SMS | `shopee-sms-otp-bypass` |
| Pesanan produk digital | `shopee-token-war-stack` → `shopee-va-digital-order` |
| VA order gagal / tidak keluar | `shopee-bank-va-channels` |
| Integrasi solver ke browser | `captcha-solver-api-integration` |

## Cara memodifikasi skill

```bash
# 1. baca dulu, jangan menulis buta
cat skills/<nama>/SKILL.md

# 2. kalau menambah catatan, taruh di references/ bukan di SKILL.md
#    SKILL.md dimuat setiap kali skill aktif; references/ hanya saat dibutuhkan

# 3. verifikasi frontmatter masih valid
head -8 skills/<nama>/SKILL.md
```

`SKILL.md` harus tetap ringkas — itu yang dibayar setiap pemuatan. Detail panjang masuk `references/`, kode yang bisa dijalankan masuk `scripts/`.

## Jebakan yang sudah dibayar mahal

- **`x-sap-sec` tidak bisa dikarang.** Nilai acak membuat semua akun dibalas `90309999` — dan itu terlihat seperti akun diblok. Kalau tidak bisa menghitungnya, jangan kirim headernya sama sekali.
- **`get_settings_v2` punya counter.** Setiap panggilan menaikkan counter anti-abuse per akun. Memanggilnya untuk "cek status" akan mengunci akun yang sehat.
- **`90309999` di `order_list` bukan indikator.** Endpoint itu membalas `90309999` untuk hampir semua request web-PC. Menganggapnya flag menghasilkan false positive di setiap akun.
- **`ivs/methods` butuh `event: 2`, bukan string.** `"AccountChangePhone"` dibalas `211`.
- **Method IVS yang muncul hanya yang dimiliki akun.** Akun tanpa password Shopee tidak akan pernah menawarkan `PASSWORD`, sekuat apa pun kamu mencari.
- **`u_token`, bukan `ivs_utoken`.** Nama field di body berbeda dari nama field di response `init_v2`. Salah nama → `49900000`.
