# Mass Image Gen Lite

Bulk image generator using Google's Imagen models via the AI Studio API. Define your prompts in a JSON file, pick a model, and generate images in batch.

## Features

- **Dynamic model selection** — fetches available Imagen models directly from Google AI Studio so you always have the latest options
- **Batch generation** — generate images for multiple prompts in one run
- **Multiple variants** — generate 1-4 image variants per prompt
- **Auto-retry** — failed API calls retry up to 3 times with backoff
- **Timestamped output** — each run saves to its own folder so nothing gets overwritten
- **Externalized prompts** — edit `prompts.json` without touching the code
- **Secure API key** — stored in `.env`, kept out of version control

## Installation

### 1. Clone the repo

```bash
git clone https://github.com/thegoatofficial/Mass-Image-Gen-Lite.git
cd Mass-Image-Gen-Lite
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Add your API key

Get a free API key from [Google AI Studio](https://aistudio.google.com/apikey).

Create a `.env` file in the project root:

```
GOOGLE_API_KEY=your_api_key_here
```

Replace `your_api_key_here` with your actual key. This file is gitignored and will not be committed.

### 4. Add your prompts

Edit `prompts.json` with your image prompts:

```json
{
  "Person Name": "A detailed description of the image you want...",
  "Another Name": "Another detailed prompt..."
}
```

The key is used as the output filename and the value is the prompt sent to the model.

## Usage

```bash
python generate.py
```

The tool will walk you through:

1. **Model selection** — pick from available Imagen models
2. **Images per prompt** — choose how many variants (1-4) to generate per prompt
3. **Confirmation** — review the run summary before starting
4. **Generation** — sit back while it generates all your images

Output is saved to `generated_images/<timestamp>/` in the project directory.

## Project Structure

```
Mass-Image-Gen-Lite/
  .env                  # Your API key (not committed)
  .gitignore
  generate.py           # Main script
  prompts.json          # Your prompts
  requirements.txt
  generated_images/     # Created on first run
```
