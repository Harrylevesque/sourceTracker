    resp = {"project": name, "url": normalized, "title": result, "saved": saved}
        name, _, json_path = project_paths(project_name)
import time
import requests
from bs4 import BeautifulSoup
import json
from typing import Optional, Dict, List
from urllib.parse import urlparse, urljoin
from typing import Optional
from urllib.parse import urlparse
import hashlib
import difflib
import base64
import html
# ...existing code... (removed unused imports)
from urllib.parse import urlparse
import ipaddress
from fastapi.responses import HTMLResponse, Response
from urllib3.exceptions import NameResolutionError

from fastapi import FastAPI, HTTPException, Body, Query, Path
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, root_validator

import uvicorn


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEFAULT_PROJECT = "random"
STORAGE_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "storage"))


@app.get("/")
async def check():
    return {"message": "Hello World", "time": time.time()}


def get_title(url: str) -> str:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        return soup.title.string.strip() if soup.title and soup.title.string else "No title found"
    except (requests.exceptions.MissingSchema, requests.exceptions.InvalidURL) as e:
        # Treat malformed URLs as client errors
        raise ValueError(str(e))
    except requests.exceptions.ConnectionError as e:
        # DNS resolution failures are client-side issues for bad/unknown hosts
        if isinstance(e.__cause__, NameResolutionError) or 'NameResolutionError' in str(e):
            raise ValueError(f"Unable to resolve host for URL: {url}")
        return f"Error: {e}"
    except requests.RequestException as e:
        # Network/remote errors are returned as an "Error: ..." string and handled as 502 by the caller
        return f"Error: {e}"


def sanitize_project_name(name: Optional[str]) -> str:
    name = (name or DEFAULT_PROJECT).strip()
    if not name:
        raise ValueError("Project name cannot be empty")
    if not re.match(r"^[A-Za-z0-9_-]+$", name):
        raise ValueError("Project names may only contain letters, numbers, hyphens, and underscores")
    return name


def project_paths(name: Optional[str]):
    sanitized = sanitize_project_name(name)
    directory = os.path.normpath(os.path.join(STORAGE_ROOT, sanitized))
    file_path = os.path.join(directory, "visited.json")
    os.makedirs(directory, exist_ok=True)
def history_root_for_project(name: str) -> str:
    _, directory, _ = project_paths(name)
    return os.path.join(directory, 'history')


@app.get("/projects/{project_name}/history")
async def list_history(project_name: str = Path(...)):
    try:
        name, directory, _ = project_paths(project_name)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    hist_root = os.path.join(directory, 'history')
    if not os.path.exists(hist_root):
        return {"project": name, "history": []}

    entries = []
    for entry in os.listdir(hist_root):
        entry_path = os.path.join(hist_root, entry)
        if not os.path.isdir(entry_path):
            continue
        # try to read latest meta if any
        snapshots_dir = os.path.join(entry_path, 'snapshots')
        latest_meta = None
        if os.path.exists(snapshots_dir):
            metas = [f for f in os.listdir(snapshots_dir) if f.endswith('.meta.json')]
            if metas:
                metas_sorted = sorted(metas)
                try:
                    with open(os.path.join(snapshots_dir, metas_sorted[-1]), 'r', encoding='utf-8') as f:
                        latest_meta = json.load(f)
                except Exception:
                    latest_meta = None
        entries.append({"url_hash": entry, "meta": latest_meta})

    return {"project": name, "history": entries}


