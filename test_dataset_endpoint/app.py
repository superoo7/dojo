import asyncio
from fastapi import Form, File, UploadFile, Request, FastAPI
from typing import List
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import aiofiles
import os
import httpx

import uvicorn
app = FastAPI()
templates = Jinja2Templates(directory="templates")


@app.post("/submit")
def submit(
    name: str = Form(...),
    point: float = Form(...),
    is_accepted: bool = Form(...),
    files: List[UploadFile] = File(...),
):
    return {
        "JSON Payload": {"name": name, "point": point, "is_accepted": is_accepted},
        "Filenames": [file.filename for file in files],
    }


@app.get("/", response_class=HTMLResponse)
async def main(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})



async def server():
    config = uvicorn.Config(app, host="0.0.0.0", port=8000)
    server = uvicorn.Server(config)
    await server.serve()

async def test_endpoint():
    # Create test data
    test_data = {
        'name': 'test_user',
        'point': 95.5,
        'is_accepted': True
    }

    # Create a temporary test file
    test_filename = "dataset_20241202.jsonl"

    # Build form data similar to how dojo.py does it
    form_body = {
        'name': ('', test_data['name']),
        'point': ('', str(test_data['point'])),
        'is_accepted': ('', str(test_data['is_accepted']))
    }

    # Add file to form data if it exists
    if os.path.exists(test_filename):
        async with aiofiles.open(test_filename, 'rb') as f:
            file_content = await f.read()
            form_body['files'] = (test_filename, file_content)
    else:
        raise FileNotFoundError(f"Test file {test_filename} not found")

    # Make request using httpx
    async with httpx.AsyncClient() as client:
        response = await client.post(
            'http://localhost:8000/submit',
            files=form_body,
            timeout=15.0
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")

if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        asyncio.run(test_endpoint())
    else:
        asyncio.run(server())
