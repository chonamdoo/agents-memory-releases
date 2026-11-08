"""Native evidence and conservative literal subject constraints.

This only sees complete, authorized sources already nominated by Native recall.
It neither retrieves other records nor assigns a lexical relevance score. A
subject is used only when an original source declares it grammatically and the
query mentions that literal subject (or an explicitly documented alias).
Unscoped sources and ambiguous queries keep their Native order.
"""
from __future__ import annotations

import math
import re
import unicodedata


def native_evidence(hit, rank, source_ids):
    """Keep actual Native scores separate from the gateway's reciprocal rank."""
    scores = hit.get("scores")
    result = {"rank": rank, "source_ids": sorted(set(source_ids))}
    if isinstance(hit.get("id"), str):
        result["native_id"] = hit["id"]
    if isinstance(scores, dict):
        result["scores"] = {
            key: value for key, value in scores.items()
            if key in {"final", "reranker", "semantic", "keyword"}
            and (value is None or type(value) in (int, float) and math.isfinite(value))
        }
    return result


def merge_evidence(left, right):
    result = list(left)
    for entry in right:
        if entry not in result:
            result.append(entry)
    return result


def _normal(text):
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


# Deictic/general qualifiers do not name an independent subject. In particular,
# an unnamed exception must not be treated as a different entity.
_UNSCOPED_HEADS = {
    "the", "a", "an", "this", "that", "these", "those", "its", "their", "our",
    "my", "your", "his", "her", "every", "each", "any", "all",
    "i", "me", "we", "us", "you", "he", "him", "she", "it", "they", "them",
    "itself", "themselves", "ours", "yours", "mine", "theirs", "oneself",
    "someone", "something", "anyone", "anything", "everyone", "everything",
    "here", "there", "some", "other", "another",
    "이", "그", "해당", "우리", "내", "모든", "일반", "기본", "기존", "다음", "이번",
    "이것", "그것", "저것", "이들", "그들", "저들", "여기", "거기", "저기",
    "어떤", "각", "현재", "긴급", "정규", "표준",
}
_KOREAN_SUBJECT = re.compile(r"^(.{1,160}?)(?:에서(?:는|도)?|의)(?=\s)")
_POSSESSIVE_SUBJECT = re.compile(r"^(.{1,160}?)[’']s(?=\s)")
_ALIAS = re.compile(r"^(.*?)\s*\((?:also known as|aka|별칭)\s+(.+?)\)$", re.I)
_ROLE = re.compile(r"^(?:project|service|team|프로젝트|서비스|팀)\s+(.+)$", re.I)
_PARTICLE = re.compile(r"^(?:에서는|에서도|에서|으로|의|은|는|이|가|을|를|에|와|과|도)(?=$|\W)")
_PREFACE = re.compile(r"^(?:please\s+)?(?:remember|note|keep in mind)(?:\s+that)?\s+", re.I)
_NEGATED_QUERY = re.compile(
    r"\b(?:not|never|no|without|except|exclude\w*|excluding|avoid\w*|ignore\w*)\b"
    r"|\b\w+n['’]t\b"
    r"|\b(?:other|rather)\s+than\b|\binstead\s+of\b"
    r"|(?:말고|아닌|아니라|아니고|빼고|대신)(?=$|\W)"
    r"|제외(?:하고|해서|하여|한|할|해|하라)?(?=$|\W)"
)


def _specific_name(name):
    # A role may establish the full literal "Project A", but does not make
    # its shorthand "a" distinguishable from an article. The same applies to
    # an explicitly supplied alias that is a pronoun or a deictic expression.
    words = name.split()
    return (bool(words) and words[0] not in _UNSCOPED_HEADS
            and sum(char.isalnum() for char in name) > 1)


