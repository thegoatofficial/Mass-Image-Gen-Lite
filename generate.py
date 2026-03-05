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


def is_gemini_model(model_name):
    """Check if a model is a Gemini native image gen model (vs Imagen)."""
    return "gemini" in model_name.lower()


def fetch_image_models(client):
    """Fetch available image generation models from Google AI Studio."""
    print("Fetching available models from Google AI Studio...")
    try:
        image_models = []
        for model in client.models.list():
            name = model.name or ""
            short_name = name.removeprefix("models/")
            lower = short_name.lower()
            # Include Imagen models
            if "imagen" in lower:
                image_models.append(short_name)
            # Include Gemini models with native image generation
            elif "gemini" in lower and "image" in lower:
                image_models.append(short_name)

        if image_models:
            return sorted(set(image_models))
    except Exception as e:
        print(f"  Warning: Could not fetch models ({e})")

    # Fallback defaults
    print("  Using known default models.")
    return [
        "gemini-2.5-flash-preview-image-generation",
        "gemini-2.0-flash-exp-image-generation",
        "imagen-3.0-generate-002",
        "imagen-4.0-generate-001",
        "imagen-4.0-ultra-generate-001",
    ]


def select_model(models):
    """Interactive model selection menu."""
    # Split into Gemini and Imagen for clearer display
    gemini_models = [m for m in models if is_gemini_model(m)]
    imagen_models = [m for m in models if not is_gemini_model(m)]
    ordered = gemini_models + imagen_models

    print(f"\n{'─' * 50}")
    print("  Available Image Generation Models")
    print(f"{'─' * 50}")

    idx = 0
    if gemini_models:
        print("  Gemini (native image generation):")
        for m in gemini_models:
            idx += 1
            print(f"    [{idx}] {m}")
    if imagen_models:
        print("  Imagen (dedicated image models):")
        for m in imagen_models:
            idx += 1
            print(f"    [{idx}] {m}")

    print(f"{'─' * 50}")

    while True:
        try:
            choice = input(f"Select model (1-{len(ordered)}): ").strip()
            i = int(choice) - 1
            if 0 <= i < len(ordered):
                selected = ordered[i]
                label = "Gemini" if is_gemini_model(selected) else "Imagen"
                print(f"  -> {selected} ({label})")
                return selected
        except (ValueError, IndexError):
            pass
        print("  Invalid choice, try again.")


def load_prompts():
    """Load prompts from prompts.json."""
    if not PROMPTS_FILE.exists():
        print(f"No prompts.json found. Creating a template at:")
        print(f"  {PROMPTS_FILE}")
        template = [
            {
                "id": "example_person",
                "name": "Example Person",
                "filename": "example_person.png",
                "prompt": "Describe your image prompt here.",
            }
        ]
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


def get_images_per_prompt(model):
    """Ask how many image variants per prompt."""
    if is_gemini_model(model):
        # Gemini generates one image per call
        while True:
            try:
                raw = input("Variants per prompt (1-4) [default: 1]: ").strip()
                if not raw:
                    return 1
                n = int(raw)
                if 1 <= n <= 4:
                    if n > 1:
                        print(f"  (Gemini generates 1 image per call — will make {n} calls per prompt)")
                    return n
            except ValueError:
                pass
            print("  Enter a number between 1 and 4.")
    else:
        # Imagen supports number_of_images natively
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
    engine = "Gemini" if is_gemini_model(model) else "Imagen"
    print(f"\n{'=' * 50}")
    print(f"  Engine:            {engine}")
    print(f"  Model:             {model}")
    print(f"  Prompts:           {len(prompts)}")
    print(f"  Images per prompt: {images_per_prompt}")
    print(f"  Total images:      {total_images}")
    print(f"{'=' * 50}")

    answer = input("Start generation? (Y/n): ").strip().lower()
    if answer and answer not in ("y", "yes"):
        print("Cancelled.")
        sys.exit(0)


def generate_with_gemini(client, model, prompt, output_dir, filename_base, images_per_prompt):
    """Generate images using Gemini's native image generation."""
    saved = 0
    for v in range(images_per_prompt):
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
            ),
        )

        if not response.candidates or not response.candidates[0].content.parts:
            continue

        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                suffix = f"_{v + 1}" if images_per_prompt > 1 else ""
                img_path = output_dir / f"{filename_base}{suffix}.png"
                img = part.as_image()
                img.save(str(img_path))
                print(f"  Saved: {img_path.name}")
                saved += 1
                break  # One image per call

    return saved > 0


def generate_with_imagen(client, model, prompt, output_dir, filename_base, images_per_prompt):
    """Generate images using Imagen models."""
    response = client.models.generate_images(
        model=model,
        prompt=prompt,
        config=types.GenerateImagesConfig(
            number_of_images=images_per_prompt,
        ),
    )

    if not response.generated_images:
        return False

    for j, img in enumerate(response.generated_images):
        suffix = f"_{j + 1}" if images_per_prompt > 1 else ""
        img_path = output_dir / f"{filename_base}{suffix}.png"
        with open(img_path, "wb") as f:
            f.write(img.image.image_bytes)
        print(f"  Saved: {img_path.name}")

    return True


def generate_images(client, model, prompts, images_per_prompt):
    """Generate all images with retry logic."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_dir = OUTPUT_BASE / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    use_gemini = is_gemini_model(model)
    total = len(prompts)
    success = 0
    failed = 0
    failed_names = []

    print(f"\nSaving to: {output_dir}")
    print(f"Engine: {'Gemini native' if use_gemini else 'Imagen'}\n")

    for i, entry in enumerate(prompts, 1):
        name = entry["name"]
        prompt = entry["prompt"]
        filename_base = Path(entry["filename"]).stem

        print(f"[{i}/{total}] Generating: {name}...")

        for attempt in range(3):
            try:
                if use_gemini:
                    ok = generate_with_gemini(
                        client, model, prompt, output_dir, filename_base, images_per_prompt
                    )
                else:
                    ok = generate_with_imagen(
                        client, model, prompt, output_dir, filename_base, images_per_prompt
                    )

                if ok:
                    success += 1
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

    images_per_prompt = get_images_per_prompt(model)

    confirm_run(model, prompts, images_per_prompt)
    generate_images(client, model, prompts, images_per_prompt)


if __name__ == "__main__":
    main()
