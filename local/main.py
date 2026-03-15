import typer
import requests
from bs4 import BeautifulSoup
import json
import os

app = typer.Typer()


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
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        return soup.title.string.strip() if soup.title else "No title found"
    except requests.RequestException as e:
        return f"Error: {e}"


@app.command()
def title(
    url: str = typer.Option(..., help="URL to fetch title from"),
    projectname: str = typer.Option("random", help="Project name")
):
    """Fetch and print the title of a web page."""
    result = get_title(url)
    typer.echo(result)

    json_path = os.path.join(os.path.dirname(__file__), f'../storage/{projectname}/visited.json')
    dir_path = os.path.dirname(json_path)
    os.makedirs(dir_path, exist_ok=True)
    try:
        with open(json_path, 'r') as file:
            try:
                data = json.load(file)
            except json.JSONDecodeError:
                data = []
    except FileNotFoundError:
        data = []

    # Append the new title result
    data.append({'url': url, 'title': result})

    with open(json_path, 'w') as file:
        json.dump(data, file, indent=2)



if __name__ == "__main__":
    app()
