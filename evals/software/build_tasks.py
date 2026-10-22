"""Source of truth for the software eval set.

Each task has visible examples (shown to the model, and usable by the
controller as a check) and hidden tests (used only for grading). Every test is
a Python expression that must be True. The build runs each reference solution
against all of its tests in the sandbox and refuses to write tasks.jsonl if any
fail, so a broken test can't silently mark correct code wrong.

    .venv/bin/python evals/software/build_tasks.py

Levels:
    calm      one transformation, a loop or a comprehension
    alert     one standard algorithm or careful parsing rule set
    intensive data-structure design, search, dynamic programming, or a parser
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from plm_software.sandbox import run_tests  # noqa: E402

TASKS = []


def task(tid, level, entry, prompt, examples, tests, reference):
    TASKS.append({"id": tid, "level": level, "entry": entry, "prompt": prompt,
                  "examples": examples, "tests": tests, "reference": reference.strip() + "\n"})


# ---------------- calm ----------------
task("sw-c01", "calm", "count_vowels",
     "Write a function `count_vowels(s: str) -> int` that returns how many vowels (a, e, i, o, u, in any case) are in `s`.",
     ["count_vowels('hello') == 2", "count_vowels('') == 0"],
     ["count_vowels('AEIOU') == 5", "count_vowels('rhythm') == 0", "count_vowels('Programming Language') == 7",
      "count_vowels('aaa bbb') == 3"],
     """
def count_vowels(s):
    return sum(c in "aeiou" for c in s.lower())
""")
task("sw-c02", "calm", "reverse_words",
     "Write a function `reverse_words(s: str) -> str` that returns the words of `s` in reverse order, separated by single spaces. Words are separated by any amount of whitespace; leading and trailing whitespace is dropped.",
     ["reverse_words('hello world') == 'world hello'", "reverse_words('one') == 'one'"],
     ["reverse_words('  a  b   c ') == 'c b a'", "reverse_words('') == ''", "reverse_words('the quick brown fox') == 'fox brown quick the'"],
     """
def reverse_words(s):
    return " ".join(reversed(s.split()))
""")
task("sw-c03", "calm", "is_palindrome",
     "Write a function `is_palindrome(s: str) -> bool` that returns True if `s` reads the same forwards and backwards, ignoring case and every character that is not a letter or digit.",
     ["is_palindrome('A man, a plan, a canal: Panama') is True", "is_palindrome('hello') is False"],
     ["is_palindrome('') is True", "is_palindrome('No lemon, no melon') is True", "is_palindrome('ab') is False",
      "is_palindrome('12321') is True", "is_palindrome('race a car') is False"],
     """
def is_palindrome(s):
    t = [c.lower() for c in s if c.isalnum()]
    return t == t[::-1]
""")
task("sw-c04", "calm", "sum_of_evens",
     "Write a function `sum_of_evens(nums: list[int]) -> int` that returns the sum of the even numbers in `nums`.",
     ["sum_of_evens([1, 2, 3, 4]) == 6", "sum_of_evens([]) == 0"],
     ["sum_of_evens([1, 3, 5]) == 0", "sum_of_evens([-2, -3, 4]) == 2", "sum_of_evens([0, 10]) == 10"],
     """
def sum_of_evens(nums):
    return sum(n for n in nums if n % 2 == 0)
""")
task("sw-c05", "calm", "celsius_to_fahrenheit",
     "Write a function `celsius_to_fahrenheit(c: float) -> float` that converts a temperature from Celsius to Fahrenheit.",
     ["celsius_to_fahrenheit(0) == 32", "celsius_to_fahrenheit(100) == 212"],
     ["abs(celsius_to_fahrenheit(-40) - (-40)) < 1e-9", "abs(celsius_to_fahrenheit(37) - 98.6) < 1e-9",
      "abs(celsius_to_fahrenheit(21.5) - 70.7) < 1e-9"],
     """
def celsius_to_fahrenheit(c):
    return c * 9 / 5 + 32
""")
task("sw-c06", "calm", "dedupe",
     "Write a function `dedupe(items: list) -> list` that returns the items with duplicates removed, keeping the first occurrence of each and the original order.",
     ["dedupe([1, 2, 1, 3, 2]) == [1, 2, 3]", "dedupe([]) == []"],
     ["dedupe(['b', 'a', 'b', 'c', 'a']) == ['b', 'a', 'c']", "dedupe([5, 5, 5]) == [5]", "dedupe([3, 1, 2]) == [3, 1, 2]"],
     """
def dedupe(items):
    seen, out = set(), []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out
""")
task("sw-c07", "calm", "fizzbuzz",
     "Write a function `fizzbuzz(n: int) -> list[str]` that returns the strings for 1..n: 'Fizz' for multiples of 3, 'Buzz' for multiples of 5, 'FizzBuzz' for multiples of both, otherwise the number as a string.",
     ["fizzbuzz(3) == ['1', '2', 'Fizz']", "fizzbuzz(0) == []"],
     ["fizzbuzz(15)[-1] == 'FizzBuzz'", "fizzbuzz(5) == ['1', '2', 'Fizz', '4', 'Buzz']", "len(fizzbuzz(100)) == 100",
      "fizzbuzz(100).count('FizzBuzz') == 6"],
     """
