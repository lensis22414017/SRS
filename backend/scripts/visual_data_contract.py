class ContractError(ValueError): pass

def assert_keys(name, payload, keys):
    missing = [k for k in keys if k not in payload]
    if missing:
        raise ContractError(f"{name} missing keys: {missing}")

def assert_non_empty(name, payload, key):
    v = payload.get(key)
    if not isinstance(v, list) or len(v) == 0:
        raise ContractError(f"{name}.{key} must be non-empty list")
