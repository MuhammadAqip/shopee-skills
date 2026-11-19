# Bagaimana skill ini bekerja

## Anatomi satu skill

```
skills/<nama>/
├── SKILL.md              wajib — frontmatter + isi
├── references/           opsional — detail panjang, dimuat hanya saat dirujuk
└── scripts/              opsional — kode yang bisa dijalankan
```

### Frontmatter

```yaml
---
name: shopee-ivs-flow
description: Use when driving Shopee IVS identity verification.
version: 1.0.0
author: ...
license: MIT
metadata:
  hermes:
    tags: [shopee, ivs, verification]
    category: security
---
```

`description` adalah **satu-satunya trigger**. Agent memutuskan memuat atau tidak berdasarkan baris itu saja — bukan dari isi `SKILL.md`, karena isi belum dibaca saat keputusan diambil.

Karena itu deskripsi harus dimulai dengan situasi:

```
✓ "Use when driving Shopee IVS identity verification."
✓ "Use when a Shopee VA order fails. Bank channel matrix."
✗ "Shopee IVS"
✗ "Information about verification"
```

Yang pertama memberi tahu agent **kapan** ia butuh ini. Yang kedua hanya memberi tahu **apa** isinya — dan agent tidak bisa memutuskan "kapan" dari "apa".

### Kenapa `references/` terpisah

`SKILL.md` dimuat penuh setiap kali skill aktif. Isi 915 baris masuk context dan dibayar setiap pemuatan.

Pemisahan yang benar:
- `SKILL.md` — alur, keputusan, jebakan. Yang dibutuhkan **setiap** kali.
- `references/` — tabel panjang, contoh respons, catatan per kasus. Dibaca **hanya saat** bagian tertentu dibutuhkan.

Contoh di `shopee-token-war-stack`: `SKILL.md` memuat state machine dan aturan retry; `references/pln-order-flow.md` memuat transkrip satu alur lengkap. Yang pertama dipakai selalu, yang kedua hanya ketika mengerjakan PLN.

## Cara skill berpasangan

Skill yang baik saling merujuk, bukan saling menduplikasi:

```
shopee-antifraud-reversing
        │  (menghasilkan header yang valid)
        ▼
shopee-account-phone-change ──► shopee-ivs-flow
        │                            │
        │                            ▼
        │                     shopee-captcha-solver
        │                            │
        ▼                            ▼
shopee-sms-otp-bypass      captcha-solver-api-integration
                                     │
                                     ▼
                          solver-api-capability-probing
```

`shopee-account-phone-change` tidak menjelaskan cara membuat `x-sap-sec`; ia merujuk ke `shopee-antifraud-reversing`. `shopee-ivs-flow` tidak menjelaskan payload captcha; ia merujuk ke `shopee-captcha-solver`.

**Aturan:** satu fakta, satu tempat. Kalau fakta yang sama ada di dua skill, salah satunya akan basi dan yang basi akan dipercaya.

## Kapan skill perlu dipecah

Pecah kalau dua bagian punya **trigger berbeda**:

```
✗ "shopee-captcha-and-va"
     trigger: kapan? captcha? VA? keduanya?

✓ shopee-captcha-solver      "Use when a Shopee captcha appears."
✓ shopee-va-digital-order    "Use when extracting Shopee VA numbers."
```

Jangan pecah kalau bagian-bagiannya selalu dipakai bersama. `shopee-antifraud-reversing` mencakup tiga signer (`x-sap-sec`, Sense SDK, `sz-token`) dalam satu skill karena ketiganya dihasilkan dari bundle yang sama dan tidak pernah dipakai terpisah.

## Kapan skill perlu digabung

Gabung kalau dua skill selalu dimuat bersamaan **dan** merujuk satu sama lain di setiap bagian. Itu tanda isinya sebenarnya satu.

## Bagaimana pengetahuan ini diperoleh

Semua skill di sini dibangun dengan pola yang sama:

1. **Ambil bundle.** `pb/`, `ivs_js/`, `sdkjs/` — file JS yang di-load halaman Shopee.
2. **Cari pemanggil.** `grep -rn 'nama/endpoint' bundle/` menemukan fungsi yang memanggilnya.
3. **Baca fungsi pembungkusnya.** `FetchUtils.post(path, body, {headers})` menunjukkan bentuk body dan header yang benar.
4. **Eksekusi dan catat hasilnya.** Yang ditulis di skill adalah hasil yang **terlihat**, bukan yang seharusnya.
5. **Catat jebakan.** Bagian paling berharga dari setiap skill adalah daftar hal yang terlihat benar tapi salah.

Langkah 4 yang paling sering dilewati. Skill yang ditulis dari pembacaan kode saja akan mengklaim "body-nya `{u_token}`" padahal yang benar `{u_token}` **dan** header `x-app-type`. Yang membongkar perbedaan itu hanya eksekusi.

## Cara memverifikasi skill masih akurat

```bash
# ambil skill, jalankan satu endpoint yang disebut di dalamnya
python3 -c "
import sys; sys.path.insert(0,'.')
import changenumfast as c
a = c.Api(open('ck_test.txt').read().strip())
print(a.get('/api/v4/account/basic/get_account_info'))
"
```

Kalau hasilnya cocok dengan yang tertulis di skill, skill masih akurat. Kalau tidak, periksa bundle terbaru sebelum memperbarui skill — mungkin endpoint-nya berubah, mungkin hanya nama field-nya.

## Kesalahan yang paling sering dalam menulis skill

**Menulis apa yang seharusnya, bukan apa yang terjadi.**
"Endpoint membalas daftar channel" — padahal kadang membalas `null` dan channel-nya di field lain. Yang benar: "membalas `available_channels`; kalau `null`, periksa `data.channels`".

**Menghilangkan kondisi.**
"`op 23` bebas captcha" — padahal hanya untuk akun tertentu. Kondisi adalah bagian dari fakta, bukan detail tambahan.

**Menulis terlalu lengkap di `SKILL.md`.**
Setiap baris dibayar setiap pemuatan. Tabel 200 baris di `SKILL.md` seharusnya di `references/`.

**Tidak mencatat kegagalan.**
Bagian "jebakan" biasanya yang paling sering dirujuk ulang. Skill tanpa bagian itu terasa lengkap tapi tidak mencegah pengulangan kesalahan.