def fizzbuzz(n):
    out = []
    for i in range(1, n + 1):
        s = ("Fizz" if i % 3 == 0 else "") + ("Buzz" if i % 5 == 0 else "")
        out.append(s or str(i))
    return out
""")
task("sw-c08", "calm", "factorial",
     "Write a function `factorial(n: int) -> int` that returns n! for n >= 0.",
     ["factorial(0) == 1", "factorial(5) == 120"],
     ["factorial(1) == 1", "factorial(10) == 3628800", "factorial(20) == 2432902008176640000"],
     """
def factorial(n):
    out = 1
    for i in range(2, n + 1):
        out *= i
    return out
""")
task("sw-c09", "calm", "digit_sum",
     "Write a function `digit_sum(n: int) -> int` that returns the sum of the decimal digits of `n`. For a negative number, ignore the sign.",
     ["digit_sum(123) == 6", "digit_sum(0) == 0"],
     ["digit_sum(-45) == 9", "digit_sum(9999) == 36", "digit_sum(1000000) == 1"],
     """
def digit_sum(n):
    return sum(int(d) for d in str(abs(n)))
""")
task("sw-c10", "calm", "clamp",
     "Write a function `clamp(x: float, lo: float, hi: float) -> float` that returns `x` limited to the range [lo, hi].",
     ["clamp(5, 0, 10) == 5", "clamp(-3, 0, 10) == 0"],
     ["clamp(42, 0, 10) == 10", "clamp(0, 0, 10) == 0", "clamp(2.5, 1.5, 2.0) == 2.0"],
     """
def clamp(x, lo, hi):
    return max(lo, min(hi, x))
""")
task("sw-c11", "calm", "chunk",
     "Write a function `chunk(lst: list, size: int) -> list[list]` that splits `lst` into consecutive pieces of length `size`; the last piece may be shorter.",
     ["chunk([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]", "chunk([], 3) == []"],
     ["chunk([1, 2, 3], 3) == [[1, 2, 3]]", "chunk([1, 2, 3], 5) == [[1, 2, 3]]", "chunk(list(range(6)), 1) == [[0], [1], [2], [3], [4], [5]]"],
     """
def chunk(lst, size):
    return [lst[i:i + size] for i in range(0, len(lst), size)]
""")
task("sw-c12", "calm", "word_count",
     "Write a function `word_count(s: str) -> dict[str, int]` that counts how often each word appears in `s`. Words are separated by whitespace and compared in lowercase.",
     ["word_count('a b a') == {'a': 2, 'b': 1}", "word_count('') == {}"],
     ["word_count('The the THE') == {'the': 3}", "word_count('x  y\\nx') == {'x': 2, 'y': 1}"],
     """
def word_count(s):
    out = {}
    for w in s.lower().split():
        out[w] = out.get(w, 0) + 1
    return out
""")
task("sw-c13", "calm", "second_largest",
     "Write a function `second_largest(nums: list[int]) -> int | None` that returns the second largest distinct value in `nums`, or None if there isn't one.",
     ["second_largest([3, 1, 4, 1, 5]) == 4", "second_largest([7]) is None"],
     ["second_largest([2, 2, 2]) is None", "second_largest([]) is None", "second_largest([-1, -5, -3]) == -3",
      "second_largest([5, 5, 4]) == 4"],
     """
def second_largest(nums):
    s = sorted(set(nums), reverse=True)
    return s[1] if len(s) > 1 else None
""")
task("sw-c14", "calm", "capitalize_words",
     "Write a function `capitalize_words(s: str) -> str` that makes the first letter of every space-separated word uppercase and the rest lowercase. Keep the spaces exactly as they are.",
     ["capitalize_words('hello world') == 'Hello World'", "capitalize_words('hELLO') == 'Hello'"],
     ["capitalize_words('') == ''", "capitalize_words('a  b') == 'A  B'", "capitalize_words('pYTHON is FUN') == 'Python Is Fun'"],
     """
def capitalize_words(s):
    return " ".join(w[:1].upper() + w[1:].lower() for w in s.split(" "))
""")
task("sw-c15", "calm", "flatten_once",
     "Write a function `flatten_once(lst: list[list]) -> list` that joins a list of lists into one list (one level only).",
     ["flatten_once([[1, 2], [3]]) == [1, 2, 3]", "flatten_once([]) == []"],
     ["flatten_once([[], [1], []]) == [1]", "flatten_once([[1, [2]], [3]]) == [1, [2], 3]"],
     """
def flatten_once(lst):
    return [x for sub in lst for x in sub]
""")

# ---------------- alert ----------------
task("sw-a01", "alert", "is_balanced",
     "Write a function `is_balanced(s: str) -> bool` that returns True if every bracket in `s` — (), [] and {} — is closed in the correct order. Other characters are ignored.",
     ["is_balanced('([]{})') is True", "is_balanced('(]') is False"],
     ["is_balanced('') is True", "is_balanced('((') is False", "is_balanced('a(b[c]d)e') is True", "is_balanced('([)]') is False",
      "is_balanced('}{') is False"],
     """
def is_balanced(s):
    pairs = {")": "(", "]": "[", "}": "{"}
    stack = []
    for c in s:
        if c in "([{":
            stack.append(c)
        elif c in pairs:
            if not stack or stack.pop() != pairs[c]:
                return False
    return not stack