@app.get("/projects/{project_name}/history/{url_hash}/raw")
async def get_raw_html(project_name: str = Path(...), url_hash: str = Path(...)):
    try:
        name, directory, _ = project_paths(project_name)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    page_dir = os.path.join(directory, 'history', url_hash)
    latest_html_path = os.path.join(page_dir, 'latest.html')
    if os.path.exists(latest_html_path):
        with open(latest_html_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return HTMLResponse(content=content)

    # Fallback: if we have an older latest_text.txt, render a simple HTML wrapper and
    # include any stored images so they are visible in the preview.
    latest_text_path = os.path.join(page_dir, 'latest_text.txt')
    images_dir = os.path.join(page_dir, 'images')
    if os.path.exists(latest_text_path):
        try:
            with open(latest_text_path, 'r', encoding='utf-8') as f:
                text = f.read()
        except Exception:
            text = ''

        imgs_html = ''
        if os.path.isdir(images_dir):
            try:
                for fname in sorted(os.listdir(images_dir)):
                    if not fname.endswith('.hex'):
                        continue
                    image_hash = fname[:-4]
                    src = f"/projects/{project_name}/history/{url_hash}/images/{image_hash}"
                    imgs_html += f'<div style="margin:8px 0"><img src="{src}" style="max-width:100%;height:auto"/></div>'
            except Exception:
                imgs_html = ''

        escaped = html.escape(text)
        wrapper = f"""
        <!doctype html>
        <html>
          <head><meta charset='utf-8'><title>Snapshot (text-only) - {project_name} / {url_hash}</title></head>
          <body>
            <div style='white-space:pre-wrap;font-family:system-ui,Arial,sans-serif;'>{escaped}</div>
            <hr/>
            <div>{imgs_html}</div>
          </body>
        </html>
        """
        return HTMLResponse(content=wrapper)

    raise HTTPException(status_code=404, detail='Latest HTML snapshot not found')


@app.get("/projects/{project_name}/history/{url_hash}/view")
async def view_html_wrapper(project_name: str = Path(...), url_hash: str = Path(...)):
    try:
        name, directory, _ = project_paths(project_name)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    raw_url = f"/projects/{encodeURIComponent(project_name)}/history/{url_hash}/raw"
    # But encodeURIComponent isn't available here; build a safe path
    raw_url = f"/projects/{project_name}/history/{url_hash}/raw"
    wrapper = f"""
    <!doctype html>
    <html>
      <head>
        <meta charset='utf-8'/>
        <title>Snapshot view - {project_name} / {url_hash}</title>
        <style>html,body,iframe{{height:100%;margin:0;padding:0;border:0}}iframe{{width:100%;border:0}}</style>
      </head>
      <body>
        <iframe src="{raw_url}" sandbox="allow-same-origin allow-scripts allow-forms"></iframe>
      </body>
    </html>
    """
    return HTMLResponse(content=wrapper)


def encodeURIComponent(s: str) -> str:
    # minimal replacement for safe path pieces
    return requests.utils.requote_uri(s)


@app.get("/projects/{project_name}/history/{url_hash}/images/{image_hash}")
async def serve_image(project_name: str = Path(...), url_hash: str = Path(...), image_hash: str = Path(...)):
    try:
        name, directory, _ = project_paths(project_name)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    img_path = os.path.join(directory, 'history', url_hash, 'images', f"{image_hash}.hex")
    if not os.path.exists(img_path):
        raise HTTPException(status_code=404, detail='Image not found')

    try:
        with open(img_path, 'r', encoding='utf-8') as f:
            hexstr = f.read().strip()
        data = bytes.fromhex(hexstr)
    except Exception:
        raise HTTPException(status_code=500, detail='Failed to read image')

    # Try to detect common image types by magic bytes (avoid imghdr dependency)
    def detect_mime(b: bytes) -> str:
        if b.startswith(b"\x89PNG\r\n\x1a\n"):
            return 'image/png'
        if b.startswith(b"\xff\xd8\xff"):
            return 'image/jpeg'
        if b.startswith(b'GIF87a') or b.startswith(b'GIF89a'):
            return 'image/gif'
        if b.startswith(b'BM'):
            return 'image/bmp'
        if len(b) >= 12 and b[0:4] == b'RIFF' and b[8:12] == b'WEBP':
            return 'image/webp'
        return 'application/octet-stream'

    content_type = detect_mime(data)
    return Response(content=data, media_type=content_type)


@app.get("/projects/{project_name}/history/{url_hash}/snapshots")
async def list_snapshots(project_name: str = Path(...), url_hash: str = Path(...)):
    try:
        name, directory, _ = project_paths(project_name)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    snapshots_dir = os.path.join(directory, 'history', url_hash, 'snapshots')
    if not os.path.exists(snapshots_dir):
        return {"project": name, "url_hash": url_hash, "snapshots": []}

    files = sorted(os.listdir(snapshots_dir))
    return {"project": name, "url_hash": url_hash, "snapshots": files}


@app.get("/projects/{project_name}/history/{url_hash}/snapshots/{fname}")
async def get_snapshot_file(project_name: str = Path(...), url_hash: str = Path(...), fname: str = Path(...)):
    try:
        name, directory, _ = project_paths(project_name)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    snapshots_dir = os.path.join(directory, 'history', url_hash, 'snapshots')
    file_path = os.path.join(snapshots_dir, fname)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail='Snapshot file not found')

    # serve diffs as text/plain and meta.json as application/json
    if fname.endswith('.diff'):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return Response(content=content, media_type='text/plain')
    elif fname.endswith('.json') or fname.endswith('.meta.json'):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = json.load(f)
        return content
    else:
        # generic file
        with open(file_path, 'rb') as f:
            data = f.read()
        return Response(content=data, media_type='application/octet-stream')



