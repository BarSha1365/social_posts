def _norm(n: str) -> str:
    return (n or "").strip().lower()

def merge_auto_with_overrides(auto_list: list[str], overrides_by_name: dict, max_items=60, restrict_overrides_to_menu=True):
    merged, seen = [], set()
    auto_norms = [_norm(x) for x in auto_list]
    auto_set = set(auto_norms)

    for obj in overrides_by_name.values():
        raw = (obj.get("name") or "").strip()
        norm = _norm(raw)
        if not norm or norm in seen: continue
        if restrict_overrides_to_menu and norm not in auto_set: 
            continue
        seen.add(norm)
        merged.append({"name": raw or norm.capitalize(), "fact": obj.get("fact","")})
        if len(merged) >= max_items: return merged

    for raw in auto_list:
        norm = _norm(raw)
        if norm in seen: continue
        seen.add(norm)
        merged.append({"name": raw.capitalize(), "fact": f"{raw.capitalize()} – kurz & knackig zubereitet schmeckt’s am besten."})
        if len(merged) >= max_items: break

    return merged