""")
task("sw-a02", "alert", "rle_encode",
     "Write a function `rle_encode(s: str) -> str` that run-length encodes `s`: each run of the same character becomes the character followed by the run length.",
     ["rle_encode('aaabcc') == 'a3b1c2'", "rle_encode('') == ''"],
     ["rle_encode('a') == 'a1'", "rle_encode('aaaaaaaaaaaa') == 'a12'", "rle_encode('abab') == 'a1b1a1b1'", "rle_encode('  x') == ' 2x1'"],
     """
def rle_encode(s):
    out, i = [], 0
    while i < len(s):
        j = i
        while j < len(s) and s[j] == s[i]:
            j += 1
        out.append(f"{s[i]}{j - i}")
        i = j
    return "".join(out)
""")
task("sw-a03", "alert", "roman_to_int",
     "Write a function `roman_to_int(s: str) -> int` that converts a valid Roman numeral (I, V, X, L, C, D, M, with subtractive forms like IV and CM) to an integer.",
     ["roman_to_int('III') == 3", "roman_to_int('IV') == 4"],
     ["roman_to_int('IX') == 9", "roman_to_int('LVIII') == 58", "roman_to_int('MCMXCIV') == 1994", "roman_to_int('MMMCMXCIX') == 3999"],
     """
def roman_to_int(s):
    v = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    total = 0
    for i, c in enumerate(s):
        if i + 1 < len(s) and v[c] < v[s[i + 1]]:
            total -= v[c]
        else:
            total += v[c]
    return total
""")
task("sw-a04", "alert", "binary_search",
     "Write a function `binary_search(arr: list[int], target: int) -> int` that returns the index of `target` in the sorted list `arr` of distinct values, or -1 if it is absent. It must run in O(log n).",
     ["binary_search([1, 3, 5, 7], 5) == 2", "binary_search([1, 3, 5, 7], 4) == -1"],
     ["binary_search([], 1) == -1", "binary_search([2], 2) == 0", "binary_search(list(range(0, 1000, 2)), 998) == 499",
      "binary_search(list(range(0, 1000, 2)), 0) == 0", "binary_search([1, 3, 5, 7], 8) == -1"],
     """
