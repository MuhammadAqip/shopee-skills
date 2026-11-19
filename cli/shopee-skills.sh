#!/usr/bin/env bash
# shopee-skills.sh — entrypoint interaktif paket skill.
#   ./cli/shopee-skills.sh
# Keys: 1-9 pilih · PgUp/PgDn ganti halaman · h bantuan · q keluar
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
SKD="$ROOT/skills"

# shellcheck disable=SC1091
. "$HERE/menu.sh"

title() { printf '\n%s%s%s\n' "$C_B" "$*" "$C_R"; }
hr()    { printf '%s' "$C_D"; printf '%.0s─' $(seq 1 58); printf '%s\n' "$C_R"; }
_p()    { printf '\n%s[enter]%s ' "$C_D" "$C_R"; read -r _ || true; }

_list() { ( cd "$SKD" && ls -d */ 2>/dev/null | sed 's|/||' ); }

_show() {
  local n="$1"
  if [ ! -f "$SKD/$n/SKILL.md" ]; then echo "tidak ada: $n"; _p; return; fi
  title "$n"
  hr
  sed -n '1,90p' "$SKD/$n/SKILL.md"
  echo
  local refs; refs=$(find "$SKD/$n/references" -type f 2>/dev/null | wc -l)
  local scr;  scr=$(find "$SKD/$n/scripts" -type f 2>/dev/null | wc -l)
  printf '%srefs: %s   scripts: %s   total: %s baris%s\n' \
    "$C_D" "$refs" "$scr" "$(wc -l < "$SKD/$n/SKILL.md")" "$C_R"
  _p
}

# ---- handler per skill ----
h_anti()  { _show shopee-antifraud-reversing; }
h_ivs()   { _show shopee-ivs-flow; }
h_cap()   { _show shopee-captcha-solver; }
h_sad()   { _show sadcaptcha-shopee-api; }
h_probe() { _show solver-api-capability-probing; }
h_capi()  { _show captcha-solver-api-integration; }
h_phone() { _show shopee-account-phone-change; }
h_sms()   { _show shopee-sms-otp-bypass; }
h_war()   { _show shopee-token-war-stack; }
h_va()    { _show shopee-va-digital-order; }
h_bank()  { _show shopee-bank-va-channels; }

# ---- utilitas ----
h_list() {
  title "11 skill"
  hr
  printf '%-34s %6s  %s\n' SKILL BARIS REFS
  for d in $(_list); do
    local f="$SKD/$d/SKILL.md"; [ -f "$f" ] || continue
    printf '%-34s %6s  %s\n' "$d" "$(wc -l < "$f")" \
      "$(find "$SKD/$d/references" -type f 2>/dev/null | wc -l)"
  done
  echo
  printf '%s total: %s baris SKILL.md, %s file%s\n' "$C_D" \
    "$(cat "$SKD"/*/SKILL.md 2>/dev/null | wc -l)" \
    "$(find "$SKD" -type f | wc -l)" "$C_R"
  _p
}

h_index() {
  title "INDEX-SKILLS"
  hr
  sed -n '1,90p' "$ROOT/docs/INDEX-SKILLS.md"
  _p
}

h_how() {
  title "HOW-SKILLS-WORK"
  hr
  sed -n '1,90p' "$ROOT/docs/HOW-SKILLS-WORK.md"
  _p
}

h_lessons() {
  title "LESSONS"
  hr
  sed -n '1,90p' "$ROOT/docs/LESSONS.md"
  _p
}

h_agents() {
  title "AGENTS.md"
  hr
  sed -n '1,90p' "$ROOT/AGENTS.md"
  _p
}

h_refs() {
  title "File pendukung"
  hr
  for d in $(_list); do
    local r s
    r=$(find "$SKD/$d/references" -type f 2>/dev/null | sed "s|$SKD/$d/||")
    s=$(find "$SKD/$d/scripts" -type f 2>/dev/null | sed "s|$SKD/$d/||")
    [ -n "$r$s" ] || continue
    printf '%s▸ %s%s\n' "$C_C" "$d" "$C_R"
    [ -n "$r" ] && printf '    refs   : %s\n' "$(echo "$r" | tr '\n' ' ')"
    [ -n "$s" ] && printf '    scripts: %s\n' "$(echo "$s" | tr '\n' ' ')"
  done
  _p
}

