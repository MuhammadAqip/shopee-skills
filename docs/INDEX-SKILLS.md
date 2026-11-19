# INDEX — peta 11 skill

## Berdasarkan tugas

### Reverse engineering

| Situasi | Skill | Mulai dari |
|---|---|---|
| Request ditolak `31600000` | `shopee-antifraud-reversing` | bagian "x-sap-sec" |
| Perlu membaca bundle yang di-load dinamis | `shopee-antifraud-reversing` | `references/local-mirror-recipe.md` |
| Perlu tahu endpoint mana yang dipanggil halaman tertentu | `shopee-antifraud-reversing` | `references/` — peta modul |

### Verifikasi identitas (IVS)

| Situasi | Skill | Mulai dari |
|---|---|---|
| Akun minta selfie/KTP | `shopee-ivs-flow` | alur `ivs/methods` → select → verify |
| Perlu daftar method IVS | `shopee-ivs-flow` | tabel enum `type` |
| `verify_password` dibalas `10002` | `shopee-ivs-flow` | bagian body |
| Perlu `ivs_signature` | `shopee-ivs-flow` | `token/verify` |

### Captcha

| Situasi | Skill | Mulai dari |
|---|---|---|
| Captcha muncul di alur | `shopee-captcha-solver` | tiga tipe captcha |
| Perlu tahu payload SadCaptcha | `sadcaptcha-shopee-api` | kontrak API |
| Tidak tahu method mana yang hidup | `solver-api-capability-probing` | probing |
| Integrasi solver ke Playwright | `captcha-solver-api-integration` | lifecycle |

### Nomor telepon

| Situasi | Skill | Mulai dari |
|---|---|---|
| Ganti nomor akun | `shopee-account-phone-change` | op 23 vs op 18 |
| Daftar akun baru lewat SMS | `shopee-sms-otp-bypass` | alur registrasi |
| Nomor ditolak `23500158` | `shopee-account-phone-change` | counter anti-abuse |

### Pesanan produk digital

| Situasi | Skill | Mulai dari |
|---|---|---|
| Orkestrasi pesanan lengkap | `shopee-token-war-stack` | state machine |
| VA tidak keluar | `shopee-bank-va-channels` | matriks channel |
| Ekstraksi nomor VA | `shopee-va-digital-order` | parser |

## Berdasarkan kode error

| Kode | Arti | Skill |
|---|---|---|
| `31600000` | butuh header x-sap | `shopee-antifraud-reversing` |
| `10002` | param kurang / route salah | `shopee-ivs-flow`, `shopee-account-phone-change` |
| `211` | event IVS tidak valid | `shopee-ivs-flow` |
| `49900000` | nama field salah (`u_token` vs `ivs_utoken`) | `shopee-ivs-flow` |
| `23500101` | butuh captcha saat send | `shopee-captcha-solver` |
| `23500158` | counter anti-abuse per akun | `shopee-account-phone-change` |
| `90309999` | anti-crawler — **bukan** indikator akun untuk endpoint ringan | `shopee-antifraud-reversing` |
| `12301116` | akun/nomor di-restrict | `shopee-account-phone-change` |

## Urutan baca yang disarankan

**Kalau baru mulai:**
1. `shopee-antifraud-reversing` — pahami dulu bagaimana request ditandatangani
2. `shopee-account-phone-change` — alur paling sederhana yang memakai signer itu

**Kalau mengerjakan IVS:**
1. `shopee-ivs-flow` (915 baris, paling lengkap)
2. `shopee-captcha-solver` — kalau muncul captcha di tengah alur

**Kalau mengerjakan pesanan:**
1. `shopee-token-war-stack`
2. `shopee-va-digital-order`
3. `shopee-bank-va-channels` — kalau VA gagal

## Statistik

```
11 skill
4.500+ baris SKILL.md + references
4 script Python yang bisa dijalankan langsung
```

Skill terbesar: `shopee-ivs-flow` (915 baris) — alur IVS punya enam langkah dengan percabangan per method.
Skill terkecil: `shopee-sms-otp-bypass` (89 baris) — alurnya pendek dan tidak punya percabangan.