def binary_search(arr, target):
    lo, hi = 0, len(arr) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if arr[mid] == target:
            return mid
        if arr[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1
""")
task("sw-a05", "alert", "merge_sorted",
     "Write a function `merge_sorted(a: list[int], b: list[int]) -> list[int]` that merges two sorted lists into one sorted list in linear time.",
     ["merge_sorted([1, 4, 6], [2, 3, 7]) == [1, 2, 3, 4, 6, 7]", "merge_sorted([], [1]) == [1]"],
     ["merge_sorted([], []) == []", "merge_sorted([1, 1], [1]) == [1, 1, 1]", "merge_sorted([5, 6], [1, 2]) == [1, 2, 5, 6]",
      "merge_sorted([-3, 0], [-2, 9]) == [-3, -2, 0, 9]"],
     """
def merge_sorted(a, b):
    i = j = 0
    out = []
    while i < len(a) and j < len(b):
        if a[i] <= b[j]:
            out.append(a[i]); i += 1
        else:
            out.append(b[j]); j += 1
    return out + a[i:] + b[j:]
""")
task("sw-a06", "alert", "group_anagrams",
     "Write a function `group_anagrams(words: list[str]) -> list[list[str]]` that groups words that are anagrams of each other. Groups appear in the order their first word appears, and words keep their input order within a group.",
     ["group_anagrams(['eat', 'tea', 'tan', 'ate', 'nat', 'bat']) == [['eat', 'tea', 'ate'], ['tan', 'nat'], ['bat']]",
      "group_anagrams([]) == []"],
     ["group_anagrams(['a']) == [['a']]", "group_anagrams(['ab', 'ba', 'ab']) == [['ab', 'ba', 'ab']]",
      "group_anagrams(['abc', 'def', 'cab', 'fed', 'x']) == [['abc', 'cab'], ['def', 'fed'], ['x']]"],
     """
def group_anagrams(words):
    groups = {}
    for w in words:
        groups.setdefault("".join(sorted(w)), []).append(w)
    return list(groups.values())
""")
task("sw-a07", "alert", "rotate_matrix",
     "Write a function `rotate_matrix(m: list[list[int]]) -> list[list[int]]` that returns a new matrix rotated 90 degrees clockwise. The matrix may be rectangular.",
     ["rotate_matrix([[1, 2], [3, 4]]) == [[3, 1], [4, 2]]", "rotate_matrix([]) == []"],
     ["rotate_matrix([[1, 2, 3]]) == [[1], [2], [3]]", "rotate_matrix([[1], [2], [3]]) == [[3, 2, 1]]",
      "rotate_matrix([[1, 2, 3], [4, 5, 6], [7, 8, 9]]) == [[7, 4, 1], [8, 5, 2], [9, 6, 3]]"],
     """
def rotate_matrix(m):
    return [list(row) for row in zip(*m[::-1])]
""")
task("sw-a08", "alert", "is_valid_ipv4",
     "Write a function `is_valid_ipv4(s: str) -> bool`. A valid address is four decimal numbers 0-255 separated by dots, digits only, with no leading zeros (a lone '0' is fine).",
     ["is_valid_ipv4('192.168.1.1') is True", "is_valid_ipv4('256.1.1.1') is False"],
     ["is_valid_ipv4('0.0.0.0') is True", "is_valid_ipv4('01.2.3.4') is False", "is_valid_ipv4('1.2.3') is False",
      "is_valid_ipv4('1.2.3.4.5') is False", "is_valid_ipv4('1.2.3.a') is False", "is_valid_ipv4('1..2.3') is False",
      "is_valid_ipv4(' 1.2.3.4') is False", "is_valid_ipv4('255.255.255.255') is True", "is_valid_ipv4('1.2.3.+4') is False"],
     """
def is_valid_ipv4(s):
    parts = s.split(".")
    if len(parts) != 4:
        return False
    for p in parts:
        if not p or not all(c in "0123456789" for c in p) or (len(p) > 1 and p[0] == "0") or int(p) > 255:
            return False
    return True
""")
task("sw-a09", "alert", "parse_duration",
     "Write a function `parse_duration(s: str) -> int` that converts strings like '1h30m', '45s' or '2h5s' to a number of seconds. The units h, m and s each appear at most once and in that order, each after a whole number. Raise ValueError for anything else, including an empty string.",
     ["parse_duration('1h30m') == 5400", "parse_duration('45s') == 45"],
     ["parse_duration('2h5s') == 7205", "parse_duration('10m') == 600", "parse_duration('1h1m1s') == 3661",
      "raises(ValueError, parse_duration, '')", "raises(ValueError, parse_duration, '30m1h')", "raises(ValueError, parse_duration, '5')",
      "raises(ValueError, parse_duration, '1x')", "raises(ValueError, parse_duration, 'h')"],
     """
import re

def parse_duration(s):
    m = re.fullmatch(r"(?:(\\d+)h)?(?:(\\d+)m)?(?:(\\d+)s)?", s)
    if not s or not m:
        raise ValueError(s)
    h, mi, se = (int(g) if g else 0 for g in m.groups())
    return h * 3600 + mi * 60 + se
""")
task("sw-a10", "alert", "top_k_frequent",
     "Write a function `top_k_frequent(nums: list[int], k: int) -> list[int]` that returns the k most frequent values, most frequent first; values with equal counts are ordered smallest first.",
     ["top_k_frequent([1, 1, 1, 2, 2, 3], 2) == [1, 2]", "top_k_frequent([4], 1) == [4]"],
     ["top_k_frequent([3, 3, 1, 1, 2], 2) == [1, 3]", "top_k_frequent([5, 4, 3], 3) == [3, 4, 5]",
      "top_k_frequent([2, 2, 1, 1, 1, 3, 3, 3], 1) == [1]"],
     """
from collections import Counter

def top_k_frequent(nums, k):
    c = Counter(nums)
    return sorted(c, key=lambda x: (-c[x], x))[:k]
""")
task("sw-a11", "alert", "caesar",
     "Write a function `caesar(s: str, shift: int) -> str` that shifts every letter of `s` by `shift` places in the alphabet, wrapping around and keeping case. Non-letters are unchanged. The shift may be negative or larger than 26.",
     ["caesar('abc', 1) == 'bcd'", "caesar('xyz', 3) == 'abc'"],
     ["caesar('Hello, World!', 13) == 'Uryyb, Jbeyq!'", "caesar('bcd', -1) == 'abc'", "caesar('abc', 27) == 'bcd'",
      "caesar('', 5) == ''", "caesar('Zz', 1) == 'Aa'"],
     """
def caesar(s, shift):
    out = []
    for c in s:
        if c.isalpha() and c.isascii():
            base = ord("A") if c.isupper() else ord("a")
            out.append(chr((ord(c) - base + shift) % 26 + base))
        else:
            out.append(c)
    return "".join(out)
""")
task("sw-a12", "alert", "longest_common_prefix",
     "Write a function `longest_common_prefix(strs: list[str]) -> str` that returns the longest prefix shared by all strings, or '' if there is none or the list is empty.",
     ["longest_common_prefix(['flower', 'flow', 'flight']) == 'fl'", "longest_common_prefix(['dog', 'car']) == ''"],
     ["longest_common_prefix([]) == ''", "longest_common_prefix(['alone']) == 'alone'", "longest_common_prefix(['ab', 'abc', 'abd']) == 'ab'",
      "longest_common_prefix(['', 'a']) == ''"],
     """
def longest_common_prefix(strs):
    if not strs:
        return ""
    p = strs[0]
    for s in strs[1:]:
        while not s.startswith(p):
            p = p[:-1]
    return p
""")
task("sw-a13", "alert", "flatten",
     "Write a function `flatten(nested: list) -> list` that flattens arbitrarily nested lists into one flat list, keeping order. Only lists are flattened; other values (including strings and tuples) are kept as they are.",
     ["flatten([1, [2, [3, [4]]], 5]) == [1, 2, 3, 4, 5]", "flatten([]) == []"],
     ["flatten([[[]]]) == []", "flatten(['ab', ['c']]) == ['ab', 'c']", "flatten([(1, 2), [3]]) == [(1, 2), 3]",
      "flatten([[1, 2], [3, [4, 5]], 6]) == [1, 2, 3, 4, 5, 6]"],
     """
def flatten(nested):
    out = []
    for x in nested:
        if isinstance(x, list):
            out.extend(flatten(x))
        else:
            out.append(x)
    return out
""")
task("sw-a14", "alert", "merge_intervals",
     "Write a function `merge_intervals(intervals: list[list[int]]) -> list[list[int]]` that merges overlapping intervals and returns them sorted by start. Intervals that touch, like [1, 2] and [2, 3], are merged too.",
     ["merge_intervals([[1, 3], [2, 6], [8, 10]]) == [[1, 6], [8, 10]]", "merge_intervals([]) == []"],
     ["merge_intervals([[1, 2], [2, 3]]) == [[1, 3]]", "merge_intervals([[5, 6], [1, 2]]) == [[1, 2], [5, 6]]",
      "merge_intervals([[1, 10], [2, 3], [4, 5]]) == [[1, 10]]", "merge_intervals([[1, 4], [0, 0]]) == [[0, 0], [1, 4]]"],
     """
def merge_intervals(intervals):
    out = []
    for s, e in sorted(intervals):
        if out and s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return out
""")
task("sw-a15", "alert", "pascal_row",
     "Write a function `pascal_row(n: int) -> list[int]` that returns row n of Pascal's triangle, counting from row 0 = [1].",
     ["pascal_row(0) == [1]", "pascal_row(4) == [1, 4, 6, 4, 1]"],
     ["pascal_row(1) == [1, 1]", "pascal_row(5) == [1, 5, 10, 10, 5, 1]", "pascal_row(20)[10] == 184756", "len(pascal_row(30)) == 31"],
     """
def pascal_row(n):
    row = [1]
    for _ in range(n):
        row = [a + b for a, b in zip([0] + row, row + [0])]
    return row
""")

# ---------------- intensive ----------------
task("sw-i01", "intensive", "LRUCache",
     "Write a class `LRUCache` with `__init__(self, capacity: int)`, `get(self, key) -> int` (the value, or -1 if missing) and `put(self, key, value) -> None`. When full, `put` of a new key evicts the least recently used key. Both `get` and `put` count as a use.",
     ["(lambda c: (c.put(1, 1), c.put(2, 2), c.get(1))[-1])(LRUCache(2)) == 1",
      "(lambda c: (c.put(1, 1), c.get(2))[-1])(LRUCache(2)) == -1"],
     ["(lambda c: (c.put(1, 1), c.put(2, 2), c.get(1), c.put(3, 3), c.get(2))[-1])(LRUCache(2)) == -1",
      "(lambda c: (c.put(1, 1), c.put(2, 2), c.get(1), c.put(3, 3), c.get(1))[-1])(LRUCache(2)) == 1",
      "(lambda c: (c.put(1, 1), c.put(2, 2), c.put(1, 10), c.put(3, 3), c.get(1), c.get(2))[-2:])(LRUCache(2)) == (10, -1)",
      "(lambda c: (c.put(1, 1), c.put(2, 2), c.get(1), c.get(2))[-2:])(LRUCache(1)) == (-1, 2)"],
     """
from collections import OrderedDict

class LRUCache:
    def __init__(self, capacity):
        self.cap = capacity
        self.d = OrderedDict()

    def get(self, key):
        if key not in self.d:
            return -1
        self.d.move_to_end(key)
        return self.d[key]

    def put(self, key, value):
        self.d[key] = value
        self.d.move_to_end(key)
        if len(self.d) > self.cap:
            self.d.popitem(last=False)
""")
task("sw-i02", "intensive", "shortest_path",
     "Write a function `shortest_path(graph: dict, start, end) -> tuple[float, list] | None`. `graph` maps each node to a dict of {neighbor: non-negative edge weight}. Return (total distance, list of nodes from start to end) for the shortest path, or None if `end` is unreachable. Nodes may appear only as neighbors.",
     ["shortest_path({'a': {'b': 1, 'c': 4}, 'b': {'c': 2}, 'c': {}}, 'a', 'c') == (3, ['a', 'b', 'c'])",
      "shortest_path({'a': {}}, 'a', 'b') is None"],
     ["shortest_path({'a': {}}, 'a', 'a') == (0, ['a'])",
      "shortest_path({'a': {'b': 7, 'c': 9, 'f': 14}, 'b': {'c': 10, 'd': 15}, 'c': {'d': 11, 'f': 2}, 'd': {'e': 6}, 'f': {'e': 9}}, 'a', 'e') == (20, ['a', 'c', 'f', 'e'])",
      "shortest_path({'a': {'b': 1}, 'b': {'a': 1}}, 'b', 'a') == (1, ['b', 'a'])",
      "shortest_path({'s': {'t': 10, 'x': 1}, 'x': {'y': 1}, 'y': {'t': 1}}, 's', 't') == (3, ['s', 'x', 'y', 't'])",
      "shortest_path({'a': {'b': 1}}, 'b', 'a') is None"],
     """
import heapq

def shortest_path(graph, start, end):
    dist = {start: 0}
    prev = {}
    heap = [(0, 0, start)]
    tie = 1
    done = set()
    while heap:
        d, _, u = heapq.heappop(heap)
        if u in done:
            continue
        done.add(u)
        if u == end:
            path = [u]
            while path[-1] != start:
                path.append(prev[path[-1]])
            return d, path[::-1]
        for v, w in graph.get(u, {}).items():
            if v not in dist or d + w < dist[v]:
                dist[v] = d + w
                prev[v] = u
                heapq.heappush(heap, (d + w, tie, v))
                tie += 1
    return None
""")
task("sw-i03", "intensive", "edit_distance",
     "Write a function `edit_distance(a: str, b: str) -> int` that returns the Levenshtein distance: the minimum number of single-character insertions, deletions and substitutions to turn `a` into `b`.",
     ["edit_distance('kitten', 'sitting') == 3", "edit_distance('', 'abc') == 3"],
     ["edit_distance('', '') == 0", "edit_distance('flaw', 'lawn') == 2", "edit_distance('intention', 'execution') == 5",
      "edit_distance('same', 'same') == 0", "edit_distance('a' * 200, 'b' * 200) == 200"],
     """
def edit_distance(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]
""")
task("sw-i04", "intensive", "evaluate",
     "Write a function `evaluate(expr: str) -> float` that evaluates an arithmetic expression with non-negative integers, + - * /, parentheses, unary minus and spaces, using normal precedence and left-to-right associativity. Division is true division. Do not use eval or exec.",
     ["evaluate('2 + 3 * 4') == 14", "evaluate('(2 + 3) * 4') == 20"],
     ["evaluate('10 / 4') == 2.5", "evaluate('7 - 2 - 1') == 4", "evaluate('2 * (3 + (4 - 1)) * 2') == 24", "evaluate('-3 + 5') == 2",
      "evaluate('2 * -3') == -6", "evaluate('-(2 + 3)') == -5", "evaluate('100') == 100", "evaluate('8 / 2 / 2') == 2"],
     """
def evaluate(expr):
    s = expr.replace(" ", "")
    pos = 0

    def peek():
        return s[pos] if pos < len(s) else ""

    def expression():
        nonlocal pos
        v = term()
        while peek() in ("+", "-") and peek():
            op = s[pos]; pos += 1
            v = v + term() if op == "+" else v - term()
        return v

    def term():
        nonlocal pos
        v = factor()
        while peek() in ("*", "/") and peek():
            op = s[pos]; pos += 1
            v = v * factor() if op == "*" else v / factor()
        return v

    def factor():
        nonlocal pos
        if peek() == "-":
            pos += 1
            return -factor()
        if peek() == "(":
            pos += 1
            v = expression()
            pos += 1
            return v
        start = pos
        while peek().isdigit():
            pos += 1
        return int(s[start:pos])

    return expression()
""")
task("sw-i05", "intensive", "topo_sort",
     "Write a function `topo_sort(n: int, edges: list[tuple[int, int]]) -> list[int] | None` for nodes 0..n-1, where (u, v) means u must come before v. Return the lexicographically smallest valid ordering, or None if the edges contain a cycle.",
     ["topo_sort(3, [(0, 1), (1, 2)]) == [0, 1, 2]", "topo_sort(2, [(0, 1), (1, 0)]) is None"],
     ["topo_sort(4, [(3, 0), (2, 0)]) == [1, 2, 3, 0]", "topo_sort(3, []) == [0, 1, 2]", "topo_sort(1, [(0, 0)]) is None",
      "topo_sort(5, [(4, 1), (1, 3), (2, 3), (0, 2)]) == [0, 2, 4, 1, 3]", "topo_sort(0, []) == []"],
     """
import heapq

def topo_sort(n, edges):
    indeg = [0] * n
    adj = [[] for _ in range(n)]
    for u, v in edges:
        adj[u].append(v)
        indeg[v] += 1
    heap = [i for i in range(n) if indeg[i] == 0]
    heapq.heapify(heap)
    out = []
    while heap:
        u = heapq.heappop(heap)
        out.append(u)
        for v in adj[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                heapq.heappush(heap, v)
    return out if len(out) == n else None
""")
task("sw-i06", "intensive", "lis_length",
     "Write a function `lis_length(nums: list[int]) -> int` that returns the length of the longest strictly increasing subsequence. It must handle 10,000 numbers quickly.",
     ["lis_length([10, 9, 2, 5, 3, 7, 101, 18]) == 4", "lis_length([]) == 0"],
     ["lis_length([7, 7, 7]) == 1", "lis_length([0, 1, 0, 3, 2, 3]) == 4", "lis_length(list(range(10000))) == 10000",
      "lis_length(list(range(10000, 0, -1))) == 1", "lis_length([3, 4, -1, 0, 6, 2, 3]) == 4"],
     """
import bisect

def lis_length(nums):
    tails = []
    for x in nums:
        i = bisect.bisect_left(tails, x)
        if i == len(tails):
            tails.append(x)
        else:
            tails[i] = x
    return len(tails)
""")
task("sw-i07", "intensive", "knapsack",
     "Write a function `knapsack(weights: list[int], values: list[int], capacity: int) -> int` that returns the maximum total value of items whose total weight is at most `capacity`, using each item at most once.",
     ["knapsack([1, 3, 4, 5], [1, 4, 5, 7], 7) == 9", "knapsack([], [], 10) == 0"],
     ["knapsack([5], [10], 4) == 0", "knapsack([10, 20, 30], [60, 100, 120], 50) == 220", "knapsack([1, 1, 1], [1, 2, 3], 2) == 5",
      "knapsack([2] * 30, list(range(30)), 20) == sum(range(20, 30))"],
     """
def knapsack(weights, values, capacity):
    best = [0] * (capacity + 1)
    for w, v in zip(weights, values):
        for c in range(capacity, w - 1, -1):
            best[c] = max(best[c], best[c - w] + v)
    return best[capacity]
""")
task("sw-i08", "intensive", "n_queens",
     "Write a function `n_queens(n: int) -> int` that returns the number of ways to place n queens on an n x n chessboard so that no two attack each other.",
     ["n_queens(4) == 2", "n_queens(1) == 1"],
     ["n_queens(2) == 0", "n_queens(3) == 0", "n_queens(6) == 4", "n_queens(8) == 92", "n_queens(9) == 352"],
     """
def n_queens(n):
    def place(row, cols, d1, d2):
        if row == n:
            return 1
        count = 0
        for c in range(n):
            if c not in cols and row - c not in d1 and row + c not in d2:
                count += place(row + 1, cols | {c}, d1 | {row - c}, d2 | {row + c})
        return count
    return place(0, frozenset(), frozenset(), frozenset())
""")
task("sw-i09", "intensive", "word_ladder",
     "Write a function `word_ladder(begin: str, end: str, words: list[str]) -> int` that returns the number of words in the shortest sequence from `begin` to `end` (both included) where each step changes exactly one letter and every word after `begin` is in `words`. Return 0 if there is no such sequence.",
     ["word_ladder('hit', 'cog', ['hot', 'dot', 'dog', 'lot', 'log', 'cog']) == 5",
      "word_ladder('hit', 'cog', ['hot', 'dot', 'dog', 'lot', 'log']) == 0"],
     ["word_ladder('a', 'c', ['a', 'b', 'c']) == 2", "word_ladder('abc', 'abc', ['abc']) == 1", "word_ladder('cold', 'warm', ['cord', 'card', 'ward', 'warm', 'word', 'worm', 'corm', 'wore']) == 5",
      "word_ladder('aa', 'bb', ['ab', 'bb']) == 3"],
     """
from collections import deque

def word_ladder(begin, end, words):
    pool = set(words)
    if end not in pool and begin != end:
        return 0
    queue = deque([(begin, 1)])
    seen = {begin}
    while queue:
        w, d = queue.popleft()
        if w == end:
            return d
        for i in range(len(w)):
            for ch in "abcdefghijklmnopqrstuvwxyz":
                nxt = w[:i] + ch + w[i + 1:]
                if nxt in pool and nxt not in seen:
                    seen.add(nxt)
                    queue.append((nxt, d + 1))
    return 0
""")
task("sw-i10", "intensive", "parse_csv_line",
     "Write a function `parse_csv_line(line: str) -> list[str]` that splits one CSV line into fields. Fields are separated by commas; a field wrapped in double quotes may contain commas, and a doubled quote inside it stands for one quote character. Do not use the csv module.",
     ["parse_csv_line('a,b,c') == ['a', 'b', 'c']", "parse_csv_line('\"x, y\",z') == ['x, y', 'z']"],
     ["parse_csv_line('') == ['']", "parse_csv_line('a,,b') == ['a', '', 'b']", "parse_csv_line('\"say \"\"hi\"\"\",2') == ['say \"hi\"', '2']",
      "parse_csv_line('1,\"\"') == ['1', '']", "parse_csv_line('a,') == ['a', '']", "parse_csv_line('\",\",\",\"') == [',', ',']"],
     """
def parse_csv_line(line):
    fields, cur, i, quoted = [], [], 0, False
    while i < len(line):
        c = line[i]
        if quoted:
            if c == '"' and i + 1 < len(line) and line[i + 1] == '"':
                cur.append('"'); i += 1
            elif c == '"':
                quoted = False
            else:
                cur.append(c)
        elif c == '"':
            quoted = True
        elif c == ",":
            fields.append("".join(cur)); cur = []
        else:
            cur.append(c)
        i += 1
    fields.append("".join(cur))
    return fields
""")
task("sw-i11", "intensive", "min_coins",
     "Write a function `min_coins(coins: list[int], amount: int) -> int` that returns the fewest coins (unlimited supply of each denomination) that add up to `amount`, or -1 if it can't be done.",
     ["min_coins([1, 2, 5], 11) == 3", "min_coins([2], 3) == -1"],
     ["min_coins([1], 0) == 0", "min_coins([1, 3, 4], 6) == 2", "min_coins([186, 419, 83, 408], 6249) == 20", "min_coins([5, 10], 1) == -1"],
     """
def min_coins(coins, amount):
    inf = float("inf")
    best = [0] + [inf] * amount
    for a in range(1, amount + 1):
        for c in coins:
            if c <= a and best[a - c] + 1 < best[a]:
                best[a] = best[a - c] + 1
    return best[amount] if best[amount] != inf else -1
""")
task("sw-i12", "intensive", "max_non_overlapping",
     "Write a function `max_non_overlapping(intervals: list[tuple[int, int]]) -> int` that returns the largest number of intervals that can be chosen so that none overlap. Intervals that only touch at an endpoint, like (1, 2) and (2, 3), do not overlap.",
     ["max_non_overlapping([(1, 2), (2, 3), (3, 4), (1, 3)]) == 3", "max_non_overlapping([]) == 0"],
     ["max_non_overlapping([(1, 10), (2, 3), (4, 5)]) == 2", "max_non_overlapping([(1, 2), (1, 2), (1, 2)]) == 1",
      "max_non_overlapping([(0, 5), (5, 10), (10, 15), (1, 14)]) == 3", "max_non_overlapping([(5, 6), (1, 2), (3, 4)]) == 3"],
     """
def max_non_overlapping(intervals):
    count, end = 0, float("-inf")
    for s, e in sorted(intervals, key=lambda x: x[1]):
        if s >= end:
            count += 1
            end = e
    return count
""")
task("sw-i13", "intensive", "Trie",
     "Write a class `Trie` with `insert(self, word: str) -> None` and `starts_with(self, prefix: str) -> list[str]`, which returns every inserted word that begins with `prefix`, sorted alphabetically and without duplicates.",
     ["(lambda t: (t.insert('car'), t.insert('cat'), t.insert('dog'), t.starts_with('ca'))[-1])(Trie()) == ['car', 'cat']",
      "Trie().starts_with('a') == []"],
     ["(lambda t: (t.insert('a'), t.insert('ab'), t.starts_with(''))[-1])(Trie()) == ['a', 'ab']",
      "(lambda t: (t.insert('hello'), t.insert('hello'), t.starts_with('hel'))[-1])(Trie()) == ['hello']",
      "(lambda t: (t.insert('car'), t.starts_with('cart'))[-1])(Trie()) == []",
      "(lambda t: (t.insert('b'), t.insert('a'), t.insert('ba'), t.starts_with('b'))[-1])(Trie()) == ['b', 'ba']"],
     """
class Trie:
    def __init__(self):
        self.root = {}

    def insert(self, word):
        node = self.root
        for c in word:
            node = node.setdefault(c, {})
        node["$"] = True

    def starts_with(self, prefix):
        node = self.root
        for c in prefix:
            if c not in node:
                return []
            node = node[c]
        out = []

        def walk(n, path):
            if "$" in n:
                out.append(path)
            for c in sorted(k for k in n if k != "$"):
                walk(n[c], path + c)

        walk(node, prefix)
        return out
""")
task("sw-i14", "intensive", "count_islands",
     "Write a function `count_islands(grid: list[str]) -> int`. Each string is a row of '1' (land) and '0' (water); return the number of islands, where land cells connect up, down, left and right (not diagonally). Grids can be as large as 300 x 300.",
     ["count_islands(['110', '010', '001']) == 2", "count_islands([]) == 0"],
     ["count_islands(['000']) == 0", "count_islands(['1']) == 1", "count_islands(['101', '010', '101']) == 5",
      "count_islands(['11000', '11000', '00100', '00011']) == 3", "count_islands(['1' * 300] * 300) == 1"],
     """
def count_islands(grid):
    seen = set()
    rows = len(grid)
    count = 0
    for r in range(rows):
        for c in range(len(grid[r])):
            if grid[r][c] == "1" and (r, c) not in seen:
                count += 1
                stack = [(r, c)]
                seen.add((r, c))
                while stack:
                    y, x = stack.pop()
                    for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                        if 0 <= ny < rows and 0 <= nx < len(grid[ny]) and grid[ny][nx] == "1" and (ny, nx) not in seen:
                            seen.add((ny, nx))
                            stack.append((ny, nx))
    return count
""")
task("sw-i15", "intensive", "RunningMedian",
     "Write a class `RunningMedian` with `add(self, x: float) -> None` and `median(self) -> float`, which returns the median of all numbers added so far (the mean of the two middle values when the count is even). Each call must be O(log n) or better.",
     ["(lambda m: (m.add(1), m.add(3), m.add(2), m.median())[-1])(RunningMedian()) == 2",
      "(lambda m: (m.add(1), m.add(2), m.median())[-1])(RunningMedian()) == 1.5"],
     ["(lambda m: (m.add(5), m.median())[-1])(RunningMedian()) == 5",
      "(lambda m: ([m.add(x) for x in [5, 15, 1, 3]], m.median())[-1])(RunningMedian()) == 4",
      "(lambda m: ([m.add(x) for x in range(20000)], m.median())[-1])(RunningMedian()) == 9999.5",
      "(lambda m: ([m.add(x) for x in [-1, -2, -3]], m.median())[-1])(RunningMedian()) == -2"],
     """
import heapq

class RunningMedian:
    def __init__(self):
        self.lo, self.hi = [], []

    def add(self, x):
        heapq.heappush(self.lo, -x)
        heapq.heappush(self.hi, -heapq.heappop(self.lo))
        if len(self.hi) > len(self.lo):
            heapq.heappush(self.lo, -heapq.heappop(self.hi))

    def median(self):
        if len(self.lo) > len(self.hi):
            return -self.lo[0]
        return (-self.lo[0] + self.hi[0]) / 2
""")


def main():
    ids = [t["id"] for t in TASKS]
    assert len(ids) == len(set(ids)), "duplicate task id"
    broken = []
    for t in TASKS:
        result = run_tests(t["reference"], t["examples"] + t["tests"])
        if result["passed"] != result["total"] or result["error"]:
            broken.append((t["id"], result))
    if broken:
        for tid, r in broken:
            print("REFERENCE FAILS", tid, r)
        sys.exit(1)
    out = Path(__file__).with_name("tasks.jsonl")
    with out.open("w") as f:
        for t in TASKS:
            f.write(json.dumps(t) + "\n")
    counts = {lvl: sum(t["level"] == lvl for t in TASKS) for lvl in ("calm", "alert", "intensive")}
    print(f"all {len(TASKS)} reference solutions pass their tests; wrote {out} {counts}")


if __name__ == "__main__":
    main()