@app.get("/projects/{project_name}/history/by_url")
async def history_by_url(
    project_name: str = Path(...),
    url: str = Query(...),
    lenient: Optional[bool] = Query(True),
):
    try:
        name, directory, _ = project_paths(project_name)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        normalized = normalize_url(url, lenient=bool(lenient))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    url_hash = sha256_hex(normalized)
    page_dir = os.path.join(directory, 'history', url_hash)
    exists = os.path.exists(page_dir)
    result = {
        'project': name,
        'url': normalized,
        'url_hash': url_hash,
        'exists': exists,
        'view_url': f"/projects/{name}/history/{url_hash}/view",
        'raw_url': f"/projects/{name}/history/{url_hash}/raw",
    }
    return result


    return sanitized, directory, file_path


def read_visited(json_path: str):
    if os.path.exists(json_path):
        with open(json_path, "r") as file:
            try:
                return json.load(file)
            except json.JSONDecodeError:
                return []
    return []


def write_visited(json_path: str, data):
    with open(json_path, "w") as file:
        json.dump(data, file, indent=2)


def add_visit_entry(json_path: str, url: str, title: str) -> bool:
    data = read_visited(json_path)
    if any(entry.get("url") == url for entry in data):
        return False
    data.append({"url": url, "title": title, "timestamp": int(time.time())})
    write_visited(json_path, data)
    return True


def read_citations(json_path: str):
    """Read citations from given path. Returns list or empty list on errors."""
    if os.path.exists(json_path):
        with open(json_path, "r") as file:
            try:
                return json.load(file)
            except json.JSONDecodeError:
                return []
    return []


def write_citations(json_path: str, data):
    with open(json_path, "w") as file:
        json.dump(data, file, indent=2)


def add_citation_entry(json_path: str, citation: dict) -> bool:
    data = read_citations(json_path)
    # Avoid exact-duplicate entries (same url and selected text and title)
    is_dup = any(
        entry.get("url") == citation.get("url") and
        entry.get("selected_text") == citation.get("selected_text") and
        entry.get("title") == citation.get("title")
        for entry in data
    )
    if is_dup:
        return False
    citation.setdefault("timestamp", int(time.time()))
    data.append(citation)
    write_citations(json_path, data)
    return True


def normalize_url(url: str, lenient: bool = True) -> str:
    """Ensure the URL has a scheme. If missing, prepend https://.

    Raises ValueError if the value cannot be interpreted as a URL with a netloc.
    """
    if not isinstance(url, str) or not url.strip():
        raise ValueError('Empty URL')
    url = url.strip()
    parsed = urlparse(url)
    if not parsed.scheme:
        # Prepend https by default when no scheme is supplied
        url = 'https://' + url
        parsed = urlparse(url)
    # Basic validation: require a network location
    if not parsed.netloc:
        raise ValueError(f'Invalid URL: "{url}"')

    # More strict hostname validation: accept if hostname is an IP, 'localhost', or contains a dot
    host = parsed.hostname
    if not host:
        raise ValueError(f'Invalid URL: "{url}"')
    host = host.strip('[]')  # for IPv6 literal
    # Allow localhost
    if host.lower() == 'localhost':
        return url
    # Accept IP addresses
    try:
        ipaddress.ip_address(host)
        return url
    except Exception:
        pass

    # Require a dot in the hostname for typical FQDNs unless lenient mode is enabled
    if '.' not in host:
        if lenient:
            # accept single-label hostnames in lenient mode
            return url
        raise ValueError(f'Invalid host "{host}" in URL: provide a fully-qualified domain, IP address, or "localhost"')