def _subjects(text):
    """Return source-declared subjects and aliases, never inferred entities.

    A Korean noun phrase before a possessive/locative particle or an English
    proper-name possessive is explicit subject evidence. Ordinary predicates,
    sentence keywords and single untyped Korean words do not establish scope.
    """
    declarations = []
    for clause in re.split(r"\n|[:;]|[.!?]\s+", text):
        clause = clause.strip(" \t-*#>•")
        clause = _PREFACE.sub("", clause)
        korean = _KOREAN_SUBJECT.match(clause)
        possessive = _POSSESSIVE_SUBJECT.match(clause)
        match = korean or possessive
        if not match:
            continue
        head = match.group(1).strip(" `\"'“”‘’")
        alias = _ALIAS.match(head)
        label = (alias.group(1) if alias else head).strip()
        words = label.split()
        if not words or _normal(words[0]) in _UNSCOPED_HEADS:
            continue
        role = _ROLE.match(label)
        if korean and len(words) < 2 and not role:
            continue
        if possessive and not role and not label[0].isupper():
            continue
        canonical = _normal(label)
        if not _specific_name(canonical):
            continue
        names = {canonical}
        if alias:
            shorthand = _normal(alias.group(2).strip(" `\"'“”‘’"))
            if _specific_name(shorthand):
                names.add(shorthand)
        if role:
            shorthand = _normal(role.group(1).strip(" `\"'“”‘’"))
            if _specific_name(shorthand):
                names.add(shorthand)
        declarations.append((canonical, names))
    return declarations


def _mentions(text, name):
    for match in re.finditer(re.escape(name), text):
        if match.start() and (text[match.start() - 1].isalnum() or text[match.start() - 1] == "_"):
            continue
        suffix = text[match.end():]
        if not suffix or not (suffix[0].isalnum() or suffix[0] == "_") or _PARTICLE.match(suffix):
            return True
    return False


def scoped_native_results(query, items, namespace=None):
    """Exclude an explicitly different source subject before the result limit.

    No known literal subject, a common literal present in every source, or an
    ambiguous alias leaves semantic recall intact. The number of matching
    subjects/results is unrestricted. A source mentioning the requested subject
    anywhere is retained, including cross-references and complete exceptions.
    """
    query = _normal(query)
    if _NEGATED_QUERY.search(query):
        return items  # Mention under negation does not establish positive scope.
    if namespace is None:
        namespace = lambda item: (item.get("author_id"), item.get("project"))
    groups = {}
    for item in items:
        groups.setdefault(namespace(item), []).append(item)
    if len(groups) > 1:
        retained = {id(item) for group in groups.values()
                    for item in scoped_native_results(query, group, namespace)}
        return [item for item in items if id(item) in retained]
    declarations = [_subjects(item["text"]) for item in items]
    aliases = {}
    subjects = {subject for source in declarations for subject, _ in source}
    parent = {subject: subject for subject in subjects}
    def root(subject):
        while parent[subject] != subject:
            subject = parent[subject]
        return subject
    # A documented alias can itself head another approved source. Join that
    # spelling only when the original declarations give it one owner.
    for source in declarations:
        for subject, names in source:
            for name in names:
                if name != subject:
                    aliases.setdefault(name, set()).add(subject)
    for name, owners in aliases.items():
        if name in subjects and len(owners) == 1:
            left, right = root(name), root(next(iter(owners)))
            if left != right:
                parent[left] = right
    owners = {}
    for source in declarations:
        for subject, names in source:
            for name in names:
                owners.setdefault(name, set()).add(root(subject))
    requested = set()
    for name, subjects in owners.items():
        if _mentions(query, name):
            if len(subjects) != 1:
                return items  # The source evidence does not resolve this alias.
            requested.update(subjects)
    if not requested:
        return items
    names = {name for name, subjects in owners.items()
             if len(subjects) == 1 and subjects <= requested}
    supported = [any(_mentions(_normal(item["text"]), name) for name in names) for item in items]
    if not any(supported) or all(supported):
        return items
    return [item for item, source, matches in zip(items, declarations, supported)
            if matches or not source
            or any(len(owners.get(subject, ())) != 1 for subject, _ in source)]
