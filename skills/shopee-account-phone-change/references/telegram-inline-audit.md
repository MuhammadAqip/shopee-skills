# Auditing inline buttons in a telebot bot — three gates

A copy-ready procedure for the "button does nothing" class of bug. Verified shape:
audit registration, then branch coverage, then live invocation. Skipping gate 3 is
how a passing static audit ships a dead button.

## Gate 1 — registration

Every `callback_data` literal must be matched by at least one handler predicate.

```python
import re
SRC = open("bot.py", encoding="utf-8").read()

static = [m.group(1) for m in re.finditer(r'callback_data\s*=\s*"([^"]+)"', SRC)
          if "{" not in m.group(1)]

exact, prefix = set(), set()
for m in re.finditer(r'callback_query_handler\([^)]*?c\.data\s*==\s*"([^"]+)"', SRC):
    exact.add(m.group(1))
for m in re.finditer(r'callback_query_handler\([^)]*?c\.data\s*in\s*\(([^)]+)\)', SRC):
    exact.update(re.findall(r'"([^"]+)"', m.group(1)))
for m in re.finditer(r'callback_query_handler\([^)]*?c\.data\.startswith\("([^"]+)"\)', SRC):
    prefix.add(m.group(1))

dead = [cb for cb in static
        if cb not in exact and not any(cb.startswith(p) for p in prefix)]
```

Dynamic prefixes need the literal segment before the first `{`:
`callback_data=f"adc_a:{uid}:{n}"` → prefix `adc_a:`.

## Gate 2 — branch coverage

Gate 1 only proves *some* handler receives the callback. The callback string is
usually sliced (`act = c.data[4:]`) and must then hit an `if` inside that handler.

Dispatcher routing styles seen in real bots — the parser must model all of them or
it produces false "dead button" reports:

| style | source shape | how the parser resolves it |
|---|---|---|
| literal | `if act == "cred":` | match tail after prefix |
| membership | `if act in ("list", "home"):` | collect all literals |
| prefix | `if d.startswith("ch:"):` | prefix match |
| delegation | `chg_cb(c, uid, d)` | parse branches inside `chg_cb` |
| slicing | `val = c.data[7:]` then `if val == "manual"`, else `int(val)` | accept literal or any digit |
| numeric | `amount = int(c.data.split("_")[1])` | validate the number exists in the package/pricing dict |

Bound the handler body by searching for the next `\n@bot.` decorator — this is what
stops one dispatcher's `if act ==` lines from being credited to another.

## Gate 3 — live invocation

Static analysis cannot see a branch that runs but produces no UI change. Stub the
bot and count side effects.

```python
class Msg:  chat = type("C", (), {"id": CHAT_ID})();  message_id = 1
class User: id = ADMIN_ID
class Cb:
    id = "cb"
    def __init__(self, data):
        self.data, self.from_user, self.message = data, User(), Msg()

class BotStub:
    def __init__(self): self.calls = []
    def answer_callback_query(self, *a, **k): self.calls.append("answer")
    def edit_message_text(self, *a, **k): self.calls.append("edit"); return True
    def send_message(self, *a, **k): self.calls.append("send"); return Msg()
    def delete_message(self, *a, **k): return True

bot = BotStub()
for data, handler in CASES:
    bot.calls.clear()
    try:
        handler(Cb(data))
    except Exception as e:
        print("CRASH", data, type(e).__name__, e)
        continue
    if not {"edit", "send", "reply"} & set(bot.calls):
        print("NO RESPONSE", data)
```

Monkeypatch the module-level `bot` before importing the handlers, or the real
Telegram client sends actual messages during the test.

## Ordering pitfall

Text features that consume free-form input (a cookie paste, a custom amount) must
be routed by an early handler with a narrow `step` predicate, registered **before**
any generic parser (phone-number detector, admin input reader). Registration order
is dispatch order in telebot: the first matching handler wins and the rest never
run, which presents as a silent bot rather than an error.

## Resetting test residue

A live-invocation test that touches a real SQLite/JSON store leaves rows behind
(extra balance, extra log entries). Zero those fields and drop the test log before
restarting the service, or the first user-visible screen shows inflated numbers.
