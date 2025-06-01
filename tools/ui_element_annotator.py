"""
UI Element Annotator

A standalone tool for batch processing of Android app screenshots to identify and annotate UI elements.
This tool uses Google's Gemini Vision AI to analyze screenshots and detect UI elements such as buttons,
text fields, and other interactive components, saving their locations and properties in a JSON file.

Features:
- Batch processing of screenshot directories
- Normalized coordinate system (0.0-1.0) for element positions
- JSON output format compatible with manual annotation tools
- Support for common Android UI element types
- Detailed element property extraction (type, description, resource_id, bounding_box)

Usage:
    python -m tools.ui_element_annotator --input-dir "path/to/screenshots" --output-file "annotations.json"

The output JSON structure follows the format:
{
    "screenshot1.png": [
        {
            "type": "button",
            "description": "Login",
            "resource_id": "com.example.app:id/login_button",
            "bounding_box": {
                "top_left": [y1, x1],
                "bottom_right": [y2, x2]
            }
        },
        ...
    ],
    ...
}
"""

import google.generativeai as genai
from google.generativeai.client import configure as genai_configure
from google.generativeai.generative_models import GenerativeModel
from google.generativeai.types import GenerationConfig
from google.ai import generativelanguage as glm
from google.ai.generativelanguage import Schema, Type as GLMType, Content, Part

import os
import json
import logging
from typing import Dict, Any, List, Optional
from PIL import Image
import io
from pathlib import Path
import argparse
from dotenv import load_dotenv
import time
from functools import partial
import re