def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def fetch_page_snapshot(url: str) -> Dict:
    """Fetch the page, extract full text and download/convert images to hex strings.

    Returns a dict with keys: 'text' (str), 'images' (dict mapping image_hash->hexstring),
    and 'image_map' (list of original src -> image_hash) for ordering/reference.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        # On failure return minimal snapshot with an error note in text
        return {"text": f"[ERROR_FETCHING_PAGE] {e}", "images": {}, "image_map": []}

    # Keep full HTML so styling and structure are preserved
    page_html = resp.text
    # Also extract visible text if needed elsewhere
    soup = BeautifulSoup(page_html, 'html.parser')
    page_text = soup.get_text(separator="\n", strip=True)

    images: Dict[str, str] = {}
    image_map: List[Dict[str, str]] = []

    for img in soup.find_all('img'):
        src = img.get('src') or img.get('data-src') or img.get('data-original')
        if not src:
            continue
        src = src.strip()
        try:
            if src.startswith('data:'):
                # data:[<mediatype>][;base64],<data>
                comma = src.find(',')
                if comma == -1:
                    continue
                meta = src[5:comma]
                data_part = src[comma+1:]
                if ';base64' in meta:
                    raw = base64.b64decode(data_part)
                else:
                    # percent-encoded
                    raw = data_part.encode('utf-8')
            else:
                full_url = urljoin(url, src)
                try:
                    r = requests.get(full_url, headers=headers, timeout=15)
                    r.raise_for_status()
                    raw = r.content
                except Exception:
                    continue
            hexstr = raw.hex()
            img_hash = hashlib.sha256(raw).hexdigest()
            images.setdefault(img_hash, hexstr)
            image_map.append({"src": src, "hash": img_hash})
        except Exception:
            # skip images that fail to process
            continue

    return {"html": page_html, "text": page_text, "images": images, "image_map": image_map}


def record_page_history(project_dir: str, url: str, snapshot: Dict) -> Dict:
    """Record history for a single URL under project_dir/history/<url_hash>.

    Stores latest full text at latest_text.txt and writes diffs for changes. Images are
    stored under images/ with filenames <image_hash>.hex. Returns metadata about what was saved.
    """
    history_root = os.path.join(project_dir, "history")
    url_hash = sha256_hex(url)
    page_dir = os.path.join(history_root, url_hash)
    images_dir = os.path.join(page_dir, "images")
    snapshots_dir = os.path.join(page_dir, "snapshots")
    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(snapshots_dir, exist_ok=True)

    latest_html_path = os.path.join(page_dir, "latest.html")
    prev_html = None
    if os.path.exists(latest_html_path):
        with open(latest_html_path, 'r', encoding='utf-8') as f:
            prev_html = f.read()

    current_html = snapshot.get('html') or snapshot.get('text') or ''
    ts = int(time.time())
    meta = {"timestamp": ts, "url": url, "images": [], "changed": False}

    # Handle images: write any new image hex files
    images = snapshot.get('images', {}) or {}
    for img_hash, hexstr in images.items():
        img_path = os.path.join(images_dir, f"{img_hash}.hex")
        if not os.path.exists(img_path):
            try:
                with open(img_path, 'w', encoding='utf-8') as f:
                    f.write(hexstr)
            except Exception:
                continue
        meta['images'].append(img_hash)

    # Compute diff against previous
    def _rewrite_images_in_html(html_content: str, image_map: List[Dict[str, str]]) -> str:
        try:
            soup_local = BeautifulSoup(html_content, 'html.parser')
            # build lookup from original src to hash for quick matching
            lookup = {}
            for im in image_map:
                src = im.get('src')
                h = im.get('hash')
                if src and h:
                    lookup[src] = h

            for img_tag in soup_local.find_all('img'):
                src = img_tag.get('src') or img_tag.get('data-src') or img_tag.get('data-original')
                if not src:
                    continue
                # direct match
                if src in lookup:
                    img_tag['src'] = f"images/{lookup[src]}"
                    # remove srcset to avoid browser choosing non-local variants
                    if 'srcset' in img_tag.attrs:
                        del img_tag.attrs['srcset']
                else:
                    # also try matching by the path portion in case of absolute vs relative differences
                    for orig, h in lookup.items():
                        if orig and orig.endswith(src):
                            img_tag['src'] = f"images/{h}"
                            if 'srcset' in img_tag.attrs:
                                del img_tag.attrs['srcset']
                            break

            return str(soup_local)
        except Exception:
            return html_content

    if prev_html is None:
        # first snapshot: save full html (rewrite image srcs to local relative endpoints)
        try:
            rewritten = _rewrite_images_in_html(current_html, snapshot.get('image_map', []) or [])
            with open(latest_html_path, 'w', encoding='utf-8') as f:
                f.write(rewritten)
            meta['changed'] = True
            meta['type'] = 'full'
        except Exception:
            pass
    else:
        prev_lines = prev_html.splitlines(keepends=True)
        cur_lines = current_html.splitlines(keepends=True)
        diff_lines = list(difflib.unified_diff(prev_lines, cur_lines, fromfile='prev.html', tofile='cur.html', lineterm=''))
        if diff_lines:
            diff_text = '\n'.join(diff_lines) + '\n'
            diff_filename = os.path.join(snapshots_dir, f"{ts}.diff")
            try:
                with open(diff_filename, 'w', encoding='utf-8') as f:
                    f.write(diff_text)
                # Update latest_html (rewrite image srcs)
                try:
                    rewritten = _rewrite_images_in_html(current_html, snapshot.get('image_map', []) or [])
                    with open(latest_html_path, 'w', encoding='utf-8') as f:
                        f.write(rewritten)
                except Exception:
                    # fallback to raw html
                    with open(latest_html_path, 'w', encoding='utf-8') as f:
                        f.write(current_html)
                meta['changed'] = True
                meta['type'] = 'diff'
                meta['diff_file'] = os.path.relpath(diff_filename, page_dir)
            except Exception:
                pass
        else:
            # No change
            meta['changed'] = False
            meta['type'] = 'no_change'

    # Save snapshot metadata
    meta_path = os.path.join(snapshots_dir, f"{ts}.meta.json")
    try:
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=2)
    except Exception:
        pass

    return meta


    return url


class TitleRequest(BaseModel):
    # Accept either `url` or `pubk` in incoming JSON. Normalize to `url`.
    url: Optional[str] = None
    pubk: Optional[str] = None
    projectname: Optional[str] = "random"
    lenient: Optional[bool] = True

    @root_validator(pre=True)
    def ensure_url_present(cls, values):
        # If `url` is missing but `pubk` is provided, use it as the url.
        if not values.get('url') and values.get('pubk'):
            values['url'] = values.get('pubk')
        if not values.get('url'):
            raise ValueError('Either "url" or "pubk" must be provided in the request body')
        return values


class ProjectRequest(BaseModel):
    name: str


class CitationRequest(BaseModel):
    url: Optional[str] = None
    pubk: Optional[str] = None
    projectname: Optional[str] = DEFAULT_PROJECT
    selected_text: Optional[str] = None
    title: Optional[str] = None
    author: Optional[str] = None
    publication_date: Optional[str] = None
    lenient: Optional[bool] = True

    @root_validator(pre=True)
    def ensure_url_present(cls, values):
        if not values.get('url') and values.get('pubk'):
            values['url'] = values.get('pubk')
        if not values.get('url'):
            raise ValueError('Either "url" or "pubk" must be provided in the request body')
        return values


@app.post("/title")
async def fetch_title(
    payload: Optional[TitleRequest] = Body(None),
    url: Optional[str] = Query(None),
    pubk: Optional[str] = Query(None),
    projectname: Optional[str] = Query(None),
    lenient: Optional[bool] = Query(True),
):
    """Fetch title for a given URL and record it to storage/PROJECTNAME/visited.json"""
    if payload is None and not any([url, pubk]):
        raise HTTPException(status_code=422, detail='Either "url" or "pubk" must be provided in the request body or query parameters')

    try:
        if payload is None:
            # Build the payload from query params when no JSON body is supplied
            payload = TitleRequest(url=url, pubk=pubk, projectname=projectname, lenient=lenient)
        else:
            # Merge query params over the provided body and re-validate
            updates = {k: v for k, v in {
                'url': url,
                'pubk': pubk,
                'projectname': projectname,
                'lenient': lenient,
            }.items() if v is not None}
            payload = TitleRequest(**{**payload.dict(), **updates})
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        normalized = normalize_url(payload.url, lenient=bool(payload.lenient))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        result = get_title(normalized)
    except ValueError as e:
        # client-side URL problem -> 422
        raise HTTPException(status_code=422, detail=str(e))

    if isinstance(result, str) and result.startswith("Error:"):
        # propagate as HTTP error
        raise HTTPException(status_code=502, detail=result)

    try:
        project_name, _, json_path = project_paths(payload.projectname)
        saved = add_visit_entry(json_path, normalized, result)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to write storage: {e}")

    return {"project": project_name, "url": normalized, "title": result, "saved": saved}


@app.get("/projects")
async def list_projects():
    if not os.path.exists(STORAGE_ROOT):
        return {"projects": []}
    projects = [entry for entry in os.listdir(STORAGE_ROOT) if os.path.isdir(os.path.join(STORAGE_ROOT, entry))]
    return {"projects": sorted(projects)}


@app.post("/projects")
async def create_project(payload: ProjectRequest):
    try:
        name, _, json_path = project_paths(payload.name)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    created = not os.path.exists(json_path)
    try:
        if created:
            write_visited(json_path, [])
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialize project: {e}")

    return {"name": name, "created": created}


@app.get("/projects/{project_name}/visited")
async def get_visited(project_name: str = Path(...)):
    try:
        name, _, json_path = project_paths(project_name)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        visited = read_visited(json_path)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to read storage: {e}")

    return {"project": name, "visited": visited}


@app.get("/projects/{project_name}/visited/check")
async def check_visited(
    project_name: str = Path(...),
    url: str = Query(...),
    lenient: Optional[bool] = Query(True),
):
    try:
        name, _, json_path = project_paths(project_name)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        normalized = normalize_url(url, lenient=bool(lenient))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        visited = read_visited(json_path)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to read storage: {e}")

    exists = any(entry.get("url") == normalized for entry in visited)
    return {"project": name, "url": normalized, "exists": exists}


@app.get("/projects/{project_name}/citations")
async def list_citations(project_name: str = Path(...)):
    try:
        name, _, json_path = project_paths(project_name)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    citations_path = os.path.join(os.path.dirname(json_path), "citations.json")
    try:
        citations = read_citations(citations_path)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to read storage: {e}")

    return {"project": name, "citations": citations}


@app.post("/projects/{project_name}/citations")
async def add_citation(
    project_name: str = Path(...),
    payload: Optional[CitationRequest] = Body(None),
    url: Optional[str] = Query(None),
    pubk: Optional[str] = Query(None),
    selected_text: Optional[str] = Query(None),
    title: Optional[str] = Query(None),
    lenient: Optional[bool] = Query(True),
):
    try:
        if payload is None:
            payload = CitationRequest(url=url, pubk=pubk, projectname=project_name, selected_text=selected_text, title=title, lenient=lenient)
        else:
            updates = {k: v for k, v in {
                "url": url,
                "pubk": pubk,
                "projectname": project_name,
                "selected_text": selected_text,
                "title": title,
                "lenient": lenient,
            }.items() if v is not None}
            payload = CitationRequest(**{**payload.dict(), **updates})
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        normalized = normalize_url(payload.url, lenient=bool(payload.lenient))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # If title missing, try to fetch
    citation_title = payload.title
    if not citation_title:
        try:
            maybe_title = get_title(normalized)
            if isinstance(maybe_title, str) and not maybe_title.startswith("Error:"):
                citation_title = maybe_title
        except Exception:
            citation_title = None

    citation = {
        "url": normalized,
        "title": citation_title,
        "selected_text": payload.selected_text,
        "author": payload.author if hasattr(payload, 'author') else None,
        "publication_date": payload.publication_date if hasattr(payload, 'publication_date') else None,
    }

    try:
        name, directory, _ = project_paths(project_name)
        citations_path = os.path.join(directory, "citations.json")
        saved = add_citation_entry(citations_path, citation)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to write storage: {e}")


@app.post("/projects/{project_name}/snapshot")
async def add_snapshot(
    project_name: str = Path(...),
    payload: dict = Body(...),
):
    """Accept a client-captured snapshot and record history.

    Expected payload keys: url (required), title (optional), text (optional), images (optional list of {src, dataUrl}).
    dataUrl should be a data:<mediatype>;base64,... string when provided; images without dataUrl will be listed for reference.
    """
    try:
        url = payload.get('url')
        if not url:
            raise ValueError('Missing "url" in payload')
        lenient = payload.get('lenient', True)
        normalized = normalize_url(url, lenient=bool(lenient))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Ensure project exists and add visit entry if needed
    try:
        name, directory, json_path = project_paths(project_name)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    title = payload.get('title')
    try:
        # Attempt to add a visited entry (only if not already present)
        add_visit_entry(json_path, normalized, title)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to write storage: {e}")

    # Build snapshot structure expected by record_page_history
    snapshot: dict = {}
    # Prefer full HTML when provided by client
    snapshot['html'] = payload.get('html') or payload.get('html_content') or payload.get('text') or ''
    snapshot['text'] = payload.get('text') or ''
    images_in = payload.get('images') or []
    images_map = {}
    image_map_list = []
    for img in images_in:
        src = img.get('src')
        dataUrl = img.get('dataUrl') or img.get('data_url') or img.get('data')
        if dataUrl and isinstance(dataUrl, str) and dataUrl.startswith('data:'):
            # decode base64 part
            comma = dataUrl.find(',')
            if comma != -1:
                meta = dataUrl[5:comma]
                data_part = dataUrl[comma+1:]
                try:
                    if ';base64' in meta:
                        raw = base64.b64decode(data_part)
                    else:
                        raw = data_part.encode('utf-8')
                    hexstr = raw.hex()
                    img_hash = hashlib.sha256(raw).hexdigest()
                    images_map[img_hash] = hexstr
                    image_map_list.append({"src": src, "hash": img_hash})
                except Exception:
                    # skip malformed image data
                    image_map_list.append({"src": src, "hash": None})
            else:
                image_map_list.append({"src": src, "hash": None})
        else:
            image_map_list.append({"src": src, "hash": None})

    snapshot['images'] = images_map
    snapshot['image_map'] = image_map_list

    try:
        history_meta = record_page_history(directory, normalized, snapshot)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to record history: {e}")

    return {"project": name, "url": normalized, "history": history_meta}


    return {"project": name, "url": normalized, "title": citation_title, "saved": saved}


@app.post("/projects/{project_name}/visited")
async def add_visited(
    project_name: str = Path(...),
    payload: Optional[TitleRequest] = Body(None),
    url: Optional[str] = Query(None),
    pubk: Optional[str] = Query(None),
    lenient: Optional[bool] = Query(True),
):
    try:
        if payload is None:
            payload = TitleRequest(url=url, pubk=pubk, projectname=project_name, lenient=lenient)
        else:
            updates = {k: v for k, v in {
                "url": url,
                "pubk": pubk,
                "projectname": project_name,
                "lenient": lenient,
            }.items() if v is not None}
            payload = TitleRequest(**{**payload.dict(), **updates})
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        normalized = normalize_url(payload.url, lenient=bool(payload.lenient))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        result = get_title(normalized)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    warning = None
    if isinstance(result, str) and result.startswith("Error:"):
        # If title fetch failed due to remote/network issues (403, timeouts, etc.),
        # record the visit anyway with a null title and include the error as a warning
        warning = result
        name, directory, json_path = project_paths(project_name)

        # Fetch full page snapshot (text + images) and record history diffs
        try:
            snapshot = fetch_page_snapshot(normalized)
            history_meta = record_page_history(directory, normalized, snapshot)
        except Exception as e:
            # If history recording fails, include a warning but don't block the visit save
            history_meta = {"error": str(e)}
    try:
        name, _, json_path = project_paths(project_name)
        saved = add_visit_entry(json_path, normalized, result)
    resp = {"project": name, "url": normalized, "title": result, "saved": saved, "history": history_meta}
        raise HTTPException(status_code=500, detail=f"Failed to write storage: {e}")

    resp = {"project": name, "url": normalized, "title": result, "saved": saved}
    if warning:
        resp["warning"] = warning
    return resp


if __name__ == "__main__":
    # Run with uvicorn when executed directly
    uvicorn.run(app, host="127.0.0.1", port=8000)
