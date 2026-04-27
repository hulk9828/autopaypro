def repeated_chars(s):
    freq = {}

    for ch in s:
        freq[ch] = freq.get(ch, 0) + 1

    result = []
    seen = set()

    for ch in s:
        if freq[ch] > 1 and ch not in seen:
            result.append(ch)
            seen.add(ch)

    return "".join(result)


print(repeated_chars("ffabbeaaacffacaeebca"))