class UIElementAnnotator:
    @staticmethod
    def _get_ui_element_schema() -> Schema:
        """Defines the schema for a UI element."""
        return Schema(
            type=GLMType.OBJECT,
            description="Represents a single identifiable UI element on the screen.",
            properties={
                'type': Schema(
                    type=GLMType.STRING,
                    description="The type of the UI element (e.g., button, editText, textView, etc.)."
                ),
                'description': Schema(
                    type=GLMType.STRING,
                    nullable=True,
                    description="Visible text content or accessibility label of the element."
                ),
                'resource_id': Schema(
                    type=GLMType.STRING,
                    nullable=True,
                    description="The resource-id of the element, if available from XML."
                ),
                'bounding_box': Schema(
                    type=GLMType.OBJECT,
                    nullable=True,
                    properties={
                        'top_left': Schema(type=GLMType.ARRAY, items=Schema(type=GLMType.NUMBER)),
                        'bottom_right': Schema(type=GLMType.ARRAY, items=Schema(type=GLMType.NUMBER))
                    },
                    required=['top_left', 'bottom_right']
                )
            },
            required=['type', 'bounding_box']
        )

    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash-preview-05-20"):
        self.api_key = api_key
        genai_configure(api_key=self.api_key)
        
        generation_config = GenerationConfig(
            temperature=0.3,
            top_p=0.8,
            top_k=20,
            max_output_tokens=8192,
            response_mime_type="application/json",
            response_schema=Schema(
                type=GLMType.ARRAY,
                items=self._get_ui_element_schema(),
                description="List of all UI elements detected in the image."
            )
        )

        self.model = GenerativeModel(
            model_name=model_name,
            generation_config=generation_config
        )

    def _prepare_image(self, image_path: str) -> Optional[Content]:
        try:
            with Image.open(image_path) as img:
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format='PNG')
                img_bytes = img_byte_arr.getvalue()
                return Content(parts=[Part(inline_data=glm.Blob(mime_type="image/png", data=img_bytes))])
        except Exception as e:
            logging.error(f"Failed to prepare image {image_path}: {e}")
            return None

    def _clean_json_response(self, text: str) -> str:
        """Clean and validate JSON response text."""
        # Remove any markdown code block markers
        text = re.sub(r'```(?:json)?\s*|\s*```', '', text)
        # Remove any trailing commas before closing brackets/braces
        text = re.sub(r',(\s*[\]}])', r'\1', text)
        # Remove any non-JSON text before or after the actual JSON content
        text = text.strip()
        if not text.startswith('['):
            start_idx = text.find('[')
            if start_idx != -1:
                text = text[start_idx:]
        if not text.endswith(']'):
            end_idx = text.rfind(']')
            if end_idx != -1:
                text = text[:end_idx+1]
        return text

    def annotate_image(self, image_path: str, max_retries: int = 3) -> Optional[List[Dict[str, Any]]]:
        image_content = self._prepare_image(image_path)
        if not image_content:
            return None

        prompt = """
        Analyze this screenshot and identify ALL UI elements visible in the image.
        For each element, provide:
        1. The element type (button, editText, textView, etc.)
        2. Any visible text or accessibility description
        3. Any resource ID if visible
        4. Normalized bounding box coordinates (values 0.0-1.0)
           - top_left: [y1, x1]
           - bottom_right: [y2, x2]
           where (0,0) is top-left of screen, (1,1) is bottom-right
        
        Be thorough and precise with coordinate estimation.
        IMPORTANT: Ensure output is valid JSON array. Do not include any explanatory text.
        """
        
        for attempt in range(max_retries):
            try:
                content_message = Content(parts=[Part(text=prompt)], role="user")
                response = self.model.generate_content([content_message, image_content])
                
                if not response.candidates:
                    logging.error(f"No response candidates for {image_path} (attempt {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        time.sleep(1)
                    continue

                try:
                    cleaned_text = self._clean_json_response(response.text)
                    elements = json.loads(cleaned_text)
                    if isinstance(elements, list):
                        return elements
                    logging.error(f"Invalid response format for {image_path} - not a list")
                except json.JSONDecodeError as e:
                    logging.error(f"JSON decode error on attempt {attempt + 1}/{max_retries} for {image_path}: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(1)
                    continue

            except Exception as e:
                logging.error(f"Error annotating {image_path} (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                continue

        logging.error(f"Failed to annotate {image_path} after {max_retries} attempts")
        return None

    def batch_process_directory(self, input_dir: str, output_file: str):
        input_path = Path(input_dir)
        if not input_path.exists():
            logging.error(f"Input directory does not exist: {input_dir}")
            return

        results = {}
        failed_images = []

        for img_path in input_path.glob("*.png"):
            logging.info(f"Processing {img_path.name}...")
            elements = self.annotate_image(str(img_path))
            if elements:
                results[img_path.name] = elements
            else:
                failed_images.append(img_path.name)

        if results:
            try:
                # Ensure output directory exists
                output_dir = os.path.dirname(output_file)
                if not os.path.exists(output_dir):
                    os.makedirs(output_dir, exist_ok=True)
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(results, f, indent=2, ensure_ascii=False)
                logging.info(f"Results saved to {output_file}")
            except Exception as e:
                logging.error(f"Error saving results to {output_file}: {e}")
        
        if failed_images:
            logging.warning(f"Failed to process {len(failed_images)} images: {', '.join(failed_images)}")
            # Save failed image list for reference
            failed_list_file = os.path.join(os.path.dirname(output_file), f"{Path(output_file).stem}_failed_annotations.txt")
            try:
                with open(failed_list_file, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(failed_images))
                logging.info(f"List of failed images saved to {failed_list_file}")
            except Exception as e:
                logging.error(f"Error saving failed images list: {e}")

def main():
    parser = argparse.ArgumentParser(description='Batch annotate UI elements in screenshots')
    parser.add_argument('--input-dir', required=True, help='Directory containing screenshot images')
    parser.add_argument('--output-dir', required=True, help='Base directory for output JSON file')
    parser.add_argument('--app-identifier', required=True, help='App identifier (e.g., package name) for naming the output file')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    load_dotenv()
    
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        logging.error("GEMINI_API_KEY not found in environment variables")
        return

    # Resolve paths relative to project root
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    input_dir = os.path.normpath(os.path.join(project_root, args.input_dir))
    # Construct the output file name
    output_filename = f"{args.app_identifier}_annotations.json"
    output_file = os.path.normpath(os.path.join(project_root, args.output_dir, output_filename))

    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    logging.info(f"Using input directory: {input_dir}")
    logging.info(f"Output will be saved to: {output_file}")

    if not os.path.exists(input_dir):
        logging.error(f"Input directory does not exist: {input_dir}")
        logging.info("Note: Paths should be relative to project root directory")
        logging.info(f"Project root detected as: {project_root}")
        return

    annotator = UIElementAnnotator(api_key)
    annotator.batch_process_directory(input_dir, output_file)

if __name__ == '__main__':
    main()
