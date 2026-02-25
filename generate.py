import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
from google import genai
from google.genai import types

SCRIPT_DIR = Path(__file__).parent.resolve()
PROMPTS_FILE = SCRIPT_DIR / "prompts.json"
OUTPUT_BASE = SCRIPT_DIR / "generated_images"


def get_client():
    load_dotenv(SCRIPT_DIR / ".env")
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("Error: GOOGLE_API_KEY not found.")
        print("Add your key to .env:  GOOGLE_API_KEY=your_key_here")
        sys.exit(1)
    return genai.Client(api_key=api_key)


def fetch_image_models(client):
    """Fetch available image generation models from Google AI Studio."""
    print("Fetching available models from Google AI Studio...")
    try:
        imagen_models = []
        for model in client.models.list():
            name = model.name or ""
            # Models come back as "models/imagen-..." — strip the prefix
            short_name = name.removeprefix("models/")
            if "imagen" in short_name.lower():
                imagen_models.append(short_name)

        if imagen_models:
            return sorted(set(imagen_models))
    except Exception as e:
        print(f"  Warning: Could not fetch models ({e})")

    # Fallback defaults if API didn't return any or errored
    print("  Using known default models.")
    return [
        "imagen-3.0-generate-001",
        "imagen-3.0-generate-002",
        "imagen-4.0-generate-001",
        "imagen-4.0-ultra-generate-001",
    ]


def select_model(models):
    """Interactive model selection menu."""
    print(f"\n{'─' * 42}")
    print("  Available Image Generation Models")
    print(f"{'─' * 42}")
    for i, model in enumerate(models, 1):
        print(f"  [{i}] {model}")
    print(f"{'─' * 42}")

    while True:
        try:
            choice = input(f"Select model (1-{len(models)}): ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(models):
                print(f"  -> {models[idx]}")
                return models[idx]
        except (ValueError, IndexError):
            pass
        print("  Invalid choice, try again.")


def load_prompts():
    """Load prompts from prompts.json."""
    if not PROMPTS_FILE.exists():
        print(f"No prompts.json found. Creating a template at:")
        print(f"  {PROMPTS_FILE}")
        template = {"Example Person": "Describe your image prompt here."}
        with open(PROMPTS_FILE, "w") as f:
            json.dump(template, f, indent=2)
        print("Edit prompts.json with your prompts and run again.")
        sys.exit(0)

    with open(PROMPTS_FILE, "r") as f:
        prompts = json.load(f)

    if not prompts:
        print("prompts.json is empty. Add some prompts and run again.")
        sys.exit(0)

    print(f"Loaded {len(prompts)} prompt(s) from prompts.json")
    return prompts


def get_images_per_prompt():
    """Ask how many image variants per prompt (1-4)."""
    while True:
        try:
            raw = input("Images per prompt (1-4) [default: 1]: ").strip()
            if not raw:
                return 1
            n = int(raw)
            if 1 <= n <= 4:
                return n
        except ValueError:
            pass
        print("  Enter a number between 1 and 4.")


def confirm_run(model, prompts, images_per_prompt):
    """Show summary and ask for confirmation before starting."""
    total_images = len(prompts) * images_per_prompt
    print(f"\n{'=' * 50}")
    print(f"  Model:             {model}")
    print(f"  Prompts:           {len(prompts)}")
    print(f"  Images per prompt: {images_per_prompt}")
    print(f"  Total images:      {total_images}")
    print(f"{'=' * 50}")

    answer = input("Start generation? (Y/n): ").strip().lower()
    if answer and answer not in ("y", "yes"):
        print("Cancelled.")
        sys.exit(0)


def generate_images(client, model, prompts, images_per_prompt):
    """Generate all images with retry logic."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_dir = OUTPUT_BASE / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    total = len(prompts)
    success = 0
    failed = 0
    failed_names = []

    print(f"\nSaving to: {output_dir}\n")

    for i, (name, prompt) in enumerate(prompts.items(), 1):
        print(f"[{i}/{total}] Generating: {name}...")

        generated = False
        for attempt in range(3):
            try:
                response = client.models.generate_images(
                    model=model,
                    prompt=prompt,
                    config=types.GenerateImagesConfig(
                        number_of_images=images_per_prompt,
                    ),
                )

                if response.generated_images:
                    for j, img in enumerate(response.generated_images):
                        suffix = f"_{j + 1}" if images_per_prompt > 1 else ""
                        img_path = output_dir / f"{name}{suffix}.png"
                        with open(img_path, "wb") as f:
                            f.write(img.image.image_bytes)
                        print(f"  Saved: {img_path.name}")
                    success += 1
                    generated = True
                else:
                    print(f"  No image returned by API")
                    failed += 1
                    failed_names.append(name)
                break

            except Exception as e:
                if attempt < 2:
                    wait = (attempt + 1) * 3
                    print(f"  Retry {attempt + 1}/2 in {wait}s... ({e})")
                    time.sleep(wait)
                else:
                    print(f"  Failed after 3 attempts: {e}")
                    failed += 1
                    failed_names.append(name)

    # Summary
    print(f"\n{'=' * 50}")
    print(f"  Completed: {success}/{total} succeeded, {failed} failed")
    if failed_names:
        print(f"  Failed:    {', '.join(failed_names)}")
    print(f"  Output:    {output_dir}")
    print(f"{'=' * 50}")


def main():
    print()
    print("  Bulk Image Generator")
    print("  ====================")
    print()

    client = get_client()
    prompts = load_prompts()

    models = fetch_image_models(client)
    model = select_model(models)

    images_per_prompt = get_images_per_prompt()

    confirm_run(model, prompts, images_per_prompt)
    generate_images(client, model, prompts, images_per_prompt)


if __name__ == "__main__":
    main()
