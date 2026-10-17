"""Pure Vim grammar engine: no Textual, so it can be unit-tested.

The widget feeds it one key at a time together with the current text and cursor index;
it answers with edits (index ranges on the *current* text), a new cursor, a mode change, and
register/yank info. Supported:

  counts           3dd  2w  d2w  5x  10G
  operators        d c y > <   (dd cc yy >> <<, d{motion}, d{text-object}, visual d/c/y/>/<)
  motions          h l 0 ^ $ w W b B e E j k gg G { } f t F T ; ,
  text objects     iw aw iW aW  i" a" i' a' i` a`  i( a( ib ab  i[ a[  i{ a{ iB aB  i< a<
  commands         x X D C Y s S p P J ~ r{c} i a I A o O u v V n N  g- g+  (visual: o x s)
Not implemented: `.` repeat, macros, marks, named registers, % and search motions.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

INDENT = "    "
VISUAL_MODES = ("VISUAL", "V-LINE")


@dataclass
class Edit:
    start: int
    end: int
    text: str


@dataclass
class Result:
    handled: bool = True
    edits: List[Edit] = field(default_factory=list)
    cursor: Optional[int] = None      # index into the text AFTER edits
    mode: Optional[str] = None
    yank: Optional[Tuple[str, bool, bool]] = None  # (text, linewise, copy_to_system_clipboard)
    selection: Optional[Tuple[int, int]] = None    # visual (anchor, cursor) indices
    external: Optional[str] = None                 # undo | earlier | later | search_next | search_prev


@dataclass
class Motion:
    target: int
    linewise: bool = False
    inclusive: bool = False


# ---------------------------------------------------------------------------
# text helpers
# ---------------------------------------------------------------------------

def apply_edits(text: str, edits: List[Edit]) -> str:
    for e in sorted(edits, key=lambda e: e.start, reverse=True):
        text = text[: e.start] + e.text + text[e.end:]
    return text


def _line_start(s: str, i: int) -> int:
    return s.rfind("\n", 0, i) + 1


def _line_end(s: str, i: int) -> int:
    j = s.find("\n", i)
    return len(s) if j == -1 else j


def _first_nonblank(s: str, ls: int) -> int:
    j = ls
    while j < len(s) and s[j] in " \t":
        j += 1
    return j


def _clamp_normal(s: str, i: int) -> int:
    """NORMAL-mode cursors sit ON a character (never past the end of a non-empty line)."""
    i = max(0, min(i, len(s)))
    ls, le = _line_start(s, i), _line_end(s, i)
    return le - 1 if (i >= le and le > ls) else i


def _starts(s: str) -> List[int]:
    out = [0]
    for k, ch in enumerate(s):
        if ch == "\n":
            out.append(k + 1)
    return out


def _vertical(s: str, i: int, delta: int) -> Tuple[int, int]:
    starts = _starts(s)
    row = s.count("\n", 0, i)
    col = i - starts[row]
    nr = max(0, min(len(starts) - 1, row + delta))
    ls = starts[nr]
    le = _line_end(s, ls)
    return min(ls + col, max(ls, le - 1)), nr


def _cls(c: str, big: bool = False) -> int:
    if c.isspace():
        return 0
    if big:
        return 1
    return 1 if (c.isalnum() or c == "_") else 2


# ---------------------------------------------------------------------------
# motions
# ---------------------------------------------------------------------------

def motion_w(s: str, i: int, n: int = 1, big: bool = False) -> int:
    L = len(s)
    for _ in range(n):
        if i >= L:
            break
        c = _cls(s[i], big)
        if c:
            while i < L and _cls(s[i], big) == c:
                i += 1
        while i < L and _cls(s[i], big) == 0:
            if s[i] == "\n" and i > 0 and s[i - 1] == "\n":
                break  # an empty line counts as a word
            i += 1
    return i


def motion_e(s: str, i: int, n: int = 1, big: bool = False) -> int:
    L = len(s)
    for _ in range(n):
        if i < L - 1:
            i += 1
        while i < L and _cls(s[i], big) == 0:
            i += 1
        if i >= L:
            return L - 1
        c = _cls(s[i], big)
        while i + 1 < L and _cls(s[i + 1], big) == c:
            i += 1
    return i


def motion_b(s: str, i: int, n: int = 1, big: bool = False) -> int:
    for _ in range(n):
        if i <= 0:
            break
        i -= 1
        while i > 0 and _cls(s[i], big) == 0 and not (s[i] == "\n" and s[i - 1] == "\n"):
            i -= 1
        c = _cls(s[i], big)
        if c:
            while i > 0 and _cls(s[i - 1], big) == c:
                i -= 1
    return i


def _word_end_here(s: str, i: int, n: int, big: bool) -> int:
    """End of the current word (stays put if already on its last char); then n-1 more `e`s."""
    c = _cls(s[i], big)
    while i + 1 < len(s) and _cls(s[i + 1], big) == c:
        i += 1
    return motion_e(s, i, n - 1, big) if n > 1 else i


def find_motion(s: str, i: int, kind: str, ch: str, n: int) -> Optional[Motion]:
    ls, le = _line_start(s, i), _line_end(s, i)
    pos = i
    if kind in "ft":
        for _ in range(n):
            pos = s.find(ch, pos + 1, le)
            if pos == -1:
                return None
        return Motion(pos if kind == "f" else pos - 1, inclusive=True)
    for _ in range(n):
        pos = s.rfind(ch, ls, pos)
        if pos == -1:
            return None
    return Motion(pos if kind == "F" else pos + 1)


def resolve_motion(s: str, i: int, key: str, n: int, has_count: bool) -> Optional[Motion]:
    ls, le = _line_start(s, i), _line_end(s, i)
    big = key in ("W", "B", "E")
    if key == "h":
        return Motion(max(ls, i - n))
    if key in ("l", " "):
        return Motion(min(le, i + n))
    if key == "0":
        return Motion(ls)
    if key == "^":
        return Motion(_first_nonblank(s, ls))
    if key == "$":
        starts = _starts(s)
        row = min(s.count("\n", 0, i) + n - 1, len(starts) - 1)
        rs = starts[row]
        return Motion(max(rs, _line_end(s, rs) - 1), inclusive=True)
    if key in ("w", "W"):
        return Motion(motion_w(s, i, n, big))
    if key in ("b", "B"):
        return Motion(motion_b(s, i, n, big))
    if key in ("e", "E"):
        return Motion(motion_e(s, i, n, big), inclusive=True)
    if key in ("j", "k"):
        t, _ = _vertical(s, i, n if key == "j" else -n)
        if s.count("\n", 0, t) == s.count("\n", 0, i):
            return None
        return Motion(t, linewise=True)
    if key in ("G", "gg"):
        starts = _starts(s)
        row = (n - 1) if has_count else (len(starts) - 1 if key == "G" else 0)
        row = max(0, min(row, len(starts) - 1))
        return Motion(_first_nonblank(s, starts[row]), linewise=True)
    if key in ("}", "{"):
        step, t = (1, i) if key == "}" else (-1, i)
        starts = _starts(s)
        row = s.count("\n", 0, i)
        for _ in range(n):
            row += step
            while 0 <= row < len(starts) and s[starts[row]: _line_end(s, starts[row])].strip():
                row += step
            row = max(0, min(row, len(starts) - 1))
        return Motion(starts[row])
    return None


# ---------------------------------------------------------------------------
# text objects (return [a, b) or None)
# ---------------------------------------------------------------------------

def obj_word(s: str, i: int, around: bool, big: bool = False) -> Optional[Tuple[int, int]]:
    ls, le = _line_start(s, i), _line_end(s, i)
    if i >= le:
        return None
    c = _cls(s[i], big)
    a = i
    while a > ls and _cls(s[a - 1], big) == c:
        a -= 1
    b = i + 1
    while b < le and _cls(s[b], big) == c:
        b += 1
    if around:
        if c != 0:
            e = b
            while e < le and s[e] in " \t":
                e += 1
            if e > b:
                b = e
            else:
                while a > ls and s[a - 1] in " \t":
                    a -= 1
        elif b < le:
            c2 = _cls(s[b], big)
            while b < le and _cls(s[b], big) == c2:
                b += 1
    return a, b


def obj_quote(s: str, i: int, q: str, around: bool) -> Optional[Tuple[int, int]]:
    ls, le = _line_start(s, i), _line_end(s, i)
    pos = [k for k in range(ls, le) if s[k] == q and (k == ls or s[k - 1] != "\\")]
    pairs = list(zip(pos[0::2], pos[1::2]))
    for a, b in pairs:
        if a <= i <= b:
            return (a, b + 1) if around else (a + 1, b)
    for a, b in pairs:  # cursor before a pair: use the next one on the line
        if a > i:
            return (a, b + 1) if around else (a + 1, b)
    return None


_PAIRS = {"(": ("(", ")"), ")": ("(", ")"), "b": ("(", ")"), "[": ("[", "]"), "]": ("[", "]"),
          "{": ("{", "}"), "}": ("{", "}"), "B": ("{", "}"), "<": ("<", ">"), ">": ("<", ">")}


def obj_pair(s: str, i: int, o: str, c: str, around: bool) -> Optional[Tuple[int, int]]:
    L = len(s)
    a = None
    if i < L and s[i] == o:
        a = i
    else:
        depth = 0
        for k in range(i - 1, -1, -1):
            if s[k] == c:
                depth += 1
            elif s[k] == o:
                if depth == 0:
                    a = k
                    break
                depth -= 1
    if a is None:
        return None
    depth = 0
    for k in range(a + 1, L):
        if s[k] == o:
            depth += 1
        elif s[k] == c:
            if depth == 0:
                return (a, k + 1) if around else (a + 1, k)
            depth -= 1
    return None


def text_object(s: str, i: int, around: bool, key: str) -> Optional[Tuple[int, int]]:
    if key in ("w", "W"):
        return obj_word(s, i, around, key == "W")
    if key in "\"'`":
        return obj_quote(s, i, key, around)
    if key in _PAIRS:
        o, c = _PAIRS[key]
        return obj_pair(s, i, o, c, around)
    return None


# ---------------------------------------------------------------------------
# engine
# ---------------------------------------------------------------------------

class VimEngine:
    def __init__(self) -> None:
        self.mode = "NORMAL"  # NORMAL | INSERT | VISUAL | V-LINE
        self.register: Tuple[str, bool] = ("", False)
        self.last_find: Optional[Tuple[str, str]] = None
        self.vis_anchor = 0
        self._reset()

    def _reset(self) -> None:
        self.count = ""
        self.op: Optional[str] = None
        self.op_count = ""
        self.prefix: Optional[str] = None

    @property
    def pending(self) -> str:
        return f"{self.count}{self.op or ''}{self.op_count}{self.prefix or ''}"

    def _n(self) -> int:
        return int(self.count or 1) * int(self.op_count or 1)

    def enter_normal(self) -> None:
        self.mode = "NORMAL"
        self._reset()

    # --- main entry ------------------------------------------------------

    def feed(self, key: str, text: str, cur: int) -> Result:
        if self.mode == "INSERT":
            return Result(handled=False)
        cur = _clamp_normal(text, cur)
        r = self._dispatch(key, text, cur)
        if r.mode is not None:
            self.mode = r.mode
        return r

    def _dispatch(self, key: str, text: str, cur: int) -> Result:
        visual = self.mode in VISUAL_MODES

        if key == "<Esc>":
            had = bool(self.pending) or visual
            self._reset()
            if visual:
                return Result(mode="NORMAL", cursor=cur)
            return Result(handled=had)

        if self.prefix:
            return self._feed_prefix(key, text, cur, visual)

        if key.isdigit() and len(key) == 1 and (key != "0" or (self.op_count if self.op else self.count)):
            if self.op:
                self.op_count += key
            else:
                self.count += key
            return Result()

        if visual and key == "x":
            key = "d"
        elif visual and key == "s":
            key = "c"
        if key in ("d", "c", "y", "<", ">"):
            return self._feed_operator(key, text, cur, visual)

        if key in ("g", "f", "t", "F", "T", "r") or (key in ("i", "a") and (self.op or visual)):
            if key == "r" and visual:
                self._reset()
                return Result()
            self.prefix = key
            return Result()

        if key in (";", ","):
            if not self.last_find:
                self._reset()
                return Result()
            kind, ch = self.last_find
            if key == ",":
                kind = kind.swapcase()
            mt = find_motion(text, cur, kind, ch, self._n())
            return self._apply_motion(mt, text, cur, visual, key)

        if key in "hl 0^$wWbBeEjkG{}" and len(key) == 1:
            mt = resolve_motion(text, cur, key, self._n(), bool(self.count or self.op_count))
            return self._apply_motion(mt, text, cur, visual, key)

        if visual:
            return self._visual_command(key, text, cur)
        return self._command(key, text, cur)

    # --- motions & ranges --------------------------------------------------

    def _apply_motion(self, m: Optional[Motion], text: str, cur: int, visual: bool, key: str) -> Result:
        n = self._n()
        op = self.op
        if m is None:
            self._reset()
            return Result()
        if op:
            if op == "c" and key in ("w", "W") and cur < len(text) and not text[cur].isspace():
                m = Motion(_word_end_here(text, cur, n, key == "W"), inclusive=True)
            if key in ("w", "W") and m.target > _line_end(text, cur):
                m = Motion(_line_end(text, cur))  # dw on the last word of a line never joins lines
            a, b, lw = self._range(text, cur, m)
            self._reset()
            return self._do_op(op, a, b, lw, text, cur)
        self._reset()
        if visual:
            t = max(0, min(m.target, max(0, len(text) - 1)))
            return Result(cursor=t, selection=(self.vis_anchor, t))
        return Result(cursor=_clamp_normal(text, m.target))

    @staticmethod
    def _range(text: str, cur: int, m: Motion) -> Tuple[int, int, bool]:
        if m.linewise:
            return _line_start(text, min(cur, m.target)), _line_end(text, max(cur, m.target)), True
        a, b = sorted((cur, m.target))
        if m.inclusive and b < len(text) and text[b] != "\n":
            b += 1
        return a, b, False

    def _visual_range(self, text: str, cur: int) -> Tuple[int, int, bool]:
        lo, hi = sorted((self.vis_anchor, cur))
        if self.mode == "V-LINE":
            return _line_start(text, lo), _line_end(text, hi), True
        return lo, min(hi + 1, len(text)), False

    # --- operators ----------------------------------------------------------

    def _feed_operator(self, key: str, text: str, cur: int, visual: bool) -> Result:
        if visual:
            a, b, lw = self._visual_range(text, cur)
            self._reset()
            r = self._do_op(key, a, b, lw, text, cur)
            if r.mode is None:
                r.mode = "NORMAL"
            return r
        if self.op is None:
            self.op = key
            return Result()
        if self.op == key:  # dd cc yy >> <<
            n = self._n()
            t, _ = _vertical(text, cur, n - 1)
            a, b = _line_start(text, cur), _line_end(text, t)
            op = self.op
            self._reset()
            return self._do_op(op, a, b, True, text, cur)
        self._reset()
        return Result()

    def _do_op(self, op: str, a: int, b: int, lw: bool, text: str, cur: int) -> Result:
        seg = text[a:b]
        reg = (seg + "\n", True) if lw else (seg, False)
        if op == "y":
            self.register = reg
            keep = cur if (lw and a <= cur) else a
            return Result(yank=(reg[0], lw, True), cursor=_clamp_normal(text, keep), mode="NORMAL" if self.mode in VISUAL_MODES else None)
        if op in ("<", ">"):
            starts = [a] + [k + 1 for k in range(a, b) if text[k] == "\n"]
            edits = []
            for s0 in starts:
                if op == ">":
                    if s0 < len(text) and text[s0] != "\n":
                        edits.append(Edit(s0, s0, INDENT))
                else:
                    m = 0
                    while m < 4 and s0 + m < len(text) and text[s0 + m] == " ":
                        m += 1
                    if m == 0 and s0 < len(text) and text[s0] == "\t":
                        m = 1
                    if m:
                        edits.append(Edit(s0, s0 + m, ""))
            new = apply_edits(text, edits)
            return Result(edits=edits, cursor=_first_nonblank(new, a), mode="NORMAL")

        self.register = reg
        yank = (reg[0], lw, False)
        if op == "d":
            if lw:
                if b < len(text):
                    edits = [Edit(a, b + 1, "")]
                elif a > 0:
                    edits = [Edit(a - 1, b, "")]
                else:
                    edits = [Edit(a, b, "")]
                new = apply_edits(text, edits)
                ls = _line_start(new, min(a, len(new))) if (b < len(text)) else _line_start(new, len(new))
                return Result(edits=edits, cursor=_first_nonblank(new, ls), yank=yank, mode="NORMAL")
            new = text[:a] + text[b:]
            return Result(edits=[Edit(a, b, "")], cursor=_clamp_normal(new, a), yank=yank, mode="NORMAL")
        if op == "c":
            if lw:
                ind = text[a:_first_nonblank(text, a)]
                return Result(edits=[Edit(a, b, ind)], cursor=a + len(ind), yank=yank, mode="INSERT")
            return Result(edits=[Edit(a, b, "")], cursor=a, yank=yank, mode="INSERT")
        return Result()

    # --- prefixes (g, f/t/F/T, r, text objects) -------------------------------

    def _feed_prefix(self, key: str, text: str, cur: int, visual: bool) -> Result:
        p, self.prefix = self.prefix, None
        n = self._n()
        has_count = bool(self.count or self.op_count)
        if len(key) != 1:
            self._reset()
            return Result()
        if p == "r":
            le = _line_end(text, cur)
            self._reset()
            if cur + n > le:
                return Result()
            return Result(edits=[Edit(cur, cur + n, key * n)], cursor=cur + n - 1)
        if p in ("f", "t", "F", "T"):
            self.last_find = (p, key)
            return self._apply_motion(find_motion(text, cur, p, key, n), text, cur, visual, p)
        if p == "g":
            if key == "g":
                return self._apply_motion(resolve_motion(text, cur, "gg", n, has_count), text, cur, visual, "gg")
            self._reset()
            if key in "-+":
                return Result(external="earlier" if key == "-" else "later")
            return Result()
        if p in ("i", "a"):
            obj = text_object(text, cur, p == "a", key)
            op = self.op
            self._reset()
            if obj is None or obj[1] <= obj[0]:
                return Result()
            a, b = obj
            if visual:
                self.vis_anchor = a
                return Result(cursor=b - 1, selection=(a, b - 1))
            return self._do_op(op, a, b, False, text, cur)
        self._reset()
        return Result()

    # --- visual-only and normal-mode commands ----------------------------------

    def _visual_command(self, key: str, text: str, cur: int) -> Result:
        self._reset()
        if key == "o":
            self.vis_anchor, cur = cur, self.vis_anchor
            return Result(cursor=cur, selection=(self.vis_anchor, cur))
        if key == "v":
            return Result(mode="NORMAL", cursor=cur) if self.mode == "VISUAL" else Result(mode="VISUAL", selection=(self.vis_anchor, cur))
        if key == "V":
            return Result(mode="NORMAL", cursor=cur) if self.mode == "V-LINE" else Result(mode="V-LINE", selection=(self.vis_anchor, cur))
        return Result()

    def _command(self, key: str, text: str, cur: int) -> Result:
        n = self._n()
        self._reset()  # any stray operator is cancelled by a non-motion key
        ls, le = _line_start(text, cur), _line_end(text, cur)

        if key == "x":
            return self._do_op("d", cur, min(le, cur + n), False, text, cur) if le > cur else Result()
        if key == "X":
            return self._do_op("d", max(ls, cur - n), cur, False, text, cur) if cur > ls else Result()
        if key == "D":
            return self._do_op("d", cur, le, False, text, cur)
        if key == "C":
            return self._do_op("c", cur, le, False, text, cur)
        if key == "Y":
            t, _ = _vertical(text, cur, n - 1)
            return self._do_op("y", ls, _line_end(text, t), True, text, cur)
        if key == "s":
            return self._do_op("c", cur, min(le, cur + n), False, text, cur)
        if key == "S":
            t, _ = _vertical(text, cur, n - 1)
            return self._do_op("c", ls, _line_end(text, t), True, text, cur)

        if key in ("p", "P"):
            body, lw = self.register
            if not body:
                return Result()
            if lw:
                chunk = body.rstrip("\n")
                if key == "p":
                    ins = ("\n" + chunk) * n
                    new = apply_edits(text, [Edit(le, le, ins)])
                    return Result(edits=[Edit(le, le, ins)], cursor=_first_nonblank(new, le + 1))
                ins = (chunk + "\n") * n
                new = apply_edits(text, [Edit(ls, ls, ins)])
                return Result(edits=[Edit(ls, ls, ins)], cursor=_first_nonblank(new, ls))
            ins = body * n
            pos = cur + 1 if (key == "p" and le > ls) else cur
            return Result(edits=[Edit(pos, pos, ins)], cursor=pos + len(ins) - 1)

        if key == "J":
            starts = _starts(text)
            row = text.count("\n", 0, cur)
            last = min(len(starts) - 1, row + max(2, n) - 1)
            if last <= row:
                return Result()
            end = _line_end(text, starts[last])
            joined, last_piece = "", ""
            for r in range(row + 1, last + 1):
                piece = text[starts[r]: _line_end(text, starts[r])].strip()
                if piece:
                    joined += " " + piece
                    last_piece = piece
            if text[le - 1: le] in (" ", "\t"):
                joined = joined.lstrip(" ")
            # Vim leaves the cursor on the last join point
            pos = le + max(0, len(joined) - len(last_piece) - 1) if last_piece else le
            return Result(edits=[Edit(le, end, joined)], cursor=pos)
        if key == "~":
            k = min(le, cur + n)
            if k <= cur:
                return Result()
            return Result(edits=[Edit(cur, k, text[cur:k].swapcase())], cursor=_clamp_normal(text, k))

        if key == "i":
            return Result(mode="INSERT", cursor=cur)
        if key == "a":
            return Result(mode="INSERT", cursor=cur + 1 if le > ls else cur)
        if key == "I":
            return Result(mode="INSERT", cursor=_first_nonblank(text, ls))
        if key == "A":
            return Result(mode="INSERT", cursor=le)
        ind = text[ls:_first_nonblank(text, ls)]
        if key == "o":
            return Result(edits=[Edit(le, le, "\n" + ind)], cursor=le + 1 + len(ind), mode="INSERT")
        if key == "O":
            return Result(edits=[Edit(ls, ls, ind + "\n")], cursor=ls + len(ind), mode="INSERT")

        if key == "u":
            return Result(external="undo")
        if key == "n":
            return Result(external="search_next")
        if key == "N":
            return Result(external="search_prev")
        if key in ("v", "V"):
            self.vis_anchor = cur
            return Result(mode="VISUAL" if key == "v" else "V-LINE", selection=(cur, cur))
        return Result()  # unknown key: swallow so nothing is typed in NORMAL mode
