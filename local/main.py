import time
import requests
from bs4 import BeautifulSoup
import json
import os
import re
from typing import Optional
from urllib.parse import urlparse
import ipaddress
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
        result = None

    try:
        name, _, json_path = project_paths(project_name)
        saved = add_visit_entry(json_path, normalized, result)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to write storage: {e}")

    resp = {"project": name, "url": normalized, "title": result, "saved": saved}
    if warning:
        resp["warning"] = warning
    return resp


if __name__ == "__main__":
    # Run with uvicorn when executed directly
    uvicorn.run(app, host="127.0.0.1", port=8000)