h_install() {
  title "Pasang ke Hermes"
  hr
  local dst="${HOME}/.hermes/skills"
  echo "tujuan: $dst"
  echo
  if [ ! -d "$dst" ]; then
    printf '%s%s tidak ada — Hermes belum terpasang?%s\n' "$C_E" "$dst" "$C_R"
    _p; return
  fi
  printf '%sSalin semua skill? [y/N]%s ' "$C_Y" "$C_R"
  local a; IFS= read -rn1 a; echo
  [[ "$a" =~ ^[yY]$ ]] || { echo "dibatalkan"; _p; return; }
  local n=0
  for d in $(_list); do
    rm -rf "$dst/$d"
    cp -r "$SKD/$d" "$dst/$d" && n=$((n+1))
  done
  echo "$n skill dipasang ke $dst"
  _p
}

h_verify() {
  title "Verifikasi frontmatter"
  hr
  local bad=0
  for d in $(_list); do
    local f="$SKD/$d/SKILL.md"
    [ -f "$f" ] || { printf '  %sMISSING%s %s\n' "$C_E" "$C_R" "$d"; bad=$((bad+1)); continue; }
    local nm ds
    nm=$(grep -m1 -oP '^name:\s*\K.*' "$f")
    ds=$(grep -m1 -oP '^description:\s*\K.*' "$f" | sed 's/^"//;s/"$//')
    if [ -z "$nm" ] || [ -z "$ds" ]; then
      printf '  %sBAD%s %s\n' "$C_E" "$C_R" "$d"; bad=$((bad+1))
    elif [[ "$ds" != Use\ when* ]] && [[ "$ds" != Use\ for* ]]; then
      printf '  %sWARN%s %-30s %s\n' "$C_Y" "$C_R" "$d" "${ds:0:36}"
    else
      printf '  %sOK%s   %-30s\n' "$C_G" "$C_R" "$d"
    fi
  done
  echo
  [ "$bad" -eq 0 ] && printf '%ssemua frontmatter valid%s\n' "$C_G" "$C_R" \
                   || printf '%s%s bermasalah%s\n' "$C_E" "$bad" "$C_R"
  _p
}

h_sanitize() {
  title "Sanitasi kredensial"
  hr
  bash "$HERE/sanitize.sh" "$ROOT"
}

h_tree() {
  title "Struktur"
  hr
  ( cd "$ROOT" && find . -maxdepth 2 -not -path './.git*' \
      | sed 's|^\./||' | sort | head -50 )
  echo
  printf '%-8s %s\n' file "$(find "$ROOT" -type f -not -path '*/.git/*' | wc -l)"
  printf '%-8s %s\n' md   "$(find "$ROOT" -name '*.md' -not -path '*/.git/*' | wc -l)"
  printf '%-8s %s\n' size "$(du -sh "$ROOT" | cut -f1)"
  _p
}

h_zip() {
  title "Buat zip"
  local out="/root/$(basename "$ROOT")_$(date +%Y%m%d).zip"
  rm -f "$out"
  ( cd "$(dirname "$ROOT")" && zip -qr -9 "$out" "$(basename "$ROOT")" \
      -x '*/__pycache__/*' -x '*.pyc' -x '*/.git/*' )
  echo "zip  : $out"
  echo "size : $(du -h "$out" | cut -f1)"
  echo "md5  : $(md5sum "$out" | cut -d' ' -f1)"
  _p
}

# ---- MENU -----------------------------------------------------------------
menu_init "SHOPEE SKILLS" "11 skill reverse-engineering Shopee"

menu_page "Reverse"
menu_item 1 "antifraud-reversing"    h_anti
menu_item 2 "ivs-flow"               h_ivs

menu_page "Captcha"
menu_item 1 "captcha-solver"         h_cap
menu_item 2 "sadcaptcha-api"         h_sad
menu_item 3 "capability-probing"     h_probe
menu_item 4 "solver-integration"     h_capi

menu_page "Nomor"
menu_item 1 "account-phone-change"   h_phone
menu_item 2 "sms-otp-bypass"         h_sms

menu_page "Pesanan"
menu_item 1 "token-war-stack"        h_war
menu_item 2 "va-digital-order"       h_va
menu_item 3 "bank-va-channels"       h_bank

menu_page "Dokumen"
menu_item 1 "Daftar skill"           h_list
menu_item 2 "File pendukung"         h_refs
menu_item 3 "INDEX-SKILLS"           h_index
menu_item 4 "HOW-SKILLS-WORK"        h_how
menu_item 5 "LESSONS"                h_lessons
menu_item 6 "AGENTS.md"              h_agents

menu_page "Sistem"
menu_item 1 "Pasang ke Hermes"       h_install
menu_item 2 "Verifikasi frontmatter" h_verify
menu_item 3 "Sanitasi kredensial"    h_sanitize
menu_item 4 "Struktur"               h_tree
menu_item 5 "Buat zip"               h_zip

menu_run
