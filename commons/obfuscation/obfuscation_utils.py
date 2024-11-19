import argparse
import asyncio
import base64
import hashlib
import os
import random
import string
from functools import partial

import minify_html
from bittensor.btlogging import logging as logger
from bs4 import BeautifulSoup
from jsmin import jsmin


# Obfuscator base class
class Obfuscator:
    @staticmethod
    def generate_random_string(length=8):
        return "".join(
            random.choices(string.ascii_letters, k=1)
            + random.choices(string.ascii_letters + string.digits, k=length - 1)
        )

    @staticmethod
    def simple_encrypt(text, key):
        return base64.b64encode(bytes([ord(c) ^ key for c in text])).decode()

    @classmethod
    def obfuscate(cls, content):
        raise NotImplementedError("Subclasses must implement this method")


class HTMLandJSObfuscator(Obfuscator):
    @classmethod
    def obfuscate(cls, html_content):
        try:
            minify_params = {
                "do_not_minify_doctype": True,
                "ensure_spec_compliant_unquoted_attribute_values": True,
                "keep_comments": True,
                "keep_html_and_head_opening_tags": True,
                "keep_input_type_text_attr": True,
                "keep_spaces_between_attributes": True,
                "keep_ssi_comments": True,
                "preserve_brace_template_syntax": True,
                "preserve_chevron_percent_template_syntax": True,
                "remove_bangs": True,
                "remove_processing_instructions": True,
            }

            # Always include keep_closing_tags=True to avoid breaking the HTML structure
            selected_params = {"keep_closing_tags": True}
            random_params = random.sample(minify_params.items(), 5)
            selected_params.update(random_params)

            # Use minify to obfuscate the JavaScript code
            minified_content = minify_html.minify(
                html_content,
                **selected_params,
            )

            # Apply a random number of obfuscation techniques
            obfuscated_content = cls.apply_techniques(minified_content)

            # Optionally add random comments (50% chance)
            if random.random() < 0.5:
                obfuscated_content = cls.add_enclosing_comments(obfuscated_content)

            return obfuscated_content
        except Exception as e:
            logger.error(f"Minification failed: {str(e)}")
            logger.warning("Falling back to simple minification.")
            return cls.simple_minify(html_content)

    @classmethod
    def apply_techniques(cls, content):
        techniques = [
            cls.add_random_attributes,
            cls.add_dummy_elements,
            cls.shuffle_attributes,
        ]
        num_techniques = random.randint(1, len(techniques))
        chosen_techniques = random.sample(techniques, num_techniques)

        soup = BeautifulSoup(content, "html.parser")
        for technique in chosen_techniques:
            soup = technique(soup)
        return str(soup)

    @classmethod
    def add_enclosing_comments(cls, content):
        return (
            f"<!-- {cls.generate_random_string(16)} -->\n"
            f"{content}\n"
            f"<!-- {cls.generate_random_string(16)} -->"
        )

    @classmethod
    def add_random_attributes(cls, soup):
        for tag in soup.find_all():
            if random.random() < 0.3:
                tag[cls.generate_random_string(5)] = cls.generate_random_string(8)
        return soup

    @classmethod
    def add_dummy_elements(cls, soup):
        dummy_elements = [
            soup.new_tag(
                "div", style="display:none;", string=cls.generate_random_string(20)
            )
            for _ in range(random.randint(1, 5))
        ]
        soup.body.extend(dummy_elements)
        return soup

    @staticmethod
    def shuffle_attributes(soup):
        for tag in soup.find_all():
            tag.attrs = dict(random.sample(list(tag.attrs.items()), len(tag.attrs)))
        return soup

    @staticmethod
    def simple_minify(js_code):
        return jsmin(js_code)


async def obfuscate_html_and_js(html_content, timeout=30):
    loop = asyncio.get_event_loop()
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(
                None, partial(_obfuscate_html_and_js_sync, html_content)
            ),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        logger.error(f"Obfuscation timed out after {timeout} seconds")
        return html_content  # Return original content if obfuscation times out


def _obfuscate_html_and_js_sync(html_content):
    return HTMLandJSObfuscator.obfuscate(html_content)


async def process_file(input_file: str, output_file: str):
    try:
        with open(input_file, encoding="utf-8") as file:
            original_content = file.read()
    except FileNotFoundError:
        logger.error(f"Error: The file '{input_file}' was not found.")
        return
    except OSError:
        logger.error(f"Error: Could not read the file '{input_file}'.")
        return

    obfuscated = await obfuscate_html_and_js(original_content)

    try:
        with open(output_file, "w", encoding="utf-8") as file:
            file.write(obfuscated)
        logger.info(f"Obfuscated content has been written to '{output_file}'")

        # Calculate and display hashes to show difference
        original_hash = hashlib.md5(original_content.encode()).hexdigest()
        obfuscated_hash = hashlib.md5(obfuscated.encode()).hexdigest()
        logger.info(f"\nOriginal content MD5: {original_hash}")
        logger.info(f"Obfuscated content MD5: {obfuscated_hash}")
    except OSError:
        logger.error(f"Error: Could not write to the file '{output_file}'.")


# Function to test the obfuscation
# Command to run: python obfuscation_utils.py input.html
async def main():
    parser = argparse.ArgumentParser(
        description="Obfuscate HTML and JavaScript content"
    )
    parser.add_argument("input_file", help="Path to the input HTML file")
    parser.add_argument(
        "-o", "--output", help="Path to the output obfuscated HTML file (optional)"
    )
    args = parser.parse_args()

    # Generate default output filename based on input filename
    input_filename = os.path.basename(args.input_file)
    input_name, input_ext = os.path.splitext(input_filename)
    output_file = args.output or f"{input_name}_obfuscated{input_ext}"

    await process_file(args.input_file, output_file)


if __name__ == "__main__":
    asyncio.run(main())
