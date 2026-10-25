"""Client minimal de l'API Apify (bibliothèque standard uniquement)."""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.apify.com/v2"


class ApifyError(RuntimeError):
    pass


def _request(method, path, token, body=None, params=None, timeout=120):
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise ApifyError(f"{method} {path} -> HTTP {e.code}: {e.read()[:300]!r}") from e


def run_actor(actor, run_input, token, max_charge_usd=None, timeout_s=3600):
    """Lance un actor, attend la fin et renvoie les éléments de son dataset."""
    params = {}
    if max_charge_usd:
        # Plafond de dépense : l'actor s'arrête proprement une fois atteint.
        params["maxTotalChargeUsd"] = max_charge_usd
    run = _request("POST", f"/acts/{actor}/runs", token, run_input, params)["data"]
    run_id = run["id"]
    print(f"  Apify {actor}: run {run_id} lancé")

    deadline = time.time() + timeout_s
    while run["status"] in ("READY", "RUNNING"):
        if time.time() > deadline:
            raise ApifyError(f"{actor}: délai dépassé (run {run_id})")
        run = _request("GET", f"/actor-runs/{run_id}", token, params={"waitForFinish": 60})["data"]

    # Un run stoppé par le plafond de dépense a quand même produit des résultats exploitables.
    if run["status"] not in ("SUCCEEDED", "ABORTED", "TIMED-OUT"):
        raise ApifyError(f"{actor}: run {run_id} terminé en {run['status']}")
    print(f"  Apify {actor}: {run['status']}, coût ~{run.get('usageTotalUsd', '?')} $")

    items, offset = [], 0
    while True:
        page = _get_items(run["defaultDatasetId"], token, offset)
        items.extend(page)
        if len(page) < 1000:
            return items
        offset += len(page)


def _get_items(dataset_id, token, offset):
    url = f"{API}/datasets/{dataset_id}/items?" + urllib.parse.urlencode(
        {"clean": "true", "format": "json", "offset": offset, "limit": 1000}
    )
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